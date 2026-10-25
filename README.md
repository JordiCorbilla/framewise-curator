# Framewise

**Your best frames, discovered.** A local photography curation desk for Nikon NEF, JPEG and PNG.
FastAPI + SQLite, React 19 + TypeScript, real CPU aesthetic inference, read-only originals.

Scan a trip, inspect measured quality, compare conservative similarity groups, keep/exclude/rate,
and export a shortlist for Lightroom Classic. No uploads, cloud inference or telemetry.

## Start on Windows

Prerequisites: Python **3.11+**, Node **22.12+**, [uv](https://docs.astral.sh/uv/),
and [ExifTool](https://exiftool.org/). CPU works on AMD systems; no CUDA/NVIDIA dependency.

```powershell
winget install --id OliverBetz.ExifTool --exact
cd C:\repo\framewise-curator
.\scripts\setup.ps1 -WithAI
# ONLY with explicit approval for the one-time ~350 MB model download:
.\backend\.venv\Scripts\python.exe .\scripts\install_models.py --approve-download
.\scripts\start.ps1
```

Open **http://127.0.0.1:8765**. `start.ps1` opens the browser and runs the server hidden; logs are in
`.local`. `stop.ps1` stops that server. To install weights during setup after consent, use
`setup.ps1 -DownloadModels`. Plain `setup.ps1` installs classical scanning plus optional RAW fallback;
AI dependencies and weights are optional. Setup requires internet; subsequent operation is offline.

### First Nikon scan

Choose **Scan**, enter `C:\Desk\2026-10-18 Fotos NY`, leave **Include subfolders** checked, then
**Start local scan**. Photos appear in small batches. CPU inference is real; model absence/errors are
shown explicitly. Review **Curate**, adjust the 25% budget, inspect a photo, and press P to keep or X to
exclude. **Selected → Final selection → Export selection → Selected photographs · CSV** downloads
paths to the original NEFs. XMP writing is disabled; [Lightroom handoff](docs/lightroom.md) explains
the manual CSV workflow and catalogue limitations.

On this workstation the models have been installed with approval; see [validation](docs/validation.md)
for actual test/scan results. The app-data folder is `%LOCALAPPDATA%\Framewise`, separate from originals.
Reopening a collection uses the database/cache. **Check for changes** reuses unchanged scores.

### Development

```powershell
cd backend
uv sync --frozen --python 3.11 --extra dev --extra ai --extra raw
.\.venv\Scripts\python.exe -m uvicorn framewise.api.app:app --host 127.0.0.1 --port 8765
# Another terminal:
cd frontend
npm ci
npm run dev
```

Vite serves `http://127.0.0.1:5173` and proxies `/api`. To use a nonstandard ExifTool location, set
`$env:FRAMEWISE_EXIFTOOL = 'C:\tools\exiftool.exe'`. To isolate app data, set `FRAMEWISE_DATA_DIR`
before starting. Run a single backend process; do not use multiple uvicorn workers.

```powershell
cd backend
.\.venv\Scripts\pytest.exe -q
.\.venv\Scripts\ruff.exe check framewise tests ..\scripts
.\.venv\Scripts\ruff.exe format --check framewise tests ..\scripts
cd ..\frontend
npm run lint
npm run build
```

Tests use generated raster fixtures and mocked preview/RAW fallback contracts. They do not claim
camera-specific RAW compatibility. Real D850 integration is recorded separately; test your own camera's
NEF compression/preview flavour. A 1,000–5,000-file performance soak and aesthetic-quality evaluation
are still needed; do not treat functional tests or a valid model output as proof of artistic accuracy.

### Generated demo

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\make_demo.py
```

Scan the printed app-data `demo-generated` folder using a **DEMO — generated studies** name.
These geometric illustrations are project-owned and labelled in every image; no third-party
photographs or user NEFs are included in the repository. (The demo folder is the sole permitted
app-data input exception.)

## Scope and references

[Architecture](docs/architecture.md) · [Scoring and model provenance](docs/scoring.md) ·
[Lightroom](docs/lightroom.md) · [Validation](docs/validation.md)

Deferred: XMP writes, automatic RAW copying, richer critiques, personal preference learning,
genre-specific tuning, side-by-side comparison and sensor-level 100% RAW inspection.
Native folder picking is unavailable in the browser; manual path entry is provided.

UI inspiration: [Facet](https://github.com/ncoevoet/facet), [Selects](https://github.com/bihanikeshav/selects).
No code copied from either. The existing CC0 repository license is preserved; dependencies and
pretrained model checkpoints retain their own licenses. LAION's predictor and OpenAI CLIP sources
are MIT; verify checkpoint suitability for your use. No claim of competition/publication prediction.
