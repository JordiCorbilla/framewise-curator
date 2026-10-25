import csv
import io

FIELDS = ["original_path", "relative_path", "filename", "overall_score", "aesthetic_score", "sharpness_metric",
          "exposure_metric", "ai_recommendation", "manual_decision", "final_selected", "star_rating",
          "similarity_group_id", "selection_rank"]


def make_csv(photos):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    for p in photos:
        writer.writerow(dict(zip(FIELDS, [p["original_path"], p["relative_path"], p["filename"], p["score"],
                                         p["aesthetic"], p["calibrated"].get("sharpness"),
                                         p["calibrated"].get("exposure"), p["recommendation"], p["decision"],
                                         p["selected"], p["stars"], p["group_id"], p["selection_rank"]], strict=True)))
    return stream.getvalue().encode("utf-8-sig")
