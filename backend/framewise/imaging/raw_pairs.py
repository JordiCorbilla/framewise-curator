"""Conservative edited-JPEG/RAW association using registered source metadata, never filename alone."""

from pathlib import PurePath

from framewise.db.models import Photo, PhotoMetadata, PhotoRawSource


def associate(db, library_id):
    rows = (
        db.query(Photo, PhotoMetadata)
        .join(PhotoMetadata, PhotoMetadata.photo_id == Photo.id)
        .filter(Photo.library_id == library_id, Photo.status == "ready")
        .all()
    )
    ids = [p.id for p, _ in rows]
    if ids:
        db.query(PhotoRawSource).filter(PhotoRawSource.photo_id.in_(ids)).delete(synchronize_session="fetch")
    index = {}

    def key(p, metadata):
        captured = str(metadata.data.get("DateTimeOriginal", ""))[:19]
        camera = str(metadata.data.get("Model", "")).strip().casefold()
        if not captured or not camera:
            return None
        return PurePath(p.filename).stem.casefold(), captured, camera

    for photo, metadata in rows:
        capture = key(photo, metadata)
        if photo.filename.lower().endswith(".nef") and capture:
            index.setdefault(capture, []).append(photo.id)
    result = {}
    for photo, metadata in rows:
        matches = index.get(key(photo, metadata), [])
        if not photo.filename.lower().endswith(".nef") and len(matches) == 1:
            result[photo.id] = matches[0]
            db.add(
                PhotoRawSource(
                    photo_id=photo.id,
                    raw_photo_id=matches[0],
                    method="unique filename stem, capture timestamp and camera model",
                )
            )
    db.flush()
    return result
