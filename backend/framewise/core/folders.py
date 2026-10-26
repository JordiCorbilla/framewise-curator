"""Source-folder access and host path presentation, shared by Docker and native mode."""

import json
import ntpath
import os
from pathlib import Path


def photo_roots():
    configured = os.environ.get("FRAMEWISE_PHOTO_ROOTS")
    if configured:
        roots = json.loads(configured)
        if not isinstance(roots, list) or not roots or any(not isinstance(p, str) for p in roots):
            raise ValueError("FRAMEWISE_PHOTO_ROOTS must be a nonempty JSON array of absolute paths")
        if any(not Path(p).is_absolute() for p in roots):
            raise ValueError("Photo roots must be absolute")
        return [Path(p).resolve() for p in roots]
    if os.name == "nt":
        import ctypes

        mask = ctypes.windll.kernel32.GetLogicalDrives()
        return [Path(f"{chr(65 + n)}:/") for n in range(26) if mask & (1 << n)]
    return [Path.home(), Path("/mnt"), Path("/media")]


def restricted():
    return bool(os.environ.get("FRAMEWISE_PHOTO_ROOTS"))


def allowed_source(path):
    resolved = Path(path).expanduser().resolve()
    if restricted() and not any(resolved == root or root in resolved.parents for root in photo_roots()):
        raise ValueError("Choose a folder inside the mounted photographs folder using Choose folder")
    return resolved


def display_path(source, relative):
    """CSV/lightbox paths refer to the host's real originals, never a fabricated RAW path."""
    source_root = Path(source).resolve()
    path = (source_root / relative).resolve()
    path.relative_to(source_root)
    host = os.environ.get("FRAMEWISE_HOST_PHOTO_ROOT")
    if host and restricted():
        root = photo_roots()[0]
        if path == root or root in path.parents:
            parts = path.relative_to(root).parts
            return (
                ntpath.join(host, *parts) if ntpath.splitdrive(host)[0] else str(Path(host).joinpath(*parts))
            )
    return str(path)


def verify_mount_identity(data):
    """Never reinterpret an existing database against a different host folder mounted at /photos."""
    if not restricted():
        return
    identity = {
        "roots": [str(p) for p in photo_roots()],
        "host": os.environ.get("FRAMEWISE_HOST_PHOTO_ROOT", ""),
    }
    manifest = data / "photo-mount.json"
    if manifest.exists() and json.loads(manifest.read_text(encoding="utf-8")) != identity:
        raise RuntimeError(
            "This data volume belongs to a different photographs folder. "
            "Use the launcher to select a separate workspace; do not reuse its volume with another mount."
        )
    manifest.write_text(json.dumps(identity, indent=2), encoding="utf-8")
