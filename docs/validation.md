# Initial-use validation — 25 October 2026

**Milestone 1: validated on the supplied Nikon D850 collection.** This is functional evidence, not an
evaluation of aesthetic ranking accuracy. XMP writes and richer intelligence remain deferred.

## Executed checks

- `backend/.venv/Scripts/pytest.exe -q`: **27 passed**, one upstream Starlette/AnyIO deprecation warning.
  Covers discovery/extensions, EXIF, Unicode Windows filenames, largest embedded-preview fallback,
  orientation, optional LibRaw contract, corrupt NEFs, JPEG caching, deterministic metrics, grouping,
  bracket protection, stable ranking, manual persistence, cancellation/resume, changed/missing sources,
  CSV quoting/Unicode, local request security, pagination/SSE, and explicit missing-model states.
- Ruff lint and formatting checks pass on backend, tests and scripts.
- Frontend ESLint passes with zero warnings. TypeScript checking and the Vite production build pass.
- Production npm dependency audit reports zero vulnerabilities (development dependencies excluded).
- Windows setup/start/stop scripts exercised locally. Backend binds to 127.0.0.1:8765 and serves built UI.
- Browser review exercised progressive gallery updates, pause, real NEF resumption, lightbox,
  P/X/U/1–5/arrow/Escape shortcuts, enlarged preview, related frames, final selection and export controls.
  Responsive inspection includes a 390px embedded viewport and a 1440px desktop viewport; compact
  navigation has explicit accessible names. Photographs are never embedded in this repository.

## Real source and model evidence

Source: `C:\Desk\2026-10-18 Fotos NY` — **381 NEFs**, 20,299,433,061 source bytes.
All **381 previews and 381 aesthetic scores completed; zero file failures**. Every score used
`embedded JPEG (JpgFromRaw)`. D850 sample preview: 8256 × 5504 before display-cache downsampling.
There is no general claim about other Nikon models or compression variants.

At the default weights and 25% budget: **96 selected**, **115 similarity groups**, including
**37 protected/uncertain groups**. These groups have not been manually audited for artistic correctness.
The browser-test frame was restored to its original Auto decision and zero stars after testing.

The real scan was paused after 120 files. Resuming reused those 120 results and processed the other
261 files in **360.3 seconds**, including model loading, after adding persistent ExifTool workers.
That is approximately **0.72 newly processed photos/second** for this run. A later unchanged-folder
check reused **all 381 results in 1.7 seconds**, without rescoring. These are observed local results,
not promised timings. Gallery API requests after completion: 12 requests, median **56.48ms**, maximum
**76.61ms** in the recorded validation run. Request timing excludes browser image downloads.

Observed worker working-set samples were approximately 1.2–1.9 GB with the CPU model loaded; these are
samples, not a measured peak or a full memory soak. Hardware: Intel Core i7-10750H CPU; Python 3.11.6,
Node 22.17.1, ExifTool 13.59, PyTorch 2.9.0, OpenCLIP 3.2.0. **No GPU/CUDA inference was used.**
AMD GPU acceleration was not tested and is not required by the implementation.

`scripts/validate_model.py` blocked socket connections and compared real inference with the official
OpenCLIP OpenAI loader/preprocessing. Repeated batch outputs matched; single and reference score on
the test frame were both **7.444772720336914**, absolute difference **0.0**. This validates compatibility
and offline operation, not model quality. All weights are optional at runtime; unavailable scores stay null.

Pinned checkpoints:

- OpenAI ViT-B/32 SHA256: `40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af`
- LAION V1 commit: `6d122adad522ab246644d9dc1c6d7a3810ee255f`
- LAION B/32 head SHA256: `c7b14cead230694acc7b9447974d3cad78003c72da032e402a303b6c2429e85f`

A source inventory captured before the full scan and verified afterwards confirms **all 381 files retain
identical SHA256, sizes and nanosecond modification times**. The inventory and CSV/validation artifacts
stay in ignored `.local/`; images and models stay in app data. No source file was written, moved or deleted.

## Acceptance checklist

| Requested initial-use criterion | Evidence |
| --- | --- |
| 1. Launch locally on Windows | Setup/start scripts, localhost production UI exercised |
| 2. Choose a Nikon NEF folder | Supplied 381-NEF folder scanned using path entry |
| 3. Photographs appear progressively | Browser observed partial 16/381 and subsequent batches |
| 4. Real progress | SSE counters, stages, elapsed time and measured throughput |
| 5. Actual aesthetic and technical scores | Real CPU inference, deterministic classical measurements, offline reference check |
| 6. Identify automatic selections | Recommended badges, AI filter and 96-frame shortlist |
| 7. Related frames and reasons | Ranked groups, alternative previews and measured-only explanations |
| 8. Manually keep/exclude | Browser P/X/U and ratings, API persistence tests |
| 9. Reopen with decisions preserved | Restart, SQLite tests, unchanged-library cache check |
| 10. Selected page and original-path CSV | 96 selected; both CSVs parsed and all paths checked against originals |
| 11. Offline after installation | Socket-blocked reference inference, locally served fonts/assets, no runtime downloads |
| 12. Originals unchanged | Full before/after SHA256, size and mtime comparison |

## Explicit limits and next validation

- XMP writing is disabled, with conflict detection/dry-run reason and a rejected confirmation endpoint.
  No merging, star mapping, sidecar backups or Lightroom round trips are claimed as implemented.
- No native browser folder picker; manual path entry is functional.
- No sensor-level RAW inspection, automatic RAW copy export, personal preference learning, richer
  critiques, genre tuning, semantic panorama detector, or side-by-side comparison.
- Similarity is conservative and bounded; protected alternatives require human review.
- The automated NEF fallback tests use mocks. The real source test covers this D850 collection only;
  add a redistributable, consented camera-specific fixture before claiming portable NEF regression coverage.
- The 1,000–5,000-file responsiveness/memory soak target is **not yet measured**. To validate, use a
  representative collection with the installed model, observe process working set, API response times
  and incremental gallery availability, then repeat unchanged-folder scanning to verify cache reuse.
- Artistic usefulness still needs user-labelled keeper judgements; functional tests do not establish it.

## Reproduce key checks

```powershell
cd C:\repo\framewise-curator
.\scripts\setup.ps1 -WithAI
.\scripts\start.ps1
.\backend\.venv\Scripts\python.exe .\scripts\validate_library.py LIBRARY_ID --expected PHOTO_COUNT
.\backend\.venv\Scripts\python.exe .\scripts\validate_model.py PATH_TO_A_CACHED_PREVIEW.jpg
```

The integrity utility is read-only: `source_integrity.py capture SOURCE MANIFEST` before processing,
then `source_integrity.py verify SOURCE MANIFEST` afterwards. Keep MANIFEST outside the source folder.
