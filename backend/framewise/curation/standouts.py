"""Pure, deterministic General Best 3 ranker. No semantic judging or success probabilities."""

from dataclasses import dataclass, field

import numpy as np

VERSION = "general-best3-v1"
DEFAULT_CONFIG = {
    "mode": "general",
    "aesthetic_floor": 6.5,
    "technical_floor": 35.0,
    "flickr_aesthetic_floor": 7.0,
    "flickr_percentile": 90.0,
    "flickr_max": 12,
    "aesthetic_weight": 0.65,
    "technical_weight": 0.20,
    "distinctiveness_weight": 0.15,
    "diversity_penalty": 8.0,
    "force_three": False,
}


@dataclass
class Frame:
    id: str
    filename: str
    aesthetic: float | None
    sharpness: float
    exposure: float
    lightroom: bool = False
    group: str | None = None
    phash: str | None = None
    aspect: float = 1.5
    embedding: np.ndarray | None = None
    model_id: str | None = None
    flickr: str = "auto"
    competition: str = "auto"
    manual_rank: int | None = None
    clipping: float = 0
    focus: str = ""
    protected: bool = False
    data: dict = field(default_factory=dict)
    raw_capture: str | None = None


def percentiles(values):
    """Midrank percentiles: ties receive the same value, with no filename-based quality advantage."""
    data = np.asarray(values, dtype=float)
    sorted_values = np.sort(data)
    if len(data) == 1:
        return np.full(1, 100.0)
    return (
        100
        * (
            np.searchsorted(sorted_values, data, side="left")
            + np.searchsorted(sorted_values, data, side="right")
            - 1
        )
        / (2 * max(len(data) - 1, 1))
    )


def same_frame(a, b):
    if a.raw_capture and a.raw_capture == b.raw_capture:
        return True
    if a.group and a.group == b.group and not (a.protected or b.protected):
        return True
    if a.phash and b.phash and abs(a.aspect - b.aspect) < 0.035:
        distance = (int(a.phash, 16) ^ int(b.phash, 16)).bit_count()
        if distance <= 4:
            # Conservative perceptual-hash duplicate suppression, not landmark/scene classification.
            return True
    return False


def similarity(a, b):
    if a.embedding is not None and b.embedding is not None and a.model_id == b.model_id:
        return float(np.clip(a.embedding @ b.embedding, -1, 1))
    if a.phash and b.phash:
        return 1 - (int(a.phash, 16) ^ int(b.phash, 16)).bit_count() / 64
    return 0.0


def distinctiveness(frames):
    """Mean nearest-reference cosine distance. At most 512 deterministic references, bounded matrices."""
    result = np.zeros(len(frames), dtype=float)
    for model_id in sorted({f.model_id for f in frames if f.embedding is not None}, key=str):
        indices = [i for i, f in enumerate(frames) if f.embedding is not None and f.model_id == model_id]
        references = (
            indices
            if len(indices) <= 512
            else [indices[i] for i in np.linspace(0, len(indices) - 1, 512, dtype=int)]
        )
        matrix = np.stack([frames[i].embedding for i in references])
        for start in range(0, len(indices), 128):
            subset = indices[start : start + 128]
            similarities = np.stack([frames[i].embedding for i in subset]) @ matrix.T
            for row, index in enumerate(subset):
                mask = [
                    r != index and not (frames[index].group and frames[index].group == frames[r].group)
                    for r in references
                ]
                other = similarities[row, mask]
                if len(other):
                    nearest = np.sort(other)[-min(5, len(other)) :]
                    result[index] = float(np.clip(1 - nearest.mean(), 0, 2))
    return result


def rank(frames, config=None):
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    if cfg["mode"] != "general":
        raise ValueError("Theme-based ranking has not been implemented or validated")
    frames = sorted(frames, key=lambda f: (f.filename.casefold(), f.id))
    if not frames:
        return {}, {"finalists": [], "alternatives": [], "flickr": [], "viable": 0}
    technical = [0.65 * f.sharpness + 0.35 * f.exposure for f in frames]
    aesthetics = np.zeros(len(frames), dtype=float)
    measured = [i for i, f in enumerate(frames) if f.aesthetic is not None]
    aesthetics[measured] = percentiles([frames[i].aesthetic for i in measured])
    technical_pct = percentiles(technical)
    novelty = distinctiveness(frames)
    novelty_pct = np.zeros(len(frames), dtype=float)
    embedded = [i for i, f in enumerate(frames) if f.embedding is not None]
    novelty_pct[embedded] = percentiles(novelty[embedded])
    output = {}
    for i, f in enumerate(frames):
        has_embedding = f.embedding is not None
        weight = (
            (cfg["aesthetic_weight"] if f.aesthetic is not None else 0)
            + cfg["technical_weight"]
            + (cfg["distinctiveness_weight"] if has_embedding else 0)
        )
        numerator = cfg["aesthetic_weight"] * aesthetics[i] if f.aesthetic is not None else 0
        numerator += cfg["technical_weight"] * technical_pct[i]
        if has_embedding:
            numerator += cfg["distinctiveness_weight"] * novelty_pct[i]
        score = float(numerator / weight) if weight else 0
        viable = (
            f.aesthetic is not None
            and f.aesthetic >= cfg["aesthetic_floor"]
            and technical[i] >= cfg["technical_floor"]
        )
        strengths = [
            f"Aesthetic {f.aesthetic:.2f}/10"
            if f.aesthetic is not None
            else "Aesthetic assessment unavailable",
            f"Technical proxy {technical[i]:.1f}/100",
        ]
        uncertainties = ["Relative heuristic score; no prediction of Flickr engagement or competition wins."]
        if has_embedding:
            strengths.append(f"Visual distance to nearby reference frames {novelty[i]:.3f} (CLIP cosine)")
            uncertainties.append(
                "Embedding distance is a visual-redundancy proxy, not originality or storytelling."
            )
        else:
            uncertainties.append(
                "Embedding unavailable; distinctiveness weight omitted. Cached analysis can fill it."
            )
        if not viable:
            uncertainties.append("Below the automatic quality floor or aesthetic assessment missing.")
        if f.sharpness < 30 or "uncertain" in f.focus:
            uncertainties.append(
                "Inspect focus/detail; low texture or intentional blur may affect the metric."
            )
        if f.clipping > 0.02:
            uncertainties.append(
                f"{f.clipping * 100:.1f}% preview highlights clipped; RAW recovery is unknown."
            )
        if f.protected:
            uncertainties.append("Protected/uncertain burst or bracket: inspect alternatives.")
        output[f.id] = {
            "score": round(score, 4),
            "technical": round(technical[i], 4),
            "aesthetic_percentile": round(float(aesthetics[i]), 3),
            "technical_percentile": round(float(technical_pct[i]), 3),
            "distinctiveness": round(float(novelty[i]), 6) if has_embedding else None,
            "distinctiveness_percentile": round(float(novelty_pct[i]), 3) if has_embedding else None,
            "viable": viable,
            "strengths": strengths,
            "uncertainties": uncertainties,
            "auto_flickr": False,
            "flickr": False,
            "auto_competition_rank": None,
            "competition_rank": None,
            "candidate_rank": None,
            "group_rank": 1,
            "suppressed_by": None,
            "diversity_adjustment": 0.0,
            "model_version": f.model_id,
            "embedding_provenance": f.data.get("embedding_provenance"),
            "ranking_version": VERSION,
            "flickr_origin": "manual" if f.flickr != "auto" else "automatic",
            "competition_origin": "manual" if f.competition != "auto" or f.manual_rank else "automatic",
        }
    order = sorted(frames, key=lambda f: (-output[f.id]["score"], f.filename.casefold(), f.id))
    groups = {}
    representatives = []
    group_anchors = {}
    capture_anchors = {}
    hash_bands = {}
    positions = {}

    def bands(f):
        if not f.phash:
            return []
        value = int(f.phash, 16)
        return [(part, (value >> (part * 13)) & ((1 << (12 if part == 4 else 13)) - 1)) for part in range(5)]

    for f in order:
        if f.group:
            groups.setdefault(f.group, []).append(f)
            output[f.id]["group_rank"] = len(groups[f.group])
        candidates = {other.id: other for key in bands(f) for other in hash_bands.get(key, [])}
        if f.group and f.group in group_anchors:
            candidates[group_anchors[f.group].id] = group_anchors[f.group]
        if f.raw_capture and f.raw_capture in capture_anchors:
            candidates[capture_anchors[f.raw_capture].id] = capture_anchors[f.raw_capture]
        duplicate = next(
            (
                other
                for other in sorted(candidates.values(), key=lambda p: positions[p.id])
                if same_frame(f, other)
            ),
            None,
        )
        if duplicate:
            output[f.id]["suppressed_by"] = duplicate.id
            output[f.id]["uncertainties"].append(
                f"Automatic alternative to {duplicate.filename}; similar-frame suppression."
            )
        else:
            positions[f.id] = len(representatives)
            representatives.append(f)
            if f.group:
                group_anchors.setdefault(f.group, f)
            if f.raw_capture:
                capture_anchors.setdefault(f.raw_capture, f)
            for key in bands(f):
                bucket = hash_bands.setdefault(key, [])
                if len(bucket) < 128:
                    bucket.append(f)
    pool = [f for f in representatives if output[f.id]["viable"]]

    def choose(available, selected):
        def adjusted(f):
            redundancy = max((similarity(f, other) for other in selected), default=0)
            penalty = cfg["diversity_penalty"] * max(0, (redundancy - 0.85) / 0.15)
            return output[f.id]["score"] - penalty, penalty

        best = min(available, key=lambda f: (-adjusted(f)[0], f.filename.casefold(), f.id))
        return best, round(adjusted(best)[1], 4)

    auto_top = []
    auto_pool = list(pool)
    while auto_pool and len(auto_top) < 3:
        selected, _ = choose(auto_pool, auto_top)
        auto_top.append(selected)
        auto_pool.remove(selected)
        output[selected.id]["auto_competition_rank"] = len(auto_top)

    finalists = {}
    for f in order:
        if f.manual_rank and f.competition != "reject":
            finalists[f.manual_rank] = f
    for slot in range(1, 4):
        if slot in finalists:
            continue
        chosen = list(finalists.values())
        available = [
            f
            for f in order
            if f.id not in {p.id for p in chosen}
            and f.competition not in ("reject", "alternative")
            and not any(same_frame(f, p) for p in chosen)
            and (output[f.id]["viable"] or f.competition == "include")
            and (not output[f.id]["suppressed_by"] or f.competition == "include")
        ]
        if not available and cfg["force_three"]:
            available = [
                f
                for f in order
                if f.id not in {p.id for p in chosen} and f.competition not in ("reject", "alternative")
            ]
        if available:
            selected, penalty = choose(available, chosen)
            finalists[slot] = selected
            output[selected.id]["diversity_adjustment"] = penalty
    for slot, f in finalists.items():
        output[f.id]["competition_rank"] = slot
        if not output[f.id]["viable"] or output[f.id]["suppressed_by"]:
            output[f.id]["uncertainties"].append("Included by explicit manual/Exactly three override.")
        if f.group:
            output[f.id]["strengths"].append(
                f"Highlights rank {output[f.id]['group_rank']} within its similarity group."
            )
    alternatives = [
        f
        for f in order
        if f.id not in {p.id for p in finalists.values()}
        and f.competition != "reject"
        and (output[f.id]["viable"] or f.competition in ("include", "alternative"))
        and (not output[f.id]["suppressed_by"] or f.competition in ("include", "alternative"))
    ]
    candidate_order = [finalists[k] for k in sorted(finalists)] + alternatives
    for index, f in enumerate(candidate_order, 1):
        output[f.id]["candidate_rank"] = index
    flickr = []
    for f in order:
        automatic = (
            f.lightroom
            and output[f.id]["technical"] >= cfg["technical_floor"]
            and f.aesthetic is not None
            and f.aesthetic >= cfg["flickr_aesthetic_floor"]
            and output[f.id]["aesthetic_percentile"] >= cfg["flickr_percentile"]
            and not any(same_frame(f, other) for other in flickr)
            and (cfg["flickr_max"] is None or len(flickr) < cfg["flickr_max"])
        )
        output[f.id]["auto_flickr"] = bool(automatic)
        if automatic:
            flickr.append(f)
        output[f.id]["flickr"] = f.lightroom and (f.flickr == "keep" or (f.flickr == "auto" and automatic))
        if f.flickr == "keep" and not f.lightroom:
            output[f.id]["uncertainties"].append(
                "Manual standout retained but inactive: excluded from Lightroom picks."
            )
    for index, f in enumerate([f for f in order if output[f.id]["flickr"]], 1):
        output[f.id]["flickr_rank"] = index
    return output, {
        "finalists": [finalists[k].id for k in sorted(finalists)],
        "alternatives": [f.id for f in alternatives],
        "flickr": [f.id for f in order if output[f.id]["flickr"]],
        "viable": len(pool),
    }
