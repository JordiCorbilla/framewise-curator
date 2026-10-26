import math
import uuid
from datetime import datetime

from framewise.core.config import DEFAULT_WEIGHTS
from framewise.curation.taste import BLEND, affinity, vector_for
from framewise.db.models import (
    Photo,
    PhotoEmbedding,
    PhotoMetadata,
    PhotoMetrics,
    SimilarityGroup,
    TasteProfile,
)


def timestamp(metadata):
    try:
        return datetime.strptime(
            str(metadata.get("DateTimeOriginal", ""))[:19], "%Y:%m:%d %H:%M:%S"
        ).timestamp()
    except ValueError:
        return None


def combined_score(calibrated, aesthetic, weights):
    values = {"sharpness": calibrated["sharpness"], "exposure": calibrated["exposure"]}
    if aesthetic is not None:
        values["aesthetic"] = min(100, max(0, aesthetic * 10))
    denominator = sum(weights[k] for k in values)
    return round(sum(weights[k] * v for k, v in values.items()) / denominator, 3) if denominator else 0


def regroup(db, library_id):
    db.query(SimilarityGroup).filter_by(library_id=library_id).delete()
    rows = (
        db.query(Photo, PhotoMetadata, PhotoMetrics)
        .join(PhotoMetadata, PhotoMetadata.photo_id == Photo.id)
        .join(PhotoMetrics, PhotoMetrics.photo_id == Photo.id)
        .filter(Photo.library_id == library_id, Photo.status == "ready")
        .all()
    )
    rows.sort(key=lambda row: (timestamp(row[1].data) or 0, row[0].filename, row[0].id))
    buckets = []
    for photo, metadata, metrics in rows:
        photo.group_id, photo.group_rank = None, None
        captured = timestamp(metadata.data)
        matched = None
        for group in reversed(buckets[-48:]):
            anchor, anchor_meta, anchor_metrics = group[0]
            anchor_time = timestamp(anchor_meta.data)
            distance = (int(photo.phash, 16) ^ int(anchor.phash, 16)).bit_count()
            same_shape = abs(photo.width / photo.height - anchor.width / anchor.height) < 0.035
            close_time = (
                captured is not None and anchor_time is not None and abs(captured - anchor_time) <= 12
            )
            # Exact hashes can match without EXIF. Looser matches require a capture-time window.
            if same_shape and (distance == 0 or (close_time and distance <= 10)):
                matched = group
                break
        if matched is None:
            buckets.append([(photo, metadata, metrics)])
        else:
            matched.append((photo, metadata, metrics))
    for members in buckets:
        if len(members) < 2:
            continue
        members.sort(key=lambda row: (-(row[0].score or 0), row[0].filename, row[0].id))
        group_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "|".join(sorted(row[0].id for row in members))))
        brightness = [row[2].raw["mean_luminance"] for row in members]
        compensation = {str(row[1].data.get("ExposureCompensation", 0)) for row in members}
        anchor_hash = int(members[0][0].phash, 16)
        uncertain = any((int(row[0].phash, 16) ^ anchor_hash).bit_count() > 6 for row in members)
        protected = len(compensation) > 1 or max(brightness) - min(brightness) > 0.13 or uncertain
        reason = (
            "Possible bracket/sequence or uncertain match: review all members"
            if protected
            else "Near-identical perceptual hash; capture-time window when available"
        )
        db.add(
            SimilarityGroup(
                id=group_id, library_id=library_id, count=len(members), protected=protected, reason=reason
            )
        )
        for index, (photo, _, _) in enumerate(members, 1):
            photo.group_id, photo.group_rank = group_id, index


def recommend(db, library, group=True):
    rows = (
        db.query(Photo, PhotoMetrics)
        .join(PhotoMetrics, PhotoMetrics.photo_id == Photo.id)
        .filter(Photo.library_id == library.id, Photo.status == "ready")
        .all()
    )
    weights = library.config.get("weights", DEFAULT_WEIGHTS)
    profile = db.get(TasteProfile, "local")
    embeddings = (
        {
            e.photo_id: e
            for e in db.query(PhotoEmbedding)
            .join(Photo, Photo.id == PhotoEmbedding.photo_id)
            .filter(Photo.library_id == library.id)
        }
        if profile and profile.enabled
        else {}
    )
    for photo, metrics in rows:
        photo.score = combined_score(metrics.calibrated, metrics.aesthetic, weights)
        taste = affinity(
            profile, vector_for(embeddings.get(photo.id), photo, metrics.model_id), metrics.model_id
        )
        if taste is not None:
            photo.score = round((1 - BLEND) * photo.score + BLEND * taste, 3)
    db.flush()
    if group:
        regroup(db, library.id)
    protected = {g.id for g in db.query(SimilarityGroup).filter_by(library_id=library.id, protected=True)}
    photos = [row[0] for row in rows]
    photos.sort(
        key=lambda p: (
            bool(p.group_id and p.group_rank != 1 and p.group_id not in protected),
            -(p.score or 0),
            p.filename,
            p.id,
        )
    )
    budget = math.ceil(len(photos) * library.budget / 100)
    for index, photo in enumerate(photos):
        photo.selection_rank = index + 1
        photo.recommendation = (
            "pick"
            if index < budget
            else "review"
            if (photo.group_id in protected or index < budget * 2)
            else "low"
        )
