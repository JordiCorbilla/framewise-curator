"""Create blank favourite-label templates and evaluate offline, without photographs or model execution."""

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from framewise.curation.evaluation import agreement  # noqa: E402


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or any(
        "automatic_flickr" not in row or "automatic_competition_rank" not in row for row in rows
    ):
        raise ValueError("Use a current all_photos.csv export containing automatic recommendation fields")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["template", "evaluate"])
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--split", default="heldout")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Choose a new output filename; existing evaluations/labels are never overwritten")
    predictions = read(args.predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.mode == "template":
        if args.output.suffix.lower() != ".csv":
            raise ValueError("Label templates must use a .csv extension")
        with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
            fields = ["original_path", "relative_path", "flickr_favourite", "competition_favourite", "split"]
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for row in predictions:
                writer.writerow(
                    {
                        "original_path": row["original_path"],
                        "relative_path": row["relative_path"],
                        "flickr_favourite": "",
                        "competition_favourite": "",
                        "split": "heldout",
                    }
                )
        print(f"Created {len(predictions)} blank labels. Review photographs and fill every true/false value.")
        return
    if args.labels is None or args.output.suffix.lower() != ".json":
        raise ValueError("Evaluation requires --labels and a new .json output")
    with args.labels.open(encoding="utf-8-sig", newline="") as stream:
        labels = list(csv.DictReader(stream))
    result = agreement(predictions, labels, args.split)
    result.update(
        predictions_sha256=hashlib.sha256(args.predictions.read_bytes()).hexdigest(),
        labels_sha256=hashlib.sha256(args.labels.read_bytes()).hexdigest(),
        model_versions=sorted({r["scoring_model_version"] for r in predictions}),
        ranking_configurations=sorted({r["ranking_configuration_version"] for r in predictions}),
        notice="Agreement with human favourites, not prediction of engagement or competition results. "
        "Precision uses actually recommended frames (up to three); null means undefined. "
        "Keep historical evaluation trips held out when changing ranking weights.",
    )
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
