import csv
import io
import threading

import numpy as np
import pytest
from conftest import create_scanned

from framewise.curation.highlights import rebuild
from framewise.curation.standouts import Frame, rank
from framewise.db.models import (
    HighlightDecision,
    HighlightFeedback,
    Library,
    Photo,
    PhotoMetrics,
    ScanJob,
    Session,
    initialize,
)
from framewise.workers.scan import ScanManager


def frame(index, aesthetic=8, **kwargs):
    hashes = [
        "0000000000000000",
        "ffffffffffffffff",
        "aaaaaaaaaaaaaaaa",
        "5555555555555555",
        "00000000ffffffff",
        "ffffffff00000000",
    ]
    return Frame(
        id=str(index),
        filename=f"frame-{index}.NEF",
        aesthetic=aesthetic,
        sharpness=75,
        exposure=95,
        phash=hashes[index],
        lightroom=True,
        **kwargs,
    )


def test_top_three_are_stable_and_independent_of_input_order():
    frames = [frame(0, 8.5), frame(1, 8), frame(2, 7.5), frame(3, 7)]
    results, summary = rank(frames)
    assert summary["finalists"] == ["0", "1", "2"]
    assert summary["alternatives"] == ["3"]
    assert rank(list(reversed(frames))) == (results, summary)


@pytest.mark.parametrize("count", [0, 1, 2])
def test_fewer_than_three_are_not_fabricated(count):
    _, summary = rank([frame(i) for i in range(count)])
    assert len(summary["finalists"]) == count


def test_quality_floor_and_explicit_exactly_three():
    frames = [frame(i, 3) for i in range(4)]
    assert rank(frames)[1]["finalists"] == []
    results, summary = rank(frames, {"force_three": True})
    assert len(summary["finalists"]) == 3
    assert all(
        any("override" in text for text in results[key]["uncertainties"]) for key in summary["finalists"]
    )
    assert not summary["flickr"]


def test_similar_frames_do_not_fill_automatic_top_three():
    frames = [frame(0, 9, group="burst"), frame(1, 8.9, group="burst"), frame(2, 8)]
    results, summary = rank(frames)
    assert summary["finalists"] == ["0", "2"]
    assert results["1"]["suppressed_by"] == "0"


def test_distinct_compositions_in_uncertain_group_remain_eligible():
    _, summary = rank(
        [
            frame(0, 8, group="uncertain", protected=True),
            frame(1, 7.8, group="uncertain", protected=True),
            frame(2, 7.5),
        ]
    )
    assert len(summary["finalists"]) == 3


def test_embedding_diversity_is_a_soft_reranking_signal():
    a = np.zeros(512, dtype=np.float32)
    a[0] = 1
    b = a.copy()
    b[1], b[0] = 0.1, np.sqrt(0.99)
    c = np.zeros(512, dtype=np.float32)
    c[2] = 1
    frames = [
        frame(0, embedding=a, model_id="fixture"),
        frame(1, embedding=b, model_id="fixture"),
        frame(2, embedding=c, model_id="fixture"),
    ]
    results, summary = rank(
        frames,
        {"aesthetic_weight": 0, "technical_weight": 1, "distinctiveness_weight": 0, "diversity_penalty": 8},
    )
    assert summary["finalists"] == ["0", "2", "1"]
    assert results["1"]["diversity_adjustment"] > 0
    assert results["2"]["distinctiveness"] > results["0"]["distinctiveness"]


def test_flickr_threshold_cap_and_lightroom_subset():
    frames = [frame(0, 8.5), frame(1, 8), frame(2, 7.5)]
    assert rank(frames, {"flickr_percentile": 0, "flickr_max": 1})[1]["flickr"] == ["0"]
    assert rank(frames, {"aesthetic_floor": 9.9})[1]["flickr"] == ["0"]
    frames[0].lightroom = False
    frames[0].flickr = "keep"
    result, summary = rank(frames)
    assert not result["0"]["flickr"] and not summary["flickr"]
    assert result["0"]["flickr_origin"] == "manual"


def test_missing_aesthetic_never_implies_exceptional_quality():
    frames = [frame(i, None) for i in range(3)]
    assert not rank(frames)[1]["finalists"]
    assert len(rank(frames, {"force_three": True})[1]["finalists"]) == 3
    assert any("unavailable" in text for text in rank(frames)[0]["0"]["strengths"])


def test_raw_and_edited_jpeg_cannot_occupy_two_automatic_finalist_slots():
    first = frame(0, 8.5, raw_capture="capture-a")
    edited = frame(1, 9, raw_capture="capture-a")
    third = frame(2, 8, raw_capture="capture-b")
    result, summary = rank([first, edited, third])
    assert summary["finalists"] == ["1", "2"]
    assert result["0"]["suppressed_by"] == "1"


def test_raw_handoff_requires_unique_stem_timestamp_and_camera(client, ranked):
    from pathlib import Path

    from framewise.db.models import PhotoMetadata

    with Session.begin() as db:
        photos = db.query(Photo).filter_by(library_id=ranked).order_by(Photo.filename).all()
        jpeg, raw = photos[:2]
        raw.filename = Path(jpeg.filename).stem + ".NEF"
        raw.relative_path = raw.filename
        for p in (jpeg, raw):
            db.get(PhotoMetadata, p.id).data = {
                "DateTimeOriginal": "2026:10:18 12:00:00",
                "Model": "NIKON D850",
            }
        db.flush()
        rebuild(db, db.get(Library, ranked))
        jpeg_id, raw_id, raw_name = jpeg.id, raw.id, raw.filename
    paired = client.get(f"/api/photos/{jpeg_id}").json()
    assert paired["raw_filename"] == raw_name
    client.patch(f"/api/photos/{jpeg_id}/highlights", json={"flickr": "keep", "include_lightroom": True})
    rows = list(
        csv.DictReader(
            io.StringIO(
                client.get(f"/api/libraries/{ranked}/export/flickr_standouts.csv").content.decode("utf-8-sig")
            )
        )
    )
    record = next(row for row in rows if row["analysed_path"] == paired["original_path"])
    assert record["filename"] == raw_name and record["original_path"] == paired["raw_original_path"]
    assert record["analysed_filename"] == paired["filename"]
    with Session.begin() as db:
        db.get(PhotoMetadata, raw_id).data = {
            "DateTimeOriginal": "2026:10:18 12:01:00",
            "Model": "NIKON D850",
        }
        db.flush()
        rebuild(db, db.get(Library, ranked))
    assert client.get(f"/api/photos/{jpeg_id}").json()["raw_original_path"] is None


def test_pairwise_comparison_uses_actual_hashes_and_validates_collection(client, ranked):
    photos = client.get(f"/api/libraries/{ranked}/photos").json()["items"]
    response = client.get(
        f"/api/libraries/{ranked}/highlights/compare?left={photos[0]['id']}&right={photos[1]['id']}"
    )
    assert response.status_code == 200
    assert 0 <= response.json()["phash_distance"] <= 64
    assert response.json()["cosine_similarity"] is None
    assert (
        client.get(
            f"/api/libraries/{ranked}/highlights/compare?left=missing&right={photos[1]['id']}"
        ).status_code
        == 404
    )


@pytest.fixture
def ranked(source, image):
    for i in range(3):
        image.save(source / f"extra-{i}.jpg")
    library_id, _ = create_scanned(source)
    with Session.begin() as db:
        photos = db.query(Photo).filter_by(library_id=library_id).order_by(Photo.filename).all()
        rng = np.random.default_rng(17)
        for i, photo in enumerate(photos):
            metrics = db.get(PhotoMetrics, photo.id)
            metrics.aesthetic, metrics.model_id = 9 - i * 0.2, "synthetic-test-measurements"
            metrics.calibrated = {"sharpness": 80 - i, "exposure": 95, "focus_risk": "fixture"}
            photo.phash = f"{int(rng.integers(0, 2**64, dtype=np.uint64)):016x}"
            photo.group_id, photo.group_rank = None, None
            photo.recommendation = "pick"
        db.flush()
        rebuild(db, db.get(Library, library_id))
    return library_id


def test_manual_replacement_promotion_and_feedback(client, ranked):
    before = client.get(f"/api/libraries/{ranked}/highlights").json()
    assert len(before["finalists"]) == 3
    replacement = before["alternatives"][0]
    response = client.put(
        f"/api/libraries/{ranked}/highlights/finalists/1", json={"photo_id": replacement["id"]}
    )
    assert response.status_code == 200
    after = response.json()
    assert after["finalists"][0]["id"] == replacement["id"]
    assert before["finalists"][0]["id"] in {p["id"] for p in after["alternatives"]}
    third = after["finalists"][2]
    swap = client.put(
        f"/api/libraries/{ranked}/highlights/finalists/1", json={"photo_id": third["id"]}
    ).json()
    assert swap["finalists"][0]["id"] == third["id"]
    assert swap["finalists"][2]["id"] == replacement["id"]
    initialize()
    assert client.get(f"/api/libraries/{ranked}/highlights").json()["finalists"] == swap["finalists"]
    with Session() as db:
        assert db.query(HighlightFeedback).filter_by(library_id=ranked).count() >= 4


def test_flickr_feedback_and_rescan_preserve_manual_choices(client, ranked):
    before = client.get(f"/api/libraries/{ranked}/highlights").json()
    photo = before["finalists"][0]
    response = client.patch(f"/api/photos/{photo['id']}/highlights", json={"flickr": "reject"})
    assert response.status_code == 200
    assert photo["id"] not in {p["id"] for p in response.json()["flickr"]}
    client.put(f"/api/libraries/{ranked}/highlights/finalists/1", json={"photo_id": photo["id"]})
    with Session.begin() as db:
        job = ScanJob(library_id=ranked)
        db.add(job)
        db.flush()
        job_id = job.id
    ScanManager().run(job_id, threading.Event())
    with Session() as db:
        manual = db.get(HighlightDecision, photo["id"])
        assert manual.flickr == "reject" and manual.competition_rank == 1


def test_exports_filters_configuration_and_original_paths(client, ranked):
    for filename, count in [
        ("lightroom_picks.csv", 6),
        ("competition_top3.csv", 3),
        ("competition_alternatives.csv", 3),
        ("flickr_standouts.csv", 1),
    ]:
        response = client.get(f"/api/libraries/{ranked}/export/{filename}")
        assert response.status_code == 200
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        assert len(rows) == count
        assert all(
            row["selection_category"] and row["original_path"] and row["ranking_configuration_version"]
            for row in rows
        )
        if filename == "competition_top3.csv":
            assert [row["competition_rank"] for row in rows] == ["1", "2", "3"]
    for key, count in [("lightroom", 6), ("competition", 3), ("competition_alternatives", 3), ("flickr", 1)]:
        assert client.get(f"/api/libraries/{ranked}/photos?filter={key}").json()["total"] == count
    assert (
        client.patch(f"/api/libraries/{ranked}/highlights/config", json={"mode": "architecture"}).status_code
        == 422
    )
    update = client.patch(
        f"/api/libraries/{ranked}/highlights/config", json={"flickr_percentile": 0, "flickr_max": 2}
    )
    assert update.status_code == 200 and len(update.json()["flickr"]) == 2
    assert client.get(f"/api/libraries/{ranked}/highlights/search?q=extra").json()["total"] == 3
    uncapped = client.patch(
        f"/api/libraries/{ranked}/highlights/config", json={"flickr_percentile": 0, "flickr_max": None}
    ).json()
    assert uncapped["summary"]["flickr_count"] == 6
    second = client.get(f"/api/libraries/{ranked}/highlights?flickr_page=2").json()
    assert not second["flickr"] and second["summary"]["flickr_count"] == 6


def test_incomplete_scan_blocks_final_rankings_and_exports(client, ranked):
    with Session.begin() as db:
        db.add(ScanJob(library_id=ranked, status="running"))
        db.flush()
        rebuild(db, db.get(Library, ranked))
    response = client.get(f"/api/libraries/{ranked}/highlights").json()
    assert response["status"] == "waiting" and not response["finalists"]
    assert client.get(f"/api/libraries/{ranked}/export/competition_top3.csv").status_code == 409
    assert client.get(f"/api/libraries/{ranked}/photos?filter=competition").json()["total"] == 0
    assert (
        client.post(f"/api/libraries/{ranked}/highlights/recalculate", json={}).json()["status"] == "waiting"
    )


def test_flickr_keep_is_explicit_about_lightroom_inclusion(client, ranked):
    photo = client.get(f"/api/libraries/{ranked}/photos").json()["items"][0]
    client.patch(f"/api/photos/{photo['id']}/decision", json={"decision": "reject"})
    client.patch(f"/api/photos/{photo['id']}/highlights", json={"flickr": "keep"})
    assert not client.get(f"/api/photos/{photo['id']}").json()["highlights"]["flickr"]
    client.patch(f"/api/photos/{photo['id']}/highlights", json={"flickr": "keep", "include_lightroom": True})
    after = client.get(f"/api/photos/{photo['id']}").json()
    assert after["selected"] and after["highlights"]["flickr"]
