# Run Framewise with Docker

## Download, extract, start

Install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/) with Linux containers.
No host Python, Node.js, ExifTool or CUDA installation is needed.

1. Extract the Docker ZIP and double-click **Start Framewise.cmd**.
2. On first launch, select the parent folder containing your photo collections in the Windows folder dialog.
3. The launcher loads the bundled `framewise-image.tar`, or builds the image if this is a source-only ZIP.
   The first load/build can take several minutes. It waits for a healthy app before opening the browser.
4. Open **Scan → Choose folder → Photographs**, browse to a trip and click **Use this folder**.
5. For AI, choose **Settings → Approve download & install AI (~350 MB)** once. The pinned OpenAI/LAION
   weights stay in the persistent volume. Without weights, the app honestly uses classical measurements.
   After installation, scan/check for changes to populate AI scores.

**Stop Framewise.cmd** stops the app without removing data. Start again to resume. Docker Desktop is a
prerequisite, not installed silently. The CMD wrapper uses a process-only PowerShell execution-policy
setting; it does not change the machine’s policy. Normal scanning is offline after setup.

Prebuilt bundles target **linux/amd64**. Docker Desktop on Windows x64 was tested. Native ARM builds
and macOS emulation are not qualified. Packaging prepares a local ZIP; it does not publish a GitHub Release
or registry image automatically.

## Options and other platforms

```powershell
.\scripts\start-docker.ps1 -Photos 'C:\Pictures' -NoBrowser
# Run beside the native edition on 8765:
.\scripts\start-docker.ps1 -Photos 'C:\Pictures' -Port 8766
# Rebuild changed source:
.\scripts\start-docker.ps1 -Build
.\scripts\stop-docker.ps1
```

The launcher remembers `.local/docker-settings.json`. Choose a parent broad enough for multiple trips.
To change it, supply `-Photos`, or remove that settings file to see the dialog again. Each parent gets its
own persistent volume; earlier workspaces remain. A mount-identity check prevents saved collections from
silently referring to a different host folder at `/photos`. Native `%LOCALAPPDATA%\Framewise` data stays
separate and untouched; automatic migration is not included.

```sh
sh scripts/start-docker.sh "$HOME/Pictures"
# Or use Compose directly:
export FRAMEWISE_PHOTOS_PATH="$HOME/Pictures"
export FRAMEWISE_WORKSPACE_ID="my-pictures"
docker compose up -d --build --wait
docker compose stop
```

The shell launcher loads a bundled image or builds it and opens a browser when `open`/`xdg-open` exists.
On Linux, the non-root process uses UID/GID 1000; the shared folder must be readable by that user.
Docker Desktop handles the Windows bind mount. Remote Docker daemons cannot access client-local folders.

## What is mounted

| Location | Purpose | Access |
| --- | --- | --- |
| `/photos` | Your chosen host photo parent | Read-only; nonexistent host paths fail instead of being created |
| `/data` | SQLite, previews, taste feedback, weights and mount identity | Persistent named volume |
| `/tmp` | Temporary runtime files | Ephemeral tmpfs |
| Application | Python, ExifTool, frontend and CPU libraries | Read-only, unprivileged user, capabilities dropped |

Only localhost is exposed. No Docker socket or privileged container is needed. The folder browser lists
directories without uploading files. Restricted mode rejects out-of-mount paths and traversal in browsing
and collection creation; symlinks/junctions are omitted.

Compose sets `FRAMEWISE_HOST_PHOTO_ROOT` from the chosen host path. CSV/lightbox source paths translate
back to that prefix, including Windows separators, spaces and Unicode. Backend reads stay under `/photos`.
Unpaired rasters retain their actual original paths; no RAW path is fabricated.

Weights are excluded from images and bundles. The Settings download button requires explicit approval;
scanning cannot run concurrently with installation. Failures are shown and retryable. Images are never
sent to a model service. Stop/recreate preserves the volume; **do not run `docker compose down -v` if you
want to keep selections and feedback**. Native data, CSV downloads and your own backups are separate.

## Build a distributable ZIP

```powershell
docker build --platform linux/amd64 -t framewise:0.2.0 .
.\backend\.venv\Scripts\python.exe .\scripts\package_docker.py --include-image
# Omit --include-image for a smaller source starter that builds on first launch.
```

The packager uses a source/assets whitelist and optional `docker save` output. It excludes app data,
photographs, weights, credentials, Git history, virtual environments and node_modules. It adds per-file
hashes, checks ZIP integrity and writes a SHA256 receipt. Existing bundles are never overwritten.
Default output: `.local/releases/Framewise-0.2.0-Docker.zip` (ignored by Git).

## Troubleshooting

- Start Docker Desktop in Linux-container mode before launching.
- If 8765 is busy, stop the native edition with `scripts/stop.ps1`, or use `-Port 8766`.
- Reconnect inaccessible drives; choose a readable parent. To browse outside the mount, relaunch with a
  different parent. Do not delete the identity file to bypass a workspace mismatch.
- Retry failed model downloads in Settings. Starting/scanning never triggers a weights download by itself.
- First scans of large NEFs can be slower through Windows Docker bind mounts. Cached rescans reuse results.
- Inspect the container in Docker Desktop, or run `docker compose logs --tail 100` with Compose variables
  set. Do not attach private pictures/databases to public bug reports.

References: [Docker read-only bind mounts](https://docs.docker.com/engine/storage/bind-mounts/),
[Compose services](https://docs.docker.com/reference/compose-file/services/),
[uv CPU PyTorch indexes](https://docs.astral.sh/uv/guides/integration/pytorch/).
