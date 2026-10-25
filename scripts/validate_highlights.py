"""Read local acceptance evidence; rerank without inference and export reviewable category CSVs."""

import argparse
import csv
import io
import json
import math
import sys
import time
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("library_id")
    parser.add_argument("--output", type=Path, default=Path(".local/highlights"))
    parser.add_argument("--require-nef", action="store_true")
    args = parser.parse_args()
    base = "http://127.0.0.1:8765/api"

    def request(path, post=False):
        req = urllib.request.Request(
            base + path,
            data=b"{}" if post else None,
            headers={"Content-Type": "application/json"} if post else {},
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.read()

    library = json.loads(request(f"/libraries/{args.library_id}"))
    highlights = json.loads(request(f"/libraries/{args.library_id}/highlights"))
    assert highlights["status"] == "ready", highlights
    output = args.output.resolve()
    source = Path(library["source"]).resolve()
    assert output != source and source not in output.parents, (
        "Write validation outside the source folder"
    )
    output.mkdir(parents=True, exist_ok=True)
    final_ids = [p["id"] for p in highlights["finalists"]]
    raw_paths = [
        p["raw_original_path"] or p["original_path"] for p in highlights["finalists"]
    ]
    assert len(final_ids) <= 3 and len(set(final_ids)) == len(final_ids)
    assert all(p["selected"] for p in highlights["flickr"])
    timings = []
    for _ in range(2):
        started = time.perf_counter()
        repeated = json.loads(
            request(f"/libraries/{args.library_id}/highlights/recalculate", True)
        )
        timings.append(time.perf_counter() - started)
        assert [p["id"] for p in repeated["finalists"]] == final_ids
        assert [p["id"] for p in repeated["flickr"]] == [
            p["id"] for p in highlights["flickr"]
        ]
        assert (
            repeated["summary"]["alternatives"] == highlights["summary"]["alternatives"]
        )
    expected = {
        "lightroom_picks.csv": library["selected"],
        "flickr_standouts.csv": highlights["summary"]["flickr_count"],
        "competition_top3.csv": len(final_ids),
        "competition_alternatives.csv": len(highlights["summary"]["alternatives"]),
        "all_photos.csv": library["total"],
    }
    counts = {}
    for filename, count in expected.items():
        data = request(f"/libraries/{args.library_id}/export/{filename}")
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        assert len(rows) == count, (filename, len(rows), count)
        assert all(Path(row["original_path"]).is_file() for row in rows)
        if args.require_nef and filename != "all_photos.csv":
            assert all(row["filename"].lower().endswith(".nef") for row in rows)
        if filename == "competition_top3.csv":
            assert [int(row["competition_rank"]) for row in rows] == [
                p["highlights"]["competition_rank"] for p in highlights["finalists"]
            ]
        (output / filename).write_bytes(data)
        counts[filename] = len(rows)
    comparison = None
    if len(final_ids) >= 2:
        comparison = json.loads(
            request(
                f"/libraries/{args.library_id}/highlights/compare?"
                f"left={final_ids[0]}&right={final_ids[1]}"
            )
        )
        cosine = comparison["cosine_similarity"]
        assert cosine is None or math.isfinite(cosine) and -1 <= cosine <= 1
    result = {
        "library_id": args.library_id,
        "photos": library["total"],
        "ready": library["ready"],
        "summary": highlights["summary"],
        "configuration": highlights["config"],
        "exports": counts,
        "finalists": [
            {
                "rank": p["highlights"]["competition_rank"],
                "analysed": p["filename"],
                "raw_filename": p["raw_filename"],
                "relative_score": p["highlights"]["score"],
            }
            for p in highlights["finalists"]
        ],
        "unique_finalist_raw_captures": len(set(raw_paths)),
        "repeat_rankings_identical": True,
        "rerank_seconds": [round(t, 3) for t in timings],
        "comparison": comparison,
        "user_favourite_agreement": "Not measured: explicit human labels are required",
    }
    (output / "validation.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ("summary", "configuration")},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
