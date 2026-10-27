import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from framewise.curation.highlights import rebuild, waiting
from framewise.curation.ranking import recommend
from framewise.db.models import (
    Library,
    ModelRun,
    Photo,
    PhotoEmbedding,
    PhotoMetadata,
    PhotoMetrics,
    ScanJob,
    Session,
)
from framewise.imaging.acquisition import acquire, cache_paths, discover, identity, source_path
from framewise.imaging.exiftool import close_all
from framewise.scoring.aesthetic import analyzer
from framewise.scoring.metrics import classical

ACTIVE = {"queued", "running", "cancelling"}


class ScanManager:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan")
        self.lock = threading.Lock()
        self.cancel_events = {}

    def start(self, library_id):
        with self.lock, Session.begin() as db:
            from framewise.workers.models import installer

            if installer.state["status"] == "running":
                raise ValueError("Wait for model installation to finish before starting a scan.")
            if db.query(ScanJob).filter(ScanJob.status.in_(ACTIVE)).first():
                raise ValueError("A scan is already active. Cancel it or wait for completion.")
            analyzer.retry_failed()
            waiting(db, library_id)
            job = ScanJob(library_id=library_id, progress={"stage": "queued"})
            db.add(job)
            db.flush()
            job_id = job.id
            stop = threading.Event()
            self.cancel_events[job_id] = stop
        self.executor.submit(self.run, job_id, stop)
        return job_id

    def cancel(self, job_id):
        with self.lock, Session.begin() as db:
            job = db.get(ScanJob, job_id)
            if job and job.status in ACTIVE:
                job.status = "cancelling"
                if job_id in self.cancel_events:
                    self.cancel_events[job_id].set()

    def run(self, job_id, stop):
        started = time.monotonic()
        progress = {
            "stage": "discovering",
            "total": 0,
            "indexed": 0,
            "thumbnails": 0,
            "scored": 0,
            "failed": 0,
            "reused": 0,
            "processed": 0,
            "current": "",
            "elapsed": 0,
            "speed": 0,
            "percent": 0,
            "ai_available": analyzer.status()["status"] == "ready",
        }

        def update(status="running"):
            elapsed = time.monotonic() - started
            progress.update(
                elapsed=round(elapsed, 1),
                speed=round((progress["processed"] - progress["reused"]) / max(elapsed, 0.1), 2),
                percent=round(100 * progress["processed"] / max(progress["total"], 1), 1),
            )
            with Session.begin() as db:
                job = db.get(ScanJob, job_id)
                job.status = "cancelling" if status == "running" and stop.is_set() else status
                job.progress = dict(progress)

        try:
            update()
            with Session() as db:
                job = db.get(ScanJob, job_id)
                library = db.get(Library, job.library_id)
            root = Path(library.source)
            if not root.is_dir():
                raise ValueError("Source folder is unavailable. Reconnect the drive and resume the scan.")
            files = sorted(discover(root, library.config.get("recursive", True)))
            progress["total"] = len(files)
            model_id = analyzer.model_id() if analyzer.status()["status"] == "ready" else "classical-only-v1"
            work = []
            with Session.begin() as db:
                db.add(ModelRun(job_id=job_id, model_id=model_id, config=library.config))
                discovered = {str(path.relative_to(root)).casefold() for path in files}
                for existing in db.query(Photo).filter_by(library_id=library.id):
                    if existing.relative_path.casefold() not in discovered:
                        existing.status = "missing"
                        existing.error = "Source file no longer present; manual decisions are retained."
                        existing.recommendation = "unprocessed"
                for path in files:
                    relative = str(path.relative_to(root))
                    photo_id = str(uuid.uuid5(uuid.UUID(library.id), relative.casefold()))
                    photo = db.get(Photo, photo_id)
                    fingerprint = identity(path, model_id)
                    if photo is None:
                        photo = Photo(
                            id=photo_id, library_id=library.id, relative_path=relative, filename=path.name
                        )
                        db.add(photo)
                    if (
                        photo.status == "ready"
                        and photo.identity == fingerprint
                        and all(p.is_file() for p in cache_paths(library.id, photo_id))
                    ):
                        embedding = db.get(PhotoEmbedding, photo_id)
                        if model_id != "classical-only-v1" and (
                            embedding is None
                            or embedding.model_id != model_id
                            or embedding.identity != fingerprint
                        ):
                            work.append((photo_id, fingerprint, relative, True))
                            continue
                        progress["reused"] += 1
                        progress["thumbnails"] += 1
                        progress["processed"] += 1
                        metrics = db.get(PhotoMetrics, photo_id)
                        progress["scored"] += int(metrics is not None and metrics.aesthetic is not None)
                    else:
                        photo.status = "pending"
                        photo.score = None
                        photo.phash = None
                        photo.group_id, photo.group_rank = None, None
                        photo.recommendation = "unprocessed"
                        photo.selection_rank = None
                        db.query(PhotoMetrics).filter_by(photo_id=photo_id).delete()
                        db.query(PhotoMetadata).filter_by(photo_id=photo_id).delete()
                        db.query(PhotoEmbedding).filter_by(photo_id=photo_id).delete()
                        work.append((photo_id, fingerprint, relative, False))
                progress["indexed"] = len(files)
            progress["stage"] = "previews & analysis"
            update()

            def process(item):
                photo_id, fingerprint, relative, cached = item
                try:
                    if cached:
                        with Session() as db:
                            p = db.get(Photo, photo_id)
                            metrics = db.get(PhotoMetrics, photo_id)
                            metadata = db.get(PhotoMetadata, photo_id)
                            with Image.open(cache_paths(library.id, photo_id)[0]) as preview:
                                image = preview.convert("RGB")
                            return (
                                item,
                                (
                                    image,
                                    metadata.data,
                                    p.provenance,
                                    p.width,
                                    p.height,
                                    metrics.raw,
                                    metrics.calibrated,
                                    p.phash,
                                ),
                                None,
                            )
                    image, metadata, provenance, width, height = acquire(
                        source_path(root, relative), library.id, photo_id
                    )
                    raw, calibrated, phash = classical(image)
                    return item, (image, metadata, provenance, width, height, raw, calibrated, phash), None
                except Exception as exc:
                    return item, None, f"{type(exc).__name__}: {exc}"

            # Only two decoders and at most eight display-size images are resident at a time.
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="preview") as pool:
                for offset in range(0, len(work), 8):
                    if stop.is_set():
                        break
                    progress["current"] = Path(work[offset][2]).name
                    progress["stage"] = "previews & analysis"
                    update()
                    batch = list(pool.map(process, work[offset : offset + 8]))
                    good = [result for result in batch if result[1] is not None]
                    progress["stage"] = (
                        "aesthetic inference" if model_id != "classical-only-v1" else "classical analysis"
                    )
                    update()
                    scores = (
                        analyzer.analyze_with_embeddings([result[1][0] for result in good]) if good else []
                    )
                    score_map = {result[0][0]: score for result, score in zip(good, scores, strict=True)}
                    with Session.begin() as db:
                        for (photo_id, fingerprint, relative, cached), result, error in batch:
                            photo = db.get(Photo, photo_id)
                            progress["current"] = photo.filename
                            progress["processed"] += 1
                            if error:
                                photo.status, photo.error = "failed", error
                                progress["failed"] += 1
                                continue
                            image, metadata, provenance, width, height, raw, calibrated, phash = result
                            aesthetic, embedding = score_map[photo_id]
                            if cached:
                                # Backfill embeddings without changing the measured aesthetic score.
                                aesthetic = db.get(PhotoMetrics, photo_id).aesthetic
                            photo.status, photo.error, photo.identity = "ready", None, fingerprint
                            photo.provenance, photo.width, photo.height, photo.phash = (
                                provenance,
                                width,
                                height,
                                phash,
                            )
                            db.merge(PhotoMetadata(photo_id=photo_id, data=metadata))
                            db.merge(
                                PhotoMetrics(
                                    photo_id=photo_id,
                                    raw=raw,
                                    calibrated=calibrated,
                                    aesthetic=aesthetic,
                                    model_id=model_id if aesthetic is not None else None,
                                )
                            )
                            if embedding is not None:
                                db.merge(
                                    PhotoEmbedding(
                                        photo_id=photo_id,
                                        model_id=model_id,
                                        identity=fingerprint,
                                        vector=embedding.tobytes(),
                                        provenance=("cached display JPEG" if cached else provenance),
                                    )
                                )
                            # Retry missing inference on resume, rather than caching it as scored.
                            if aesthetic is None and model_id != "classical-only-v1":
                                photo.identity = identity(source_path(root, relative), "classical-only-v1")
                            progress["thumbnails"] += 1
                            progress["scored"] += int(aesthetic is not None)
                            image.close()
                        db.flush()
                        recommend(db, db.get(Library, library.id))
                    progress["ai_error"] = analyzer.error
                    progress["stage"] = "previews & analysis"
                    update()
            with Session.begin() as db:
                recommend(db, db.get(Library, library.id))
            progress["stage"] = "cancelled" if stop.is_set() else "complete"
            update("cancelled" if stop.is_set() else "complete")
            with Session.begin() as db:
                rebuild(db, db.get(Library, library.id))
                from framewise.curation.taste import ensure_current, rerank_all

                if ensure_current(db):
                    rerank_all(db)
        except Exception as exc:
            progress.update(stage="failed", error=f"{type(exc).__name__}: {exc}")
            update("failed")
        finally:
            close_all()
            self.cancel_events.pop(job_id, None)


manager = ScanManager()
