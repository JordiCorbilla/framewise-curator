import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, case, func, or_
from sqlalchemy.dialects.sqlite import insert
from starlette.middleware.trustedhost import TrustedHostMiddleware

from framewise.api.schemas import BudgetUpdate, DecisionUpdate, LibraryCreate, WeightUpdate
from framewise.core.config import DATA, DEFAULT_WEIGHTS, exiftool_path
from framewise.curation.ranking import recommend
from framewise.db.models import (
    ExportJob,
    Library,
    Photo,
    PhotoDecision,
    PhotoMetadata,
    PhotoMetrics,
    ScanJob,
    Session,
    SimilarityGroup,
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
    allow_methods=["GET", "POST", "PATCH"],
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


def required(db, cls, object_id):
    item = db.get(cls, object_id)
    if item is None:
        raise HTTPException(404, "Not found")
    return item


def photo_query(db, library_id):
    return (
        db.query(Photo, PhotoMetrics, PhotoDecision, PhotoMetadata, SimilarityGroup)
        .outerjoin(PhotoMetrics, PhotoMetrics.photo_id == Photo.id)
        .outerjoin(PhotoDecision, PhotoDecision.photo_id == Photo.id)
        .outerjoin(PhotoMetadata, PhotoMetadata.photo_id == Photo.id)
        .outerjoin(SimilarityGroup, SimilarityGroup.id == Photo.group_id)
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
    p, metrics, decision, metadata, group = row
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
    }


def job_info(job):
    progress = dict(job.progress)
    if "elapsed" in progress:
        progress["speed"] = round(
            (progress.get("processed", 0) - progress.get("reused", 0)) / max(progress["elapsed"], 0.1), 2
        )
    return {"id": job.id, "library_id": job.library_id, "status": job.status, **progress}


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
    return photo_detail(photo_id)


@app.patch("/api/libraries/{library_id}/budget")
def budget(library_id: str, body: BudgetUpdate):
    with Session.begin() as db:
        lib = required(db, Library, library_id)
        lib.budget = body.budget
        recommend(db, lib, group=False)
    return library_detail(library_id)


@app.patch("/api/libraries/{library_id}/weights")
def weights(library_id: str, body: WeightUpdate):
    with Session.begin() as db:
        lib = required(db, Library, library_id)
        lib.config = {**lib.config, "weights": body.model_dump()}
        recommend(db, lib)
    return library_detail(library_id)


@app.get("/api/models")
def models():
    return analyzer.status()


@app.get("/api/libraries/{library_id}/export/{filename}")
def export_csv(library_id: str, filename: str):
    if filename not in ("all_photos.csv", "selected_photos.csv"):
        raise HTTPException(404)
    with Session.begin() as db:
        lib = required(db, Library, library_id)
        query = photo_query(db, library_id)
        if filename == "selected_photos.csv":
            query = query.filter(selected_expression())
        rows = query.order_by(case((Photo.selection_rank.is_(None), 1), else_=0), Photo.selection_rank).all()
        data = make_csv([serialize(row, lib.source) for row in rows])
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


frontend = Path(__file__).resolve().parents[3] / "frontend" / "dist"
if frontend.is_dir():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
