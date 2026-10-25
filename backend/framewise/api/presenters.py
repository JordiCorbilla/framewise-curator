from fastapi import HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import aliased

from framewise.db.models import (
    HighlightDecision,
    HighlightRanking,
    HighlightState,
    Photo,
    PhotoDecision,
    PhotoMetadata,
    PhotoMetrics,
    PhotoRawSource,
    ScanJob,
    SimilarityGroup,
)
from framewise.imaging.acquisition import source_path


def required(db, cls, object_id):
    item = db.get(cls, object_id)
    if item is None:
        raise HTTPException(404, "Not found")
    return item


def photo_query(db, library_id):
    raw = aliased(Photo)
    return (
        db.query(
            Photo,
            PhotoMetrics,
            PhotoDecision,
            PhotoMetadata,
            SimilarityGroup,
            HighlightRanking,
            HighlightDecision,
            HighlightState,
            raw,
        )
        .outerjoin(PhotoMetrics, PhotoMetrics.photo_id == Photo.id)
        .outerjoin(PhotoDecision, PhotoDecision.photo_id == Photo.id)
        .outerjoin(PhotoMetadata, PhotoMetadata.photo_id == Photo.id)
        .outerjoin(SimilarityGroup, SimilarityGroup.id == Photo.group_id)
        .outerjoin(HighlightRanking, HighlightRanking.photo_id == Photo.id)
        .outerjoin(HighlightDecision, HighlightDecision.photo_id == Photo.id)
        .outerjoin(HighlightState, HighlightState.library_id == Photo.library_id)
        .outerjoin(PhotoRawSource, PhotoRawSource.photo_id == Photo.id)
        .outerjoin(raw, raw.id == PhotoRawSource.raw_photo_id)
        .filter(Photo.library_id == library_id)
    )


def selected_expression():
    return and_(
        Photo.status == "ready",
        or_(
            PhotoDecision.decision == "keep",
            and_(
                or_(PhotoDecision.decision.is_(None), PhotoDecision.decision == "auto"),
                Photo.recommendation == "pick",
            ),
        ),
    )


def serialize(row, source):
    p, metrics, decision, metadata, group, highlight, highlight_manual, highlight_state, paired_raw = row
    raw = p if p.filename.lower().endswith(".nef") else paired_raw
    manual = decision.decision if decision else "auto"
    selected = p.status == "ready" and (manual == "keep" or (manual == "auto" and p.recommendation == "pick"))
    calibrated = metrics.calibrated if metrics else {}
    explanation = []
    if metrics and metrics.aesthetic is not None:
        explanation.append(f"Aesthetic model {metrics.aesthetic:.2f}/10")
    else:
        explanation.append("Aesthetic assessment unavailable; technical ranking only")
    if calibrated:
        explanation.append(f"Detail {calibrated['sharpness']:.0f}/100; focus {calibrated['focus_risk']}")
    if group:
        explanation.append(f"Frame {p.group_rank} of {group.count}; {group.reason}")
    return {
        "id": p.id,
        "library_id": p.library_id,
        "filename": p.filename,
        "relative_path": p.relative_path,
        "original_path": str(source_path(source, p.relative_path)),
        "raw_original_path": str(source_path(source, raw.relative_path)) if raw else None,
        "raw_relative_path": raw.relative_path if raw else None,
        "raw_filename": raw.filename if raw else None,
        "status": p.status,
        "error": p.error,
        "provenance": p.provenance,
        "width": p.width,
        "height": p.height,
        "score": p.score,
        "recommendation": p.recommendation,
        "selection_rank": p.selection_rank,
        "aesthetic": metrics.aesthetic if metrics else None,
        "raw": metrics.raw if metrics else {},
        "calibrated": calibrated,
        "model_id": metrics.model_id if metrics else None,
        "highlights": (
            {
                **highlight.data,
                "flickr": highlight.flickr,
                "competition_rank": highlight.competition_rank,
                "candidate_rank": highlight.candidate_rank,
                "flickr_decision": highlight_manual.flickr if highlight_manual else "auto",
                "competition_decision": highlight_manual.competition if highlight_manual else "auto",
            }
            if highlight and highlight_state and highlight_state.status == "ready" and p.status == "ready"
            else None
        ),
        "metadata": metadata.data if metadata else {},
        "decision": manual,
        "stars": decision.stars if decision else 0,
        "selected": selected,
        "group_id": p.group_id,
        "group_rank": p.group_rank,
        "group_count": group.count if group else 1,
        "group_protected": group.protected if group else False,
        "explanation": "; ".join(explanation) + ".",
        "thumbnail": f"/api/photos/{p.id}/thumbnail" if p.status == "ready" else None,
        "preview": f"/api/photos/{p.id}/preview" if p.status == "ready" else None,
    }


def library_info(db, lib):
    counts = dict(
        db.query(Photo.status, func.count()).filter_by(library_id=lib.id).group_by(Photo.status).all()
    )
    latest = db.query(ScanJob).filter_by(library_id=lib.id).order_by(ScanJob.created.desc()).first()
    selected = photo_query(db, lib.id).filter(selected_expression()).count()
    averages = (
        photo_query(db, lib.id)
        .filter(selected_expression())
        .with_entities(
            func.avg(PhotoMetrics.aesthetic),
            func.avg(PhotoMetrics.calibrated["sharpness"].as_float()),
            func.avg(PhotoMetrics.calibrated["exposure"].as_float()),
        )
        .one()
    )
    cover = db.query(Photo).filter_by(library_id=lib.id, status="ready").order_by(Photo.score.desc()).first()
    return {
        "id": lib.id,
        "name": lib.name,
        "source": lib.source,
        "created": lib.created,
        "budget": lib.budget,
        "config": lib.config,
        "total": sum(counts.values()),
        "ready": counts.get("ready", 0),
        "failed": counts.get("failed", 0),
        "selected": selected,
        "summary": {"aesthetic": averages[0], "sharpness": averages[1], "exposure": averages[2]},
        "cover": f"/api/photos/{cover.id}/preview" if cover else None,
        "job": job_info(latest) if latest else None,
        "highlights": (
            {"status": state.status, **state.summary}
            if (state := db.get(HighlightState, lib.id))
            else {"status": "waiting"}
        ),
    }


def job_info(job):
    progress = dict(job.progress)
    if "elapsed" in progress:
        progress["speed"] = round(
            (progress.get("processed", 0) - progress.get("reused", 0)) / max(progress["elapsed"], 0.1), 2
        )
    return {"id": job.id, "library_id": job.library_id, "status": job.status, **progress}
