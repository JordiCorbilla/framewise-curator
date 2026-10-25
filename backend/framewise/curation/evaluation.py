"""Offline agreement metrics using automatic recommendations only, never manually corrected finalists."""

import math
import ntpath


def key(path):
    value = str(path).strip()
    return ntpath.normcase(ntpath.normpath(value)) if ntpath.splitdrive(value)[0] else value


def boolean(value):
    if str(value).strip().lower() in ("1", "true"):
        return True
    if str(value).strip().lower() in ("0", "false"):
        return False
    raise ValueError("Every favourite label must be explicitly true/false or 1/0; blanks are unlabelled")


def agreement(predictions, labels, split="heldout"):
    expected = {key(row["original_path"]): row for row in predictions}
    observed = {key(row["original_path"]): row for row in labels}
    if len(expected) != len(predictions) or len(observed) != len(labels):
        raise ValueError("Duplicate original paths in predictions or labels")
    if set(expected) != set(observed):
        raise ValueError(
            "Labels must cover exactly the prediction universe, including explicit negative labels"
        )
    parsed = {
        path: (boolean(row["flickr_favourite"]), boolean(row["competition_favourite"]))
        for path, row in observed.items()
    }
    universe = {path for path, row in observed.items() if row.get("split", "heldout") == split}
    if not universe:
        raise ValueError(f"No labelled photographs in split {split!r}")
    selected = {path for path in universe if boolean(expected[path]["automatic_flickr"])}
    favourite = {path for path in universe if parsed[path][0]}
    competition_favourites = {path for path in universe if parsed[path][1]}
    finalists = {}
    for path in universe:
        value = expected[path].get("automatic_competition_rank", "")
        if value:
            rank = int(value)
            if rank not in (1, 2, 3) or rank in finalists:
                raise ValueError("Automatic competition ranks must be unique 1–3 within one collection")
            finalists[rank] = path
    hits = len(selected & favourite)
    comp_hits = len(set(finalists.values()) & competition_favourites)
    precision = hits / len(selected) if selected else None
    recall = hits / len(favourite) if favourite else None
    dcg = sum(1 / math.log2(rank + 1) for rank, path in finalists.items() if path in competition_favourites)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(3, len(competition_favourites)) + 1))
    return {
        "split": split,
        "labelled_photographs": len(universe),
        "flickr_recommended": len(selected),
        "flickr_favourites": len(favourite),
        "flickr_overlap": hits,
        "flickr_precision": precision,
        "flickr_recall": recall,
        "flickr_f1": (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall
            else None
        ),
        "competition_recommended": len(finalists),
        "competition_favourites": len(competition_favourites),
        "competition_overlap_at3": comp_hits,
        "competition_precision_at3": comp_hits / len(finalists) if finalists else None,
        "competition_recall_at3": comp_hits / len(competition_favourites) if competition_favourites else None,
        "competition_ndcg_at3": dcg / ideal if ideal else None,
        "uses_automatic_recommendations_only": True,
    }
