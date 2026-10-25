import numpy as np
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_

from framewise.api.presenters import photo_query, required, serialize
from framewise.api.schemas import FinalistUpdate, HighlightConfigUpdate, HighlightDecisionUpdate
from framewise.curation.highlights import rebuild, state_for
from framewise.curation.standouts import VERSION
from framewise.db.models import (
    HighlightDecision,
    HighlightFeedback,
    HighlightRanking,
    Library,
    Photo,
    PhotoDecision,
    PhotoEmbedding,
    Session,
)

router = APIRouter(prefix="/api")


@router.get("/libraries/{library_id}/highlights/compare")
def compare(library_id: str, left: str, right: str):
    with Session() as db:
        required(db, Library, library_id)
        first, second = required(db, Photo, left), required(db, Photo, right)
        if any(p.library_id != library_id or p.status != "ready" for p in (first, second)):
            raise HTTPException(422, "Choose analysed photographs from this collection")
        distance = (
            (int(first.phash, 16) ^ int(second.phash, 16)).bit_count()
            if first.phash and second.phash
            else None
        )
        a, b = db.get(PhotoEmbedding, left), db.get(PhotoEmbedding, right)
        cosine = None
        if (
            a
            and b
            and a.model_id == b.model_id
            and a.identity == first.identity
            and b.identity == second.identity
        ):
            va, vb = np.frombuffer(a.vector, dtype=np.float32), np.frombuffer(b.vector, dtype=np.float32)
            if va.shape == vb.shape == (512,) and np.isfinite(va).all() and np.isfinite(vb).all():
                denominator = float(np.linalg.norm(va) * np.linalg.norm(vb))
                if denominator > 0:
                    cosine = float(np.clip((va @ vb) / denominator, -1, 1))
        return {
            "phash_distance": distance,
            "cosine_similarity": cosine,
            "same_similarity_group": bool(first.group_id and first.group_id == second.group_id),
        }


def payload(db, library, flickr_page=1):
    state = state_for(db, library.id)
    ranking = photo_query(db, library.id)
    summary = dict(state.summary)

    def items(ids):
        if not ids or state.status != "ready":
            return []
        values = {row[0].id: serialize(row, library.source) for row in ranking.filter(Photo.id.in_(ids))}
        return [values[key] for key in ids if key in values]

    return {
        "status": state.status,
        "config": state.config,
        "summary": summary,
        "updated": state.updated,
        "flickr": items(summary.get("flickr", [])[(flickr_page - 1) * 48 : flickr_page * 48]),
        "flickr_page": flickr_page,
        "finalists": items(summary.get("finalists", [])),
        "alternatives": items(summary.get("alternatives", [])[:24]),
    }


def ready(db, library):
    state = state_for(db, library.id)
    if state.status != "ready":
        raise HTTPException(409, "Complete or resume the scan before changing Highlights recommendations")
    return state


def decision_record(db, photo_id):
    item = db.get(HighlightDecision, photo_id)
    if item is None:
        item = HighlightDecision(photo_id=photo_id, flickr="auto", competition="auto")
        db.add(item)
        db.flush()
    return item


def decision_data(item):
    return {"flickr": item.flickr, "competition": item.competition, "competition_rank": item.competition_rank}


def feedback(db, library, photo_id, action, before, after):
    state = state_for(db, library.id)
    ranking = db.get(HighlightRanking, photo_id)
    db.add(
        HighlightFeedback(
            library_id=library.id,
            photo_id=photo_id,
            action=action,
            before=before,
            after=after,
            context={"version": VERSION, "config": state.config, "ranking": ranking.data if ranking else {}},
        )
    )


@router.get("/libraries/{library_id}/highlights")
def highlights(library_id: str, flickr_page: int = Query(1, ge=1)):
    with Session.begin() as db:
        return payload(db, required(db, Library, library_id), flickr_page)


@router.patch("/libraries/{library_id}/highlights/config")
def configure(library_id: str, body: HighlightConfigUpdate):
    with Session.begin() as db:
        library = required(db, Library, library_id)
        state = state_for(db, library_id)
        state.config = body.model_dump()
        rebuild(db, library)
        db.flush()
        return payload(db, library)


@router.post("/libraries/{library_id}/highlights/recalculate")
def recalculate(library_id: str):
    with Session.begin() as db:
        library = required(db, Library, library_id)
        rebuild(db, library)
        db.flush()
        return payload(db, library)


@router.patch("/photos/{photo_id}/highlights")
def update_decision(photo_id: str, body: HighlightDecisionUpdate):
    with Session.begin() as db:
        photo = required(db, Photo, photo_id)
        library = required(db, Library, photo.library_id)
        ready(db, library)
        if photo.status != "ready":
            raise HTTPException(409, "This photo has no available analysis")
        item = decision_record(db, photo_id)
        before = decision_data(item)
        if body.flickr is not None:
            item.flickr = body.flickr
            if body.flickr == "keep" and body.include_lightroom:
                lightroom = db.get(PhotoDecision, photo_id)
                if lightroom is None:
                    db.add(PhotoDecision(photo_id=photo_id, decision="keep"))
                else:
                    lightroom.decision = "keep"
        if body.competition is not None:
            item.competition = body.competition
            item.competition_rank = None
        feedback(db, library, photo_id, "recommendation", before, decision_data(item))
        db.flush()
        rebuild(db, library)
        db.flush()
        return payload(db, library)


@router.put("/libraries/{library_id}/highlights/finalists/{slot}")
def replace(library_id: str, slot: int, body: FinalistUpdate):
    if slot not in (1, 2, 3):
        raise HTTPException(422, "Finalist rank must be 1, 2 or 3")
    with Session.begin() as db:
        library = required(db, Library, library_id)
        ready(db, library)
        photo = required(db, Photo, body.photo_id)
        if photo.library_id != library_id or photo.status != "ready":
            raise HTTPException(422, "Choose an analysed photograph from this collection")
        # Snapshot the displayed finalists so promotion swaps places; replacement demotes the old slot.
        current = (
            db.query(HighlightRanking)
            .filter_by(library_id=library_id)
            .filter(HighlightRanking.competition_rank.is_not(None))
            .all()
        )
        old_slot = next((r.competition_rank for r in current if r.photo_id == photo.id), None)
        target = next((r for r in current if r.competition_rank == slot), None)
        for result in current:
            item = decision_record(db, result.photo_id)
            before = decision_data(item)
            if result.photo_id == photo.id:
                continue
            if result is target:
                item.competition_rank = old_slot
                item.competition = "include" if old_slot else "alternative"
            else:
                item.competition_rank = result.competition_rank
                item.competition = "include"
            feedback(db, library, result.photo_id, "finalist displacement", before, decision_data(item))
        chosen = decision_record(db, photo.id)
        before = decision_data(chosen)
        chosen.competition_rank, chosen.competition = slot, "include"
        feedback(db, library, photo.id, f"finalist rank {slot}", before, decision_data(chosen))
        db.flush()
        rebuild(db, library)
        db.flush()
        return payload(db, library)


@router.get("/libraries/{library_id}/highlights/search")
def search(library_id: str, q: str = Query("", max_length=200), page: int = Query(1, ge=1)):
    with Session() as db:
        library = required(db, Library, library_id)
        query = photo_query(db, library_id).filter(Photo.status == "ready")
        if q:
            # SQLAlchemy binds the value; escaping wildcards makes filename search literal.
            term = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = query.filter(
                or_(
                    Photo.filename.ilike(f"%{term}%", escape="\\"),
                    Photo.relative_path.ilike(f"%{term}%", escape="\\"),
                )
            )
        return {
            "total": query.count(),
            "page": page,
            "limit": 24,
            "items": [
                serialize(row, library.source)
                for row in query.order_by(
                    HighlightRanking.candidate_rank.is_(None),
                    HighlightRanking.candidate_rank,
                    Photo.score.desc(),
                    Photo.id,
                )
                .offset((page - 1) * 24)
                .limit(24)
            ],
        }
