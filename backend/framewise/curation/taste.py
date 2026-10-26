"""Small local centroid learner. Explicit taste labels only; no inferred personal judgements."""

import hashlib
import json
import math

import numpy as np

from framewise.db.models import (
    Photo,
    PhotoEmbedding,
    PhotoMetrics,
    PhotoRawSource,
    TasteLabel,
    TasteProfile,
    now,
)

VERSION = "taste-centroid-v1"
BLEND = 0.30
MIN_PER_CLASS = 10


def vector_for(embedding, photo, model_id):
    if not embedding or embedding.identity != photo.identity or embedding.model_id != model_id:
        return None
    vector = np.frombuffer(embedding.vector, dtype=np.float32)
    length = np.linalg.norm(vector)
    return vector / length if vector.shape == (512,) and np.isfinite(vector).all() and length > 0 else None


def examples(db):
    rows = (
        db.query(TasteLabel, Photo, PhotoEmbedding, PhotoMetrics)
        .join(Photo, Photo.id == TasteLabel.photo_id)
        .join(PhotoEmbedding, PhotoEmbedding.photo_id == Photo.id)
        .join(PhotoMetrics, PhotoMetrics.photo_id == Photo.id)
        .filter(Photo.status == "ready")
        .all()
    )
    # Union reliable burst groups, known RAW/JPEG pairs, and near-identical pHashes.
    # A whole group belongs to one split, so alternate versions cannot leak into holdout.
    parent = {p.id: p.id for _, p, _, _ in rows}

    def root(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(a, b):
        a, b = root(a), root(b)
        parent[max(a, b)] = min(a, b)

    anchors, bands = {}, {}
    pairs = dict(db.query(PhotoRawSource.photo_id, PhotoRawSource.raw_photo_id).all())
    for _, p, _, _ in sorted(rows, key=lambda r: r[1].id):
        for key in (f"group:{p.group_id}" if p.group_id else None, f"capture:{pairs.get(p.id, p.id)}"):
            if key:
                if key in anchors:
                    union(p.id, anchors[key])
                anchors[key] = p.id
        if p.phash:
            value = int(p.phash, 16)
            # Five bands guarantee a shared band at Hamming distance <= 4.
            for part in range(5):
                key = (part, (value >> (part * 13)) & ((1 << (12 if part == 4 else 13)) - 1))
                for other in bands.get(key, []):
                    if (
                        abs(p.width / max(p.height, 1) - other.width / max(other.height, 1)) < 0.035
                        and (value ^ int(other.phash, 16)).bit_count() <= 4
                    ):
                        union(p.id, other.id)
                bands.setdefault(key, []).append(p)
    groups = {}
    for label, photo, embedding, metrics in rows:
        vector = vector_for(embedding, photo, metrics.model_id)
        if vector is not None:
            groups.setdefault((root(photo.id), embedding.model_id), []).append((label, photo, vector))
    clean, conflicts = [], 0
    for (key, model_id), group in sorted(groups.items()):
        if len({label.value for label, _, _ in group}) != 1:
            conflicts += 1
            continue
        label, photo, vector = sorted(group, key=lambda r: r[1].id)[0]
        clean.append(
            {
                "key": key,
                "photo_id": photo.id,
                "value": label.value,
                "model_id": model_id,
                "vector": vector,
                "identity": photo.identity,
                "vector_hash": hashlib.sha256(vector.tobytes()).hexdigest(),
            }
        )
    return clean, conflicts


def choose_model(samples):
    models = sorted({s["model_id"] for s in samples})
    return (
        max(
            models,
            key=lambda m: (
                min(sum(s["model_id"] == m and s["value"] == v for s in samples) for v in (-1, 1)),
                sum(s["model_id"] == m for s in samples),
            ),
        )
        if models
        else None
    )


def fingerprint(samples):
    return hashlib.sha256(
        json.dumps(
            sorted(
                (s["key"], s["photo_id"], s["value"], s["model_id"], s["identity"], s["vector_hash"])
                for s in samples
            )
        ).encode()
    ).hexdigest()


def ensure_current(db):
    profile = db.get(TasteProfile, "local")
    if profile and profile.data.get("status") == "trained":
        samples, _ = examples(db)
        current = [s for s in samples if s["model_id"] == profile.data["model_id"]]
        if fingerprint(current) != profile.data.get("dataset_hash"):
            invalidate(db)
            return True
    return False


def fit(samples):
    """Fixed algorithm; deterministic class-stratified group holdout, never fitted on holdout."""
    by_class = {
        v: sorted(
            (s for s in samples if s["value"] == v),
            key=lambda s: hashlib.sha256(s["key"].encode()).hexdigest(),
        )
        for v in (-1, 1)
    }
    if any(len(by_class[v]) < MIN_PER_CLASS for v in by_class):
        return None
    heldout, train = [], []
    for values in by_class.values():
        count = math.ceil(len(values) * 0.25)
        heldout.extend(values[:count])
        train.extend(values[count:])
    positive = np.stack([s["vector"] for s in train if s["value"] == 1])
    negative = np.stack([s["vector"] for s in train if s["value"] == -1])
    center = (positive.mean(axis=0) + negative.mean(axis=0)) / 2
    direction = positive.mean(axis=0) - negative.mean(axis=0)
    norm = float(np.linalg.norm(direction))
    if norm < 1e-8:
        return {"status": "no_signal", "reason": "These examples contain no separable embedding signal."}
    direction /= norm
    margins = np.array([(s["vector"] - center) @ direction for s in train])
    scale = max(float(margins.std()), 0.01)
    correct = {
        v: [((s["vector"] - center) @ direction >= 0) == (v == 1) for s in heldout if s["value"] == v]
        for v in (-1, 1)
    }
    accuracy = float(np.mean([np.mean(correct[v]) for v in correct]))
    payload = {
        "status": "trained",
        "algorithm": VERSION,
        "model_id": samples[0]["model_id"],
        "center": center.tolist(),
        "direction": direction.tolist(),
        "scale": scale,
        "training_count": len(train),
        "heldout_count": len(heldout),
        "heldout_balanced_accuracy": accuracy,
        "eligible": accuracy >= 0.60,
        "training_ids": sorted(s["photo_id"] for s in train),
        "heldout_ids": sorted(s["photo_id"] for s in heldout),
        "dataset_hash": fingerprint(samples),
    }
    payload["version"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    return payload


def profile_info(db):
    profile = db.get(TasteProfile, "local")
    samples, conflicts = examples(db)
    model = choose_model(samples)
    samples = [s for s in samples if s["model_id"] == model]
    counts = {v: sum(s["value"] == v for s in samples) for v in (-1, 1)}
    data = profile.data if profile else {}
    return {
        **{
            k: v
            for k, v in data.items()
            if k not in ("center", "direction", "scale", "training_ids", "heldout_ids")
        },
        "status": data.get("status", "collecting"),
        "enabled": bool(profile and profile.enabled),
        "labels": db.query(TasteLabel).count(),
        "usable_likes": counts[1],
        "usable_dislikes": counts[-1],
        "conflicting_groups": conflicts,
        "minimum_per_class": MIN_PER_CLASS,
        "blend": BLEND,
        "updated": profile.updated if profile else None,
        "reason": data.get(
            "reason",
            "Label at least 10 distinct frames you like and 10 you dislike, using the same image encoder.",
        ),
    }


def affinity(profile, vector, model_id):
    if (
        not profile
        or not profile.enabled
        or profile.data.get("status") != "trained"
        or not profile.data.get("eligible")
        or profile.data.get("model_id") != model_id
        or vector is None
    ):
        return None
    data = profile.data
    margin = float((vector - np.asarray(data["center"])) @ np.asarray(data["direction"])) / data["scale"]
    # An affinity display scale, deliberately not presented as a probability.
    return float(100 / (1 + np.exp(-np.clip(margin, -12, 12))))


def invalidate(db):
    profile = db.get(TasteProfile, "local")
    if profile:
        profile.data, profile.enabled, profile.updated = {}, False, now()


def rerank_all(db):
    from framewise.curation.highlights import rebuild
    from framewise.curation.ranking import recommend
    from framewise.db.models import Library

    db.flush()
    for library in db.query(Library):
        recommend(db, library)
        rebuild(db, library)
