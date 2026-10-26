from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from framewise.api.presenters import required
from framewise.curation.taste import (
    choose_model,
    ensure_current,
    examples,
    fit,
    invalidate,
    profile_info,
    rerank_all,
)
from framewise.db.models import Photo, Session, TasteLabel, TasteProfile, now

router = APIRouter(prefix="/api")


class Label(BaseModel):
    value: Literal[-1, 0, 1]


class Enable(BaseModel):
    enabled: bool


@router.get("/taste")
def info():
    with Session() as db:
        return profile_info(db)


@router.get("/photos/{photo_id}/taste")
def get_label(photo_id: str):
    with Session() as db:
        required(db, Photo, photo_id)
        label = db.get(TasteLabel, photo_id)
        return {"value": label.value if label else 0}


@router.patch("/photos/{photo_id}/taste")
def label(photo_id: str, body: Label):
    with Session.begin() as db:
        photo = required(db, Photo, photo_id)
        if photo.status != "ready":
            raise HTTPException(409, "Wait until this photo is ready")
        existing = db.get(TasteLabel, photo_id)
        if body.value == 0:
            if existing:
                db.delete(existing)
        elif existing:
            existing.value, existing.updated = body.value, now()
        else:
            db.add(TasteLabel(photo_id=photo_id, value=body.value))
        invalidate(db)
        rerank_all(db)
    return {"value": body.value}


@router.post("/taste/train")
def train():
    with Session.begin() as db:
        samples, _ = examples(db)
        # Do not mix incompatible embedding spaces. Pick the most labelled encoder.
        model = choose_model(samples)
        data = fit([s for s in samples if s["model_id"] == model])
        if not data:
            raise HTTPException(
                409,
                "Add 10 distinct likes and 10 distinct dislikes with matching cached embeddings first",
            )
        profile = db.get(TasteProfile, "local") or TasteProfile(id="local")
        profile.data, profile.enabled, profile.updated = data, False, now()
        db.add(profile)
        rerank_all(db)
        return profile_info(db)


@router.patch("/taste")
def enable(body: Enable):
    with Session.begin() as db:
        # Scan completion/startup normally handles this; refuse stale training on enable too.
        if ensure_current(db):
            rerank_all(db)
        profile = db.get(TasteProfile, "local")
        if body.enabled and (not profile or not profile.data.get("eligible")):
            raise HTTPException(
                409,
                "Train a profile with held-out balanced accuracy of 60% or more before applying it",
            )
        if profile:
            profile.enabled, profile.updated = body.enabled, now()
        rerank_all(db)
        return profile_info(db)


@router.delete("/taste")
def forget():
    with Session.begin() as db:
        db.query(TasteLabel).delete()
        invalidate(db)
        rerank_all(db)
    return {"status": "forgotten"}
