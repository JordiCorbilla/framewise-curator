import os
import tempfile
from pathlib import Path

os.environ["FRAMEWISE_DATA_DIR"] = tempfile.mkdtemp(prefix="framewise-tests-")

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from framewise.api.app import app  # noqa: E402
from framewise.db.models import Base, engine  # noqa: E402
from framewise.scoring.aesthetic import analyzer  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(analyzer, "status", lambda: {"status": "download_required"})
    monkeypatch.setattr(analyzer, "model_id", lambda: "classical-only-v1")
    yield
    from framewise.imaging.exiftool import close_all

    close_all()


@pytest.fixture
def image():
    rng = np.random.default_rng(21)
    return Image.fromarray(rng.integers(0, 256, size=(240, 360, 3), dtype=np.uint8))


@pytest.fixture
def source(tmp_path, image):
    folder = tmp_path / "Photos, café"
    folder.mkdir()
    image.save(folder / "frame, 你好.JPG")
    image.save(folder / "duplicate.jpeg")
    (folder / "nested").mkdir()
    image.rotate(90, expand=True).save(folder / "nested/portrait.PNG")
    (folder / "ignored.txt").write_text("not a photograph")
    return folder


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


def create_scanned(source: Path):
    import threading

    from framewise.db.models import Library, ScanJob, Session
    from framewise.workers.scan import ScanManager

    with Session.begin() as db:
        library = Library(source=str(source), name="Generated fixture")
        db.add(library)
        db.flush()
        job = ScanJob(library_id=library.id)
        db.add(job)
        db.flush()
        library_id, job_id = library.id, job.id
    ScanManager().run(job_id, threading.Event())
    return library_id, job_id
