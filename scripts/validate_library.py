"""Validate a completed local library and write reviewable CSV artifacts outside its source."""

import argparse
import csv
import io
import json
import statistics
import time
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("library_id")
    parser.add_argument("--expected", type=int, required=True)
    parser.add_argument("--output", type=Path, default=Path(".local/exports"))
    args = parser.parse_args()
    base = "http://127.0.0.1:8765/api"

    def get(path):
        with urllib.request.urlopen(base + path, timeout=30) as response:
            return response.read()

    library = json.loads(get(f"/libraries/{args.library_id}"))
    assert library["ready"] == args.expected and library["failed"] == 0, library
    assert library["job"]["status"] == "complete"
    photos = []
    for page in range(1, (args.expected + 99) // 100 + 1):
        photos.extend(json.loads(get(f"/libraries/{args.library_id}/photos?limit=100&page={page}"))["items"])
    assert len(photos) == args.expected
    assert all(
        p["aesthetic"] is not None and p["provenance"] and Path(p["original_path"]).is_file() for p in photos
    )
    assert len({p["id"] for p in photos}) == args.expected
    assert all(p["thumbnail"] and get(p["thumbnail"][4:])[:2] == b"\xff\xd8" for p in photos[:3])
    output = args.output.resolve()
    source = Path(library["source"]).resolve()
    assert output != source and source not in output.parents, "Output must be outside the source folder"
    output.mkdir(parents=True, exist_ok=True)
    for filename, expected in [
        ("all_photos.csv", args.expected),
        ("selected_photos.csv", library["selected"]),
    ]:
        data = get(f"/libraries/{args.library_id}/export/{filename}")
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        assert len(rows) == expected
        assert all(Path(row["original_path"]).is_file() for row in rows)
        (output / filename).write_bytes(data)
    timings = []
    for _ in range(12):
        started = time.perf_counter()
        get(f"/libraries/{args.library_id}/photos?limit=48")
        timings.append(1000 * (time.perf_counter() - started))
    result = {
        "library_id": library["id"],
        "photos": len(photos),
        "selected": library["selected"],
        "failed": library["failed"],
        "ai_scored": sum(p["aesthetic"] is not None for p in photos),
        "similarity_groups": len({p["group_id"] for p in photos if p["group_id"]}),
        "protected_groups": len({p["group_id"] for p in photos if p["group_protected"]}),
        "provenance": sorted({p["provenance"] for p in photos}),
        "gallery_request_median_ms": round(statistics.median(timings), 2),
        "gallery_request_max_ms": round(max(timings), 2),
        "job": library["job"],
    }
    (output / "validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
