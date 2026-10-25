from conftest import create_scanned
from PIL import ImageFilter

from framewise.curation.ranking import combined_score, recommend
from framewise.db.models import Library, Photo, PhotoMetadata, PhotoMetrics, Session, SimilarityGroup
from framewise.scoring.metrics import classical


def test_deterministic_metrics_and_blur(image):
    original = classical(image)
    assert original == classical(image)
    blurred = classical(image.filter(ImageFilter.GaussianBlur(5)))
    assert original[1]["sharpness"] > blurred[1]["sharpness"]
    assert 0 <= original[0]["highlight_clipping"] <= 1


def test_missing_model_is_not_fake_aesthetic():
    assert (
        combined_score(
            {"sharpness": 80, "exposure": 40}, None, {"aesthetic": 0.6, "sharpness": 0.25, "exposure": 0.15}
        )
        == 65
    )


def test_ranking_stability_and_duplicates(source):
    lib_id, _ = create_scanned(source)
    with Session.begin() as db:
        lib = db.get(Library, lib_id)
        photos = db.query(Photo).filter_by(library_id=lib_id).all()
        assert all(p.status == "ready" for p in photos)
        before = [(p.id, p.recommendation, p.selection_rank, p.group_id) for p in photos]
        recommend(db, lib)
        after = [(p.id, p.recommendation, p.selection_rank, p.group_id) for p in photos]
        assert before == after
        groups = db.query(SimilarityGroup).all()
        assert len(groups) == 1
        assert groups[0].count == 2
        assert not groups[0].protected


def test_brackets_protected(source):
    lib_id, _ = create_scanned(source)
    with Session.begin() as db:
        members = db.query(Photo).filter(Photo.group_id.is_not(None)).all()
        meta = db.get(PhotoMetadata, members[0].id)
        meta.data = {**meta.data, "ExposureCompensation": 1}
        db.flush()
        recommend(db, db.get(Library, lib_id))
        assert db.query(SimilarityGroup).one().protected


def test_missing_aesthetic_is_stored_null(source):
    create_scanned(source)
    with Session() as db:
        assert all(m.aesthetic is None and m.model_id is None for m in db.query(PhotoMetrics))
