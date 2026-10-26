"""Persistence adapter for the pure portfolio ranker; manual feedback is never regenerated."""

import hashlib
import json

import numpy as np

from framewise.curation.standouts import DEFAULT_CONFIG, VERSION, Frame, rank
from framewise.db.models import (
    HighlightDecision,
    HighlightRanking,
    HighlightState,
    Photo,
    PhotoDecision,
    PhotoEmbedding,
    PhotoMetrics,
    ScanJob,
    SimilarityGroup,
    TasteProfile,
    now,
)
from framewise.imaging.raw_pairs import associate


def state_for(db, library_id):
    state = db.get(HighlightState, library_id)
    if state is None:
        state = HighlightState(library_id=library_id, config=dict(DEFAULT_CONFIG), summary={})
        db.add(state)
        db.flush()
    return state


def waiting(db, library_id):
    state = state_for(db, library_id)
    state.status = "waiting"
    state.summary = {
        **state.summary,
        "reason": "Finish or resume the scan before exceptional recommendations are final.",
    }


def rebuild(db, library):
    state = state_for(db, library.id)
    latest = db.query(ScanJob).filter_by(library_id=library.id).order_by(ScanJob.created.desc()).first()
    if (
        latest is None
        or latest.status != "complete"
        or db.query(Photo).filter_by(library_id=library.id, status="pending").first()
    ):
        waiting(db, library.id)
        return state
    cfg = {**DEFAULT_CONFIG, **state.config}
    from framewise.curation.taste import affinity

    profile = db.get(TasteProfile, "local")
    cfg["taste_version"] = profile.data.get("version") if profile and profile.enabled else None
    raw_sources = associate(db, library.id)
    config_id = hashlib.sha256(json.dumps({"version": VERSION, **cfg}, sort_keys=True).encode()).hexdigest()[
        :16
    ]
    rows = (
        db.query(Photo, PhotoMetrics, PhotoDecision, PhotoEmbedding, HighlightDecision, SimilarityGroup)
        .join(PhotoMetrics, PhotoMetrics.photo_id == Photo.id)
        .outerjoin(PhotoDecision, PhotoDecision.photo_id == Photo.id)
        .outerjoin(PhotoEmbedding, PhotoEmbedding.photo_id == Photo.id)
        .outerjoin(HighlightDecision, HighlightDecision.photo_id == Photo.id)
        .outerjoin(SimilarityGroup, SimilarityGroup.id == Photo.group_id)
        .filter(Photo.library_id == library.id, Photo.status == "ready")
        .all()
    )
    frames = []
    for p, metrics, lightroom, embedding, manual, group in rows:
        vector = None
        if embedding and embedding.model_id == metrics.model_id and embedding.identity == p.identity:
            candidate = np.frombuffer(embedding.vector, dtype=np.float32)
            if candidate.shape == (512,) and np.isfinite(candidate).all() and np.linalg.norm(candidate) > 0:
                vector = candidate / np.linalg.norm(candidate)
        decision = lightroom.decision if lightroom else "auto"
        selected = decision == "keep" or (decision == "auto" and p.recommendation == "pick")
        frames.append(
            Frame(
                id=p.id,
                filename=p.filename,
                aesthetic=metrics.aesthetic,
                sharpness=metrics.calibrated["sharpness"],
                exposure=metrics.calibrated["exposure"],
                lightroom=selected,
                group=p.group_id,
                phash=p.phash,
                aspect=p.width / max(p.height, 1),
                embedding=vector,
                model_id=metrics.model_id,
                flickr=manual.flickr if manual else "auto",
                competition=manual.competition if manual else "auto",
                manual_rank=manual.competition_rank if manual else None,
                clipping=metrics.raw.get("highlight_clipping", 0),
                focus=metrics.calibrated.get("focus_risk", ""),
                protected=group.protected if group else False,
                raw_capture=raw_sources.get(p.id, p.id),
                data={
                    "embedding_provenance": embedding.provenance if vector is not None else None,
                    "taste_affinity": affinity(profile, vector, metrics.model_id),
                    "taste_version": cfg["taste_version"],
                },
            )
        )
    results, summary = rank(frames, cfg)
    db.query(HighlightRanking).filter_by(library_id=library.id).delete(synchronize_session="fetch")
    for photo_id, data in results.items():
        data["configuration_version"] = config_id
        db.add(
            HighlightRanking(
                photo_id=photo_id,
                library_id=library.id,
                flickr=data["flickr"],
                competition_rank=data["competition_rank"],
                candidate_rank=data["candidate_rank"],
                data=data,
            )
        )
    state.status, state.config, state.updated = "ready", cfg, now()
    embedded = sum(f.embedding is not None for f in frames)
    state.summary = {
        **summary,
        "flickr_count": len(summary["flickr"]),
        "finalist_count": len(summary["finalists"]),
        "analysed": len(frames),
        "embeddings": embedded,
        "embedding_missing": len(frames) - embedded,
        "version": VERSION,
        "configuration_version": config_id,
        "reason": None,
        "forced": cfg["force_three"],
    }
    return state
