import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, LargeBinary, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from framewise.core.config import DATA, DEFAULT_WEIGHTS


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


class Library(Base):
    __tablename__ = "libraries"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    name: Mapped[str]
    source: Mapped[str] = mapped_column(unique=True)
    created: Mapped[str] = mapped_column(default=now)
    budget: Mapped[int] = mapped_column(default=25)
    config: Mapped[dict] = mapped_column(
        JSON, default=lambda: {"weights": DEFAULT_WEIGHTS, "recursive": True}
    )


class ScanJob(Base):
    __tablename__ = "scan_jobs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id"), index=True)
    status: Mapped[str] = mapped_column(default="queued")
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[str] = mapped_column(default=now)


class Photo(Base):
    __tablename__ = "photos"
    id: Mapped[str] = mapped_column(primary_key=True)
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id"), index=True)
    relative_path: Mapped[str]
    filename: Mapped[str]
    identity: Mapped[str] = mapped_column(default="")
    status: Mapped[str] = mapped_column(default="pending")
    error: Mapped[str | None]
    provenance: Mapped[str | None]
    width: Mapped[int] = mapped_column(default=0)
    height: Mapped[int] = mapped_column(default=0)
    phash: Mapped[str | None]
    group_id: Mapped[str | None] = mapped_column(index=True)
    group_rank: Mapped[int | None]
    score: Mapped[float | None]
    recommendation: Mapped[str] = mapped_column(default="unprocessed")
    selection_rank: Mapped[int | None]


class PhotoMetadata(Base):
    __tablename__ = "photo_metadata"
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class PhotoMetrics(Base):
    __tablename__ = "photo_metrics"
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    raw: Mapped[dict] = mapped_column(JSON)
    calibrated: Mapped[dict] = mapped_column(JSON)
    aesthetic: Mapped[float | None]
    model_id: Mapped[str | None]


class PhotoDecision(Base):
    __tablename__ = "photo_decisions"
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    decision: Mapped[str] = mapped_column(default="auto")
    stars: Mapped[int] = mapped_column(default=0)


class SimilarityGroup(Base):
    __tablename__ = "similarity_groups"
    id: Mapped[str] = mapped_column(primary_key=True)
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id"), index=True)
    count: Mapped[int]
    protected: Mapped[bool] = mapped_column(default=False)
    reason: Mapped[str]


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("scan_jobs.id"))
    model_id: Mapped[str]
    config: Mapped[dict] = mapped_column(JSON)
    created: Mapped[str] = mapped_column(default=now)


class ExportJob(Base):
    __tablename__ = "export_jobs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id"))
    kind: Mapped[str]
    count: Mapped[int]
    created: Mapped[str] = mapped_column(default=now)


class PhotoEmbedding(Base):
    __tablename__ = "photo_embeddings"
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    model_id: Mapped[str]
    identity: Mapped[str]
    vector: Mapped[bytes] = mapped_column(LargeBinary)
    provenance: Mapped[str]


class PhotoRawSource(Base):
    __tablename__ = "photo_raw_sources"
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    raw_photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), index=True)
    method: Mapped[str]


class HighlightState(Base):
    __tablename__ = "highlight_states"
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id"), primary_key=True)
    status: Mapped[str] = mapped_column(default="waiting")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    updated: Mapped[str] = mapped_column(default=now)


class HighlightRanking(Base):
    __tablename__ = "highlight_rankings"
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id"), index=True)
    flickr: Mapped[bool] = mapped_column(default=False)
    competition_rank: Mapped[int | None]
    candidate_rank: Mapped[int | None]
    data: Mapped[dict] = mapped_column(JSON)


class HighlightDecision(Base):
    __tablename__ = "highlight_decisions"
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), primary_key=True)
    flickr: Mapped[str] = mapped_column(default="auto")
    competition: Mapped[str] = mapped_column(default="auto")
    competition_rank: Mapped[int | None]


class HighlightFeedback(Base):
    __tablename__ = "highlight_feedback"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id"), index=True)
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"))
    action: Mapped[str]
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
    context: Mapped[dict] = mapped_column(JSON)
    created: Mapped[str] = mapped_column(default=now)


engine = create_engine(f"sqlite:///{DATA / 'framewise.sqlite3'}", connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def sqlite_options(connection, _):
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=10000")


Session = sessionmaker(engine, expire_on_commit=False)


def initialize():
    Base.metadata.create_all(engine)
    with Session.begin() as db:
        for job in db.query(ScanJob).filter(ScanJob.status.in_(["running", "queued", "cancelling"])):
            job.status = "interrupted"
        db.flush()
        from framewise.curation.highlights import rebuild

        for library in db.query(Library):
            rebuild(db, library)
