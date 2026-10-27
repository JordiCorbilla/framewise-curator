# Docker 0.2 acceptance — 26 October 2026

## Completed acceptance checks

| Requested outcome | Verified result |
| --- | --- |
| Docker runs the product | Linux/amd64 image built and healthy on Docker Desktop 4.92.0 / Engine 29.8.0 / Compose 5.5.1. |
| Easy Windows startup | PowerShell launcher exercised with a real photo parent and alternate port; stop/start recreated the container successfully and remembered the saved port. CMD wrappers call these scripts. |
| No host development stack needed | Image contains built React UI, Python, ExifTool, LibRaw fallback and CPU PyTorch/torchvision; no CUDA dependency. |
| Downloadable prebuilt bundle | Whitelist packager creates the ZIP, image tar, per-file manifest and ZIP checksum; no public release/registry upload was performed. |
| Folder-selection button | Browser test used Scan → Choose folder → Photographs → Architecture → Use this folder → Start local scan, without typing a path. |
| Read-only originals | Inspected `/photos` bind mount had `RW=false`. App root filesystem is read-only, with unprivileged user and capabilities dropped. |
| Persistent decisions and models | Real Keep/four-star override survived stop/recreate/start; original decision restored afterwards. Models and all 403 cached photos remained. |
| Correct Lightroom paths | Four category CSVs resolved to existing host NEFs rather than `/photos` paths, including edited-JPEG associations. |
| Explicit AI setup | Settings download button explains ~350 MB and requires consent. Tests cover missing consent/dependencies, active-scan exclusion and installer failure/retry. Existing approved weights were reused for live validation. |
| Workspace safety | A host-parent-derived volume and mount identity prevent silent rebinding of old records to different originals. Native app data was preserved separately. |

## Real Docker run

The full **403-image collection (381 D850 NEFs + 22 JPEGs)** completed with **403 previews, 403 AI scores,
403 embeddings and zero failures**. Initial scan took **444.1 seconds** over the Windows read-only bind
mount. A subsequent scan reused all 403 unchanged results in **2.7 seconds**, with no inference work.
This first-scan observation is slower than native Windows on this workstation; it is not a throughput guarantee.

Live export counts: Lightroom **101**, Flickr **11**, Competition **3**, Alternatives **45**, All **403**.
Repeated recalculations were identical within this Docker workspace (0.332s and 0.342s observed).
The final NEF handoffs were `DSC_7982.NEF`, `DSC_8039.NEF`, `DSC_7873.NEF`, three distinct captures.
The native workspace’s previously backfilled embeddings used recompressed cached JPEGs; this fresh scan
used acquisition-time image buffers. Those differing inputs can change relative ranking; cross-workspace
bit-identical recommendations are not claimed.

The image uses **torch 2.9.0+cpu / torchvision 0.24.0+cpu**, with `torch.version.cuda = None`.
A network-blocked reference check inside Docker produced **7.4447736740112305** from both Framewise and
the reference (absolute difference **0**, identical repeated batch scores). The same preview’s native
value differs by less than 0.000001, within the validator’s tolerance.

The final image ID is `sha256:843fd764ddd6fbf4500dc31aaa093284a7d5173a8ae90ab68fd8e3f03bf073ea`;
uncompressed image size **1,402,368,790 bytes**. `/data` is empty in the shipped image: no model weights,
database, preview cache or package-download cache is baked in. The release manifest records its image ID
and file hashes. Image build context was restricted to source/assets, not private workspace state.

## Tests and browser review

**62 tests passed**. Ruff lint/format, frontend ESLint (zero warnings), TypeScript and production build
passed. npm audit reported zero vulnerabilities. One upstream Starlette/AnyIO deprecation warning remains.
New tests cover folder roots, pagination/filtering, mount escape rejection in both browsing/creation,
Windows path translation, mount-identity mismatch and consent/scan interlocks for installation.

The browser completed an owned one-image demo scan without weights, retaining an honest technical-only
state. Folder-picker screenshots use only project-owned generated demo directories. Personal photos and
private application databases are excluded from screenshots and bundles. Older MVP/Highlights validation
is recorded [separately](highlights-validation.md).

## Limits and release state

Docker Desktop is still required. The Windows dialog is implemented with Windows Forms; the exercised
launcher path supplied the folder parameter, while the in-app chooser was tested through the browser.
macOS/Linux launcher scripts are supplied, but their desktop integration and ARM emulation were not tested.
No 1,000–5,000-file soak, automatic native database migration or public distribution upload is claimed.
The prebuilt ZIP and SHA256 receipt are local release artifacts under ignored `.local/releases`.
