"""Collection management. Deletion can touch only the registered preview cache."""

import shutil
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_

from framewise.api.presenters import library_info, required
from framewise.core.config import CACHE
from framewise.db.models import (
    ExportJob,
    HighlightDecision,
    HighlightFeedback,
    HighlightRanking,
    HighlightState,
    Library,
    ModelRun,
    Photo,
    PhotoDecision,
    PhotoEmbedding,
    PhotoMetadata,
    PhotoMetrics,
    PhotoRawSource,
    ScanJob,
    Session,
    SimilarityGroup,
    TasteLabel,
    TasteProfile,
)
from framewise.workers.scan import ACTIVE, manager

router = APIRouter(prefix="/api")


class Rename(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class Remove(BaseModel):
    confirm_name: str


@router.patch("/libraries/{library_id}")
def rename(library_id: str, body: Rename):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Enter a collection title")
    with Session.begin() as db:
        library = required(db, Library, library_id)
        library.name = name
        db.flush()
        return library_info(db, library)


@router.delete("/libraries/{library_id}")
def remove(library_id: str, body: Remove):
    # Same lock as scan submission: do not delete a collection a worker can still write.
    with manager.lock, Session.begin() as db:
        library = required(db, Library, library_id)
        if body.confirm_name != library.name:
            raise HTTPException(422, "Type the exact collection title to confirm removal")
        if db.query(ScanJob).filter(ScanJob.library_id == library_id, ScanJob.status.in_(ACTIVE)).first():
            raise HTTPException(
                409, "Cancel the scan and wait for it to stop before removing this collection"
            )
        try:
            valid_id = str(uuid.UUID(library_id)) == library_id
        except ValueError:
            valid_id = False
        if not valid_id:
            raise HTTPException(409, "Invalid collection cache identity")
        cache_root = CACHE.resolve()
        cache = CACHE / library_id
        # Never follow a symlink/junction to source media or delete any computed external path.
        reparse = cache.exists() and bool(getattr(cache.lstat(), "st_file_attributes", 0) & 0x400)
        if cache.is_symlink() or reparse or cache.resolve().parent != cache_root:
            raise HTTPException(409, "Unsafe preview cache path; collection was not removed")
        if cache.exists():
            try:
                shutil.rmtree(cache)
            except OSError as exc:
                raise HTTPException(
                    409, "Preview cache is in use. Close open previews and retry removal"
                ) from exc
        photo_ids = db.query(Photo.id).filter_by(library_id=library_id)
        jobs = db.query(ScanJob.id).filter_by(library_id=library_id)
        for table in (HighlightFeedback, HighlightRanking, HighlightState, ExportJob, SimilarityGroup):
            db.query(table).filter(table.library_id == library_id).delete(synchronize_session=False)
        db.query(PhotoRawSource).filter(
            or_(PhotoRawSource.photo_id.in_(photo_ids), PhotoRawSource.raw_photo_id.in_(photo_ids))
        ).delete(synchronize_session=False)
        for table in (
            HighlightDecision,
            TasteLabel,
            PhotoEmbedding,
            PhotoDecision,
            PhotoMetadata,
            PhotoMetrics,
        ):
            db.query(table).filter(table.photo_id.in_(photo_ids)).delete(synchronize_session=False)
        db.query(ModelRun).filter(ModelRun.job_id.in_(jobs)).delete(synchronize_session=False)
        db.query(ScanJob).filter_by(library_id=library_id).delete(synchronize_session=False)
        db.query(Photo).filter_by(library_id=library_id).delete(synchronize_session=False)
        db.delete(library)
        # The global learner may contain contributions from these photos. Invalidate it,
        # including its vector, and rerank every remaining collection without it.
        profile = db.get(TasteProfile, "local")
        if profile:
            profile.data, profile.enabled = {}, False
        db.flush()
        from framewise.curation.highlights import rebuild
        from framewise.curation.ranking import recommend

        for other in db.query(Library):
            recommend(db, other)
            rebuild(db, other)
    return {"removed": library_id, "originals_untouched": True}
