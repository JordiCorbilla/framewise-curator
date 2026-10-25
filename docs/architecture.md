# Architecture

One FastAPI process bound to 127.0.0.1 serves the API and built React application. Vite is only needed
for development. SQLAlchemy + SQLite WAL persist all decisions outside the checkout. No Redis,
Docker, telemetry, cloud or inference API is involved.

The layers are deliberately independent:

- `imaging/acquisition.py`: extension discovery, validated source resolution, read-only ExifTool EXIF
  and embedded JPEG extraction, orientation, optional LibRaw fallback, previews and thumbnails.
- `scoring/metrics.py`: deterministic raw and calibrated technical measurements.
- `scoring/aesthetic.py`: `PhotoAnalyzer` contract, optional batched offline-only PyTorch inference.
- `curation/ranking.py`: separate aggregation, conservative similarity groups and budget decisions.
- `workers/scan.py`: one background job, two acquisition workers, eight-image batches, incremental
  commits, checkpoint reuse, cancellation at the next batch boundary and restart recovery.
- `api/`: validated local API, paginated gallery, SSE progress, decision/configuration mutations.
- `export/`: UTF-8 BOM CSV generation. XMP writing is explicitly disabled.

Tables: Library, ScanJob, Photo, PhotoMetadata, PhotoMetrics, ModelRun, SimilarityGroup,
PhotoDecision, ExportJob. Photo IDs are UUID5 of library ID and case-folded relative filename;
manual decisions have their own table and do not change when recommendations are regenerated.

## Cache and resume

Default Windows data: `%LOCALAPPDATA%\Framewise` (platformdirs on other OSes). Override with
`FRAMEWISE_DATA_DIR` **before starting**. Each library has its own preview cache. The source identity
includes resolved path, size, nanosecond mtime, processing version and exact model-manifest identity.
Ranking weights do not invalidate measured features; weight changes rerank immediately. Preview-cache
loss triggers regeneration. A cancelled/interrupted scan reindexes but reuses valid measured results.
Failed files retry on resume. Reopening a library only reads SQLite and cached previews.

Maximum resident acquisition work is two decoders and eight display-sized images per batch. Full RAW
development is only a fallback. Models load once in the single inference worker; CPU threads are
capped at four. SQLite transactions publish every batch, so the browser can start browsing early.
Discovery/indexing retains paths, not images. Gallery queries paginate in SQL and images load lazily.

## Local security and privacy

No API accepts a path for image serving: only registered photo IDs resolve cached files. Source paths
are resolved under the library root; symlink escapes are excluded. Mutations require JSON and reject
foreign browser Origins; TrustedHost protection reduces DNS rebinding risk. Bind to localhost only.
This is a single-user local app, without network authentication; do not expose it on a LAN/public host.
No write operation targets a source photo or source folder. Model downloads exist only in the explicit
consent installer, not in the runtime. All UI assets and typography are local.

## Operational limits

Only one scan at a time. Pause takes effect after the current batch finishes. Source changes during a
scan should be followed by another scan. Similarity is deliberately conservative and bounded to the
last 48 group anchors in capture-time order; this may miss duplicates separated by long time intervals.
Large collections have not received a measured 1,000–5,000-file soak test unless recorded in validation.md.
No multi-process uvicorn workers: each would have an independent scan coordinator.
