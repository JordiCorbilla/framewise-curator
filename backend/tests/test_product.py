import hashlib

import numpy as np
from conftest import create_scanned

from framewise.core.config import CACHE
from framewise.curation.highlights import rebuild
from framewise.curation.ranking import recommend
from framewise.curation.taste import affinity, ensure_current, examples, fit
from framewise.db.models import (
    Library,
    Photo,
    PhotoEmbedding,
    PhotoMetrics,
    ScanJob,
    Session,
    TasteLabel,
    TasteProfile,
    initialize,
)


def taste_fixture(source):
    with Session.begin() as db:
        library = Library(name="Taste fixture", source=str(source))
        db.add(library)
        db.flush()
        rng = np.random.default_rng(42)
        for i in range(24):
            value = 1 if i < 12 else -1
            vector = rng.normal(0, 0.02, 512).astype(np.float32)
            vector[0] = value
            vector /= np.linalg.norm(vector)
            photo = Photo(
                id=f"taste-{i:02}",
                library_id=library.id,
                relative_path=f"frame-{i}.jpg",
                filename=f"frame-{i}.jpg",
                status="ready",
                identity="fixture-v1",
                width=360,
                height=240,
                phash=None,
            )
            db.add(photo)
            db.flush()
            db.add(
                PhotoMetrics(
                    photo_id=photo.id,
                    model_id="fixture-encoder",
                    aesthetic=8,
                    calibrated={"sharpness": 80, "exposure": 90},
                    raw={},
                )
            )
            db.add(
                PhotoEmbedding(
                    photo_id=photo.id,
                    model_id="fixture-encoder",
                    identity="fixture-v1",
                    vector=vector.tobytes(),
                    provenance="synthetic test fixture",
                )
            )
            db.add(TasteLabel(photo_id=photo.id, value=value))
        db.add(ScanJob(library_id=library.id, status="complete"))
        db.flush()
        recommend(db, library)
        rebuild(db, library)
        return library.id


def test_collection_rename_and_permanent_removal_preserve_originals(client, source):
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob("*") if p.is_file()}
    library_id, _ = create_scanned(source)
    with Session.begin() as db:
        db.add(TasteLabel(photo_id=db.query(Photo).filter_by(library_id=library_id).first().id, value=1))
        db.add(TasteProfile(id="local", enabled=True, data={"status": "trained", "direction": [1]}))
    assert client.patch(f"/api/libraries/{library_id}", json={"name": "   "}).status_code == 422
    renamed = client.patch(f"/api/libraries/{library_id}", json={"name": "NY — favourites"})
    assert renamed.json()["name"] == "NY — favourites"
    assert (
        client.request("DELETE", f"/api/libraries/{library_id}", json={"confirm_name": "wrong"}).status_code
        == 422
    )
    assert (CACHE / library_id).exists()
    response = client.request(
        "DELETE", f"/api/libraries/{library_id}", json={"confirm_name": "NY — favourites"}
    )
    assert response.status_code == 200, response.text
    assert not (CACHE / library_id).exists()
    assert client.get(f"/api/libraries/{library_id}").status_code == 404
    with Session() as db:
        assert db.query(Photo).count() == db.query(TasteLabel).count() == 0
        assert db.get(TasteProfile, "local").data == {}
        assert not db.get(TasteProfile, "local").enabled
    assert before == {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob("*") if p.is_file()
    }


def test_removal_blocks_active_scan_and_foreign_origin(client, source):
    library_id = client.post("/api/libraries", json={"source": str(source)}).json()["id"]
    with Session.begin() as db:
        db.add(ScanJob(library_id=library_id, status="running"))
    assert (
        client.request(
            "DELETE", f"/api/libraries/{library_id}", json={"confirm_name": source.name}
        ).status_code
        == 409
    )
    assert (
        client.request(
            "DELETE",
            f"/api/libraries/{library_id}",
            json={"confirm_name": source.name},
            headers={"Origin": "https://external.invalid"},
        ).status_code
        == 403
    )
    assert source.exists()


def test_preference_cold_start_does_not_claim_learning(client, source):
    library_id, _ = create_scanned(source)
    photo = client.get(f"/api/libraries/{library_id}/photos").json()["items"][0]
    assert client.post("/api/taste/train", json={}).status_code == 409
    assert client.patch("/api/taste", json={"enabled": True}).status_code == 409
    # Keep and ratings never become taste labels.
    client.patch(f"/api/photos/{photo['id']}/decision", json={"decision": "keep", "stars": 5})
    assert client.get("/api/taste").json()["labels"] == 0
    assert client.patch(f"/api/photos/{photo['id']}/taste", json={"value": -1}).status_code == 200
    info = client.get("/api/taste").json()
    assert info["labels"] == 1 and info["usable_dislikes"] == 0  # no embedding
    assert client.get(f"/api/photos/{photo['id']}").json()["decision"] == "keep"
    assert client.patch(f"/api/photos/{photo['id']}/taste", json={"value": 3}).status_code == 422


def test_real_training_holdout_apply_pause_and_forget(client, source):
    library_id = taste_fixture(source)
    trained = client.post("/api/taste/train", json={})
    assert trained.status_code == 200, trained.text
    data = trained.json()
    assert data["status"] == "trained" and data["eligible"] and not data["enabled"]
    assert data["training_count"] == 18 and data["heldout_count"] == 6
    assert data["heldout_balanced_accuracy"] == 1
    assert client.patch("/api/taste", json={"enabled": True}).json()["enabled"]
    with Session() as db:
        profile = db.get(TasteProfile, "local")
        assert not set(profile.data["training_ids"]) & set(profile.data["heldout_ids"])
        version = profile.data["version"]
        assert db.get(Photo, "taste-00").score > db.get(Photo, "taste-23").score
    initialize()
    assert client.get("/api/taste").json()["version"] == version
    assert client.get("/api/taste").json()["enabled"]
    # Editing labels disables and erases the old profile before a fresh explicit training run.
    client.patch("/api/photos/taste-00/taste", json={"value": -1})
    info = client.get("/api/taste").json()
    assert not info["enabled"] and info["status"] == "collecting"
    assert client.get(f"/api/libraries/{library_id}/photos").json()["total"] == 24
    assert client.request("DELETE", "/api/taste", json={}).status_code == 200
    assert client.get("/api/taste").json()["labels"] == 0


def test_duplicate_label_groups_are_not_training_leakage(source):
    taste_fixture(source)
    with Session.begin() as db:
        db.get(Photo, "taste-00").phash = "0000000000000000"
        db.get(Photo, "taste-01").phash = "0000000000000001"
        db.get(Photo, "taste-12").phash = "0000000000000003"
        db.flush()
        samples, conflicts = examples(db)
        assert conflicts == 1 and len(samples) == 21
        assert not any(s["photo_id"] in {"taste-00", "taste-01", "taste-12"} for s in samples)


def test_learner_is_deterministic_and_rejects_mismatched_encoder(source):
    taste_fixture(source)
    with Session() as db:
        samples, _ = examples(db)
        data = fit(samples)
        assert fit(list(reversed(samples))) == data
        profile = TasteProfile(data=data, enabled=True)
        assert affinity(profile, samples[0]["vector"], "another-encoder") is None
        assert affinity(profile, samples[0]["vector"], "fixture-encoder") is not None
        profile.enabled = False
        assert affinity(profile, samples[0]["vector"], "fixture-encoder") is None


def test_changed_source_invalidates_previously_trained_preferences(client, source):
    taste_fixture(source)
    client.post("/api/taste/train", json={})
    client.patch("/api/taste", json={"enabled": True})
    with Session.begin() as db:
        db.get(Photo, "taste-00").identity = "changed-source"
        db.flush()
        assert ensure_current(db)
        assert not db.get(TasteProfile, "local").enabled
        assert db.get(TasteProfile, "local").data == {}


def test_failed_cache_removal_does_not_remove_collection(client, source, monkeypatch):
    import framewise.api.collections as collections

    library_id, _ = create_scanned(source)

    def locked(_):
        raise PermissionError("preview is open")

    monkeypatch.setattr(collections.shutil, "rmtree", locked)
    name = client.get(f"/api/libraries/{library_id}").json()["name"]
    response = client.request("DELETE", f"/api/libraries/{library_id}", json={"confirm_name": name})
    assert response.status_code == 409
    assert client.get(f"/api/libraries/{library_id}").json()["total"] == 3
    assert (CACHE / library_id).exists() and source.exists()
