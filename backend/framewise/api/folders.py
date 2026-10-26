import os

from fastapi import APIRouter, HTTPException, Query

from framewise.core.config import DATA
from framewise.core.folders import allowed_source, photo_roots, restricted

router = APIRouter(prefix="/api")


@router.get("/folders")
def folders(path: str | None = None, page: int = Query(1, ge=1), q: str = Query("", max_length=200)):
    roots = photo_roots()
    root_items = [
        {"path": str(root), "name": "Photographs" if restricted() and len(roots) == 1 else str(root)}
        for root in roots
        if root.is_dir()
    ]
    if path is None:
        return {
            "roots": root_items,
            "path": None,
            "parent": None,
            "items": root_items,
            "page": 1,
            "total": len(root_items),
            "restricted": restricted(),
        }
    try:
        folder = allowed_source(path)
        if not folder.is_dir():
            raise HTTPException(404, "Folder is unavailable. Reconnect the drive or check the Docker mount.")
        directories = []
        with os.scandir(folder) as entries:
            for entry in entries:
                try:
                    if (
                        entry.name.startswith(".")
                        or not entry.is_dir(follow_symlinks=False)
                        or entry.is_symlink()
                    ):
                        continue
                    if getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
                        continue
                    child = allowed_source(entry.path)
                    if child == DATA.resolve() or DATA.resolve() in child.parents:
                        continue
                    if q.casefold() in entry.name.casefold():
                        directories.append({"path": str(child), "name": entry.name})
                except (OSError, ValueError):
                    continue
        directories.sort(key=lambda item: (item["name"].casefold(), item["path"]))
        parent = str(folder.parent) if folder.parent != folder else None
        if restricted() and folder in roots:
            parent = None
        return {
            "roots": root_items,
            "path": str(folder),
            "parent": parent,
            "items": directories[(page - 1) * 100 : page * 100],
            "page": page,
            "total": len(directories),
            "restricted": restricted(),
        }
    except ValueError as exc:
        raise HTTPException(403, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(
            403, "This folder is not readable. Choose an accessible photographs folder."
        ) from exc
    except OSError as exc:
        raise HTTPException(
            422, "Could not read this folder. Check the drive and access permissions."
        ) from exc
