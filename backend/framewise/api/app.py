import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, case, or_
from sqlalchemy.dialects.sqlite import insert
from starlette.middleware.trustedhost import TrustedHostMiddleware

from framewise.api.collections import router as collections_router
from framewise.api.highlights import router as highlights_router
from framewise.api.presenters import (
    job_info,
    library_info,
    photo_query,
    required,
    selected_expression,
    serialize,
)
from framewise.api.schemas import BudgetUpdate, DecisionUpdate, LibraryCreate, WeightUpdate
from framewise.api.taste import router as taste_router
from framewise.core.config import DATA, DEFAULT_WEIGHTS, exiftool_path
from framewise.curation.highlights import rebuild
from framewise.curation.ranking import recommend
from framewise.db.models import (
    ExportJob,
    HighlightRanking,
    HighlightState,
    Library,
    Photo,
    PhotoDecision,
    PhotoMetadata,
    PhotoMetrics,
    ScanJob,
    Session,
    initialize,
)
from framewise.export.csv_export import make_csv
from framewise.imaging.acquisition import cache_paths, source_path
from framewise.scoring.aesthetic import analyzer
from framewise.workers.scan import ACTIVE, manager

ORIGINS = [f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (5173, 8765)]


@asynccontextmanager
async def lifespan(_):
    initialize()
    yield
    for stop in list(manager.cancel_events.values()):
        stop.set()


app = FastAPI(title="Framewise", version="0.1.0", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def local_origin(request: Request, call_next):
    if request.method in ("POST", "PATCH", "DELETE", "PUT"):
        if request.headers.get("origin") and request.headers["origin"] not in ORIGINS:
            return Response("Untrusted origin", status_code=403)
        if not request.headers.get("content-type", "").startswith("application/json"):
            return Response("JSON content type required", status_code=415)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "process_id": os.getpid(),
        "data_directory": str(DATA),
        "exiftool": exiftool_path(),
        "model": analyzer.status(),
    }


@app.get("/api/libraries")
def libraries():
    with Session() as db:
        return [library_info(db, lib) for lib in db.query(Library).order_by(Library.created.desc())]


@app.post("/api/libraries")
def create_library(body: LibraryCreate):
    source = Path(body.source).expanduser().resolve()
    if not source.is_dir():
        raise HTTPException(422, "Folder does not exist or is not accessible")
    # Cache must never become part of the input collection.
    if source != DATA / "demo-generated" and (
        source == DATA or source in DATA.parents or DATA in source.parents
    ):
        raise HTTPException(422, "Choose a source folder outside Framewise application data")
    with Session.begin() as db:
        existing = db.query(Library).filter_by(source=str(source)).first()
        if existing:
            return library_info(db, existing)
        lib = Library(
            source=str(source),
            name=body.name.strip() or source.name,
            config={"weights": DEFAULT_WEIGHTS, "recursive": body.recursive},
        )
        db.add(lib)
        db.flush()
        return library_info(db, lib)


@app.get("/api/libraries/{library_id}")
def library_detail(library_id: str):
    with Session() as db:
        return library_info(db, required(db, Library, library_id))


@app.post("/api/libraries/{library_id}/scan")
def start_scan(library_id: str):
    with Session() as db:
        required(db, Library, library_id)
    try:
        return {"id": manager.start(library_id)}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with Session() as db:
        return job_info(required(db, ScanJob, job_id))


@app.post("/api/jobs/{job_id}/cancel")
def cancel_scan(job_id: str):
    with Session() as db:
        required(db, ScanJob, job_id)
    manager.cancel(job_id)
    return {"status": "cancellation requested"}


@app.post("/api/jobs/{job_id}/resume")
def resume_scan(job_id: str):
    with Session() as db:
        job = required(db, ScanJob, job_id)
        library_id = job.library_id
    return start_scan(library_id)


@app.get("/api/jobs/{job_id}/events")
async def events(job_id: str, request: Request):
    get_job(job_id)

    async def stream():
        while not await request.is_disconnected():
            data = await asyncio.to_thread(get_job, job_id)
            yield f"data: {json.dumps(data)}\n\n"
            if data["status"] not in ACTIVE:
                break
            await asyncio.sleep(0.75)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/libraries/{library_id}/photos")
def photos(
    library_id: str,
    filter: str = "all",
    sort: str = "score",
    page: int = Query(1, ge=1),
    limit: int = Query(48, ge=1, le=100),
    group_id: str | None = None,
):
    with Session() as db:
        lib = required(db, Library, library_id)
        query = photo_query(db, library_id)
        filters = {
            "all": True,
            "ai": Photo.recommendation == "pick",
            "manual": PhotoDecision.decision == "keep",
            "selected": selected_expression(),
            "lightroom": selected_expression(),
            "flickr": and_(
                HighlightState.status == "ready", Photo.status == "ready", HighlightRanking.flickr
            ),
            "competition": and_(
                HighlightState.status == "ready",
                Photo.status == "ready",
                HighlightRanking.competition_rank.is_not(None),
            ),
            "competition_alternatives": and_(
                HighlightState.status == "ready",
                Photo.status == "ready",
                HighlightRanking.candidate_rank.is_not(None),
                HighlightRanking.competition_rank.is_(None),
            ),
            "review": or_(
                PhotoDecision.decision == "review",
                and_(
                    or_(PhotoDecision.decision.is_(None), PhotoDecision.decision == "auto"),
                    Photo.recommendation == "review",
                ),
            ),
            "low": or_(
                PhotoDecision.decision == "reject",
                and_(
                    or_(PhotoDecision.decision.is_(None), PhotoDecision.decision == "auto"),
                    Photo.recommendation == "low",
                ),
            ),
            "similar": Photo.group_id.is_not(None),
            "failed": Photo.status != "ready",
        }
        if filter not in filters:
            raise HTTPException(422, "Unknown filter")
        query = query.filter(filters[filter])
        if group_id:
            query = query.filter(Photo.group_id == group_id)
        orders = {
            "score": Photo.score.desc(),
            "filename": Photo.filename.asc(),
            "date": PhotoMetadata.data["DateTimeOriginal"].as_string().asc(),
            "sharpness": PhotoMetrics.calibrated["sharpness"].as_float().desc(),
            "aesthetic": PhotoMetrics.aesthetic.desc(),
            "highlights": HighlightRanking.data["score"].as_float().desc(),
            "competition": HighlightRanking.competition_rank.asc(),
        }
        if sort not in orders:
            raise HTTPException(422, "Unknown sort")
        total = query.count()
        rows = (
            query.order_by(orders[sort], Photo.filename, Photo.id)
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        return {
            "items": [serialize(row, lib.source) for row in rows],
            "total": total,
            "page": page,
            "limit": limit,
        }


@app.get("/api/photos/{photo_id}")
def photo_detail(photo_id: str):
    with Session() as db:
        photo = required(db, Photo, photo_id)
        lib = required(db, Library, photo.library_id)
        row = photo_query(db, lib.id).filter(Photo.id == photo_id).one()
        return serialize(row, lib.source)


@app.get("/api/photos/{photo_id}/{kind}")
def image(photo_id: str, kind: str):
    if kind not in ("thumbnail", "preview"):
        raise HTTPException(404)
    with Session() as db:
        photo = required(db, Photo, photo_id)
        paths = cache_paths(photo.library_id, photo.id)
        path = paths[0 if kind == "preview" else 1]
        if not path.is_file():
            raise HTTPException(404, "Preview not generated yet")
        return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})


@app.patch("/api/photos/{photo_id}/decision")
def decision(photo_id: str, body: DecisionUpdate):
    with Session.begin() as db:
        required(db, Photo, photo_id)
        changes = body.model_dump(exclude_none=True)
        if changes:
            statement = insert(PhotoDecision).values(photo_id=photo_id, **changes)
            db.execute(statement.on_conflict_do_update(index_elements=["photo_id"], set_=changes))
            db.flush()
            photo = db.get(Photo, photo_id)
            rebuild(db, db.get(Library, photo.library_id))
    return photo_detail(photo_id)


@app.patch("/api/libraries/{library_id}/budget")
def budget(library_id: str, body: BudgetUpdate):
    with Session.begin() as db:
        lib = required(db, Library, library_id)
        lib.budget = body.budget
        recommend(db, lib, group=False)
        rebuild(db, lib)
    return library_detail(library_id)


@app.patch("/api/libraries/{library_id}/weights")
def weights(library_id: str, body: WeightUpdate):
    with Session.begin() as db:
        lib = required(db, Library, library_id)
        lib.config = {**lib.config, "weights": body.model_dump()}
        recommend(db, lib)
        rebuild(db, lib)
    return library_detail(library_id)


@app.get("/api/models")
def models():
    return analyzer.status()


@app.get("/api/libraries/{library_id}/export/{filename}")
def export_csv(library_id: str, filename: str):
    kinds = {
        "lightroom_picks.csv": "lightroom",
        "flickr_standouts.csv": "flickr",
        "competition_top3.csv": "competition",
        "competition_alternatives.csv": "competition_alternatives",
    }
    if filename not in ("all_photos.csv", "selected_photos.csv", *kinds):
        raise HTTPException(404)
    with Session.begin() as db:
        lib = required(db, Library, library_id)
        query = photo_query(db, library_id)
        if filename in ("selected_photos.csv", "lightroom_picks.csv"):
            query = query.filter(selected_expression())
        elif filename in kinds:
            state = db.get(HighlightState, library_id)
            if not state or state.status != "ready":
                raise HTTPException(409, "Complete the scan before exporting Highlights")
            query = query.filter(Photo.status == "ready")
            if filename == "flickr_standouts.csv":
                query = query.filter(HighlightRanking.flickr)
            elif filename == "competition_top3.csv":
                query = query.filter(HighlightRanking.competition_rank.is_not(None))
            else:
                query = query.filter(
                    HighlightRanking.candidate_rank.is_not(None), HighlightRanking.competition_rank.is_(None)
                )
        order = (
            HighlightRanking.competition_rank
            if filename == "competition_top3.csv"
            else HighlightRanking.candidate_rank
            if filename == "competition_alternatives.csv"
            else HighlightRanking.data["flickr_rank"].as_integer()
            if filename == "flickr_standouts.csv"
            else Photo.selection_rank
        )
        rows = query.order_by(case((order.is_(None), 1), else_=0), order, Photo.id).all()
        data = make_csv([serialize(row, lib.source) for row in rows], kinds.get(filename))
        db.add(ExportJob(library_id=library_id, kind=filename, count=len(rows)))
    return Response(
        data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/libraries/{library_id}/xmp/preview")
def xmp_preview(library_id: str):
    with Session() as db:
        lib = required(db, Library, library_id)
        conflicts = []
        for p in db.query(Photo).filter_by(library_id=library_id):
            source = source_path(lib.source, p.relative_path)
            sidecars = [source.with_suffix(".xmp"), source.with_suffix(".XMP")]
            conflicts.extend(str(path) for path in sidecars if path.exists())
        return {
            "enabled": False,
            "reason": "Sidecar writing is disabled until Lightroom round-trip validation. "
            "Use CSV export. Existing sidecars and all originals remain untouched.",
            "conflicts": sorted(set(conflicts)),
        }


@app.post("/api/libraries/{library_id}/xmp/confirm")
def xmp_confirm(library_id: str):
    raise HTTPException(
        409, "XMP writing is disabled: Lightroom metadata preservation has not been validated"
    )


app.include_router(highlights_router)
app.include_router(collections_router)
app.include_router(taste_router)

frontend = Path(__file__).resolve().parents[3] / "frontend" / "dist"
if frontend.is_dir():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
