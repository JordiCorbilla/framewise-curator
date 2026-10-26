# Current acceptance validation — 26 October 2026

This covers Highlights and the product/preference updates. The [original MVP report](validation.md)
records the initial 381-NEF scan. Functional checks do not establish aesthetic accuracy or personal fit.

## Executed checks

- **56 backend tests passed**, including ranking, thresholds, duplicate/diversity behaviour, category
  persistence, rescan/cancellation, RAW associations, manual replacement, exports and offline evaluation.
  New tests exercise collection rename/removal, exact-name confirmation, active-scan/foreign-origin
  rejection, locked-cache failure, source preservation, taste cold start, real centroid fitting on
  synthetic vectors, disjoint grouped holdout, opt-in blending, persistence, forgetting, encoder mismatch,
  conflicting duplicate labels and changed-source invalidation.
- Ruff check and formatting check passed for **37 Python files**.
- Frontend ESLint passed with **zero warnings**; TypeScript and the Vite production build passed.
- `npm audit --audit-level=low`: **zero vulnerabilities**, including development dependencies.
  Vite was updated from 7.1.12 to 7.3.7 after the audit identified affected development-server code.
- One upstream Starlette/AnyIO test-client deprecation warning remains; it did not fail the checks.
- Windows start/stop/restart exercised. Normal app serves `127.0.0.1:8765`; UI, font and icon assets are local.

## Real collection and inference

The recursive NY collection now contains **403 photos: 381 NEFs and 22 edited JPEGs**. All 403 are ready,
with cached 512-dimensional embeddings and zero file failures. Embedding backfill used existing display
JPEGs for previously processed images and preserved existing aesthetic values and manual Lightroom
decisions. There are 22 unambiguous edited-JPEG/NEF associations; folder names were not treated as labels.

The offline model validator blocked network sockets and compared the installed implementation with its
reference. Both returned **7.444772720336914** for the validation preview, absolute difference **0.0**;
repeated batches were identical. Checkpoint IDs and hashes remain in the installation manifest.

The final read-only source check rehashed the original **381 NEFs** against their existing inventory:
**zero changed and zero missing**, including identical sizes and nanosecond modification times.
The additional 22 JPEGs were not part of that original baseline. Nothing in this work wrote to the source folder.
Private inventories and runtime evidence remain under ignored `.local`, not in the public documentation assets.

## Live ranking and export checks

`scripts/validate_highlights.py` exercised the normal app and required every category handoff to resolve
to an existing NEF. Results:

| Export | Rows |
| --- | ---: |
| Lightroom Picks | 101 |
| Flickr Standouts | 11 |
| Competition Top 3 | 3 |
| Competition alternatives | 45 |
| All analysed photos | 403 |

The Top 3 referenced three distinct RAW captures: `DSC_7982.NEF`, `DSC_8039.NEF`, `DSC_7875.NEF`.
The latter two recommendations were analysed from registered edited JPEGs; CSV provenance retains that fact.
Two repeated recalculations produced identical finalists, standouts and alternatives, in **0.223s** and
**0.290s** in this run. These timings are local observations, not a large-library performance qualification.
The live pair comparison returned pHash distance **24/64**, cosine **0.7971671223640442**, different groups.

No user-favourite agreement was measured: explicit historical favourite labels have not been supplied.
The blank offline-evaluation template remains unlabelled. No private image was published.

## Browser and restart checks

An isolated demo data directory used twelve project-owned procedural illustrations with actual CPU
inference. [Screenshot provenance/configuration](images/README.md) records the lowered demo floors.
The normal collections were not used for test feedback.

- Renamed a collection through the UI and verified the title after a server restart.
- Replaced #1 through filename search. The new finalist was labelled Your choice; the displaced finalist
  remained an alternative. All three manual slots survived a real process restart. Automatic ranking
  was subsequently restored in this demo.
- Opened side-by-side comparison and verified images, model/technical values, pHash distance and cosine.
- Added an explicit Like in the lightbox; its keeper decision stayed unchanged. Demo labels were then
  cleared. No synthetic preference labels were added to the normal workspace.
- Applied the 5% budget in the browser: the twelve-frame demo went from three automatic picks to one,
  with 8% correctly shown as its rounded actual selection. The demo was returned to 25%.
- Tested the stricter-floors preset values and confirmed a weak demo produces no automatic finalists
  under default floors. Exactly three stayed off for public screenshots.
- Checked collection-removal warning, typed-title field and disabled confirmation state at narrow width.
  Actual permanent deletion, cache cleanup and original preservation were verified in isolated API tests.
- Reviewed layouts in a 390px iframe and 1440px iframe. Content widths were 375px and 1425px after
  Windows scrollbars: no horizontal document overflow and no broken images in either Highlights view.
  The removal modal also had no horizontal overflow. Sidebar spacing was fixed for short desktops.
- The final showcase browser reported no warning/error console entries. Public images were visually reviewed.

## Acceptance criteria checked

| Requirement | Evidence / result |
| --- | --- |
| Launch locally on Windows; select a NEF folder | Local launcher and real registered D850 collection; pass. |
| Progressive previews and actual scan/scoring progress | Initial live validation plus incremental scan/SSE tests; pass. |
| Inspect actual aesthetic/technical scores and automatic picks | Real scores, offline reference match, gallery/lightbox; pass. |
| Related frames and manual Keep/Exclude | Grouping/protected-sequence/persistence tests and existing live workflow; pass. |
| Reopen without losing decisions | Real restart with manual finalist slots/title and persistence tests; pass. |
| Selected page and original-NEF CSV export | Live 101-row Lightroom handoff and four category exports; pass. |
| Offline inference after installation | Network-blocked reference test, local runtime/assets; pass. |
| Original pictures not moved, modified or deleted | Original 381-NEF hash/size/mtime comparison and source-preservation tests; pass. |
| Highlights portfolio candidates and independent Top 3 | 11 standouts, three distinct RAW finalists, sparse/weak-collection tests; pass. |
| Measured evidence and side-by-side/manual reranking | Browser comparison/replacement plus deterministic API tests; pass. |
| Professional font and proper icon | Self-hosted Inter Variable; original SVG/F mark, ICO/PNG/touch/install assets; pass. |
| Rename/remove a collection | Visible Library controls, validation, active-scan protection and isolated deletion tests; pass. |
| More selective recommendations | Visible 5/10/25% presets and stricter Highlights floors; pass. |
| Learn explicit preferences locally | Functional gated centroid learner, opt-in blending, provenance, pause/reset; pass. Personal quality remains unmeasured. |
| Showcase README and layout/functionality images | README, five original-demo UI screenshots, reproducible demo script and provenance; pass. |
| Publication-ready blog draft | `docs/blog/framewise.md` with matching image assets and truthful limits; pass. Draft only, as requested. |

## Intentionally deferred

Safe XMP writing remains disabled; CSV does not create Lightroom Collections automatically. No cloud
publishing or competition submission occurs. Native installer/folder picker, genre/theme judgement,
advanced critique and sensor-level RAW inspection remain deferred. A measured 1,000–5,000-photo soak,
other camera/NEF variants and independent personal-quality evaluation have not been completed.
