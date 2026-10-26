import csv
import io

FIELDS = [
    "original_path",
    "relative_path",
    "filename",
    "overall_score",
    "aesthetic_score",
    "sharpness_metric",
    "exposure_metric",
    "ai_recommendation",
    "manual_decision",
    "final_selected",
    "star_rating",
    "similarity_group_id",
    "selection_rank",
    "selection_category",
    "portfolio_score",
    "flickr_rank",
    "competition_rank",
    "competition_candidate_rank",
    "flickr_manual_override",
    "competition_manual_override",
    "flickr_origin",
    "competition_origin",
    "scoring_model_version",
    "ranking_configuration_version",
    "ranking_algorithm_version",
    "measured_strengths",
    "uncertainties",
    "automatic_flickr",
    "automatic_competition_rank",
    "analysed_path",
    "analysed_filename",
    "analysis_provenance",
    "raw_mapping",
    "embedding_provenance",
    "exactly_three_override",
    "generic_portfolio_score",
    "taste_affinity",
    "taste_profile_version",
]


def make_csv(photos, category=None):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    for p in photos:
        use_raw = category is not None and p.get("raw_original_path") is not None
        original = p["raw_original_path"] if use_raw else p["original_path"]
        highlight = p.get("highlights") or {}
        categories = ["lightroom"] if p["selected"] else []
        if highlight.get("flickr"):
            categories.append("flickr")
        if highlight.get("competition_rank"):
            categories.append("competition")
        elif highlight.get("candidate_rank"):
            categories.append("competition_alternatives")
        writer.writerow(
            dict(
                zip(
                    FIELDS,
                    [
                        original,
                        p["raw_relative_path"] if use_raw else p["relative_path"],
                        p["raw_filename"] if use_raw else p["filename"],
                        p["score"],
                        p["aesthetic"],
                        p["calibrated"].get("sharpness"),
                        p["calibrated"].get("exposure"),
                        p["recommendation"],
                        p["decision"],
                        p["selected"],
                        p["stars"],
                        p["group_id"],
                        p["selection_rank"],
                        category or ";".join(categories),
                        highlight.get("score"),
                        highlight.get("flickr_rank"),
                        highlight.get("competition_rank"),
                        highlight.get("candidate_rank"),
                        highlight.get("flickr_decision", "auto"),
                        highlight.get("competition_decision", "auto"),
                        highlight.get("flickr_origin"),
                        highlight.get("competition_origin"),
                        p.get("model_id"),
                        highlight.get("configuration_version"),
                        highlight.get("ranking_version"),
                        "; ".join(highlight.get("strengths", [])),
                        "; ".join(highlight.get("uncertainties", [])),
                        highlight.get("auto_flickr", False),
                        highlight.get("auto_competition_rank"),
                        p["original_path"],
                        p["filename"],
                        p.get("provenance"),
                        (
                            "verified RAW capture"
                            if use_raw
                            else "original raster; no verified RAW association"
                        ),
                        highlight.get("embedding_provenance"),
                        highlight.get("forced_inclusion", False),
                        highlight.get("generic_score"),
                        p.get("taste_affinity"),
                        p.get("taste_version"),
                    ],
                    strict=True,
                )
            )
        )
    return stream.getvalue().encode("utf-8-sig")
