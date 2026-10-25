import io
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from PIL import Image

from framewise.imaging import acquisition as acq


def test_discovery_extensions_recursive(source):
    (source / "camera.NEF").write_bytes(b"fixture")
    assert len(list(acq.discover(source))) == 4
    assert len(list(acq.discover(source, False))) == 3
    assert {p.suffix.lower() for p in acq.discover(source)} == acq.SUPPORTED - {".jpg"} | {".jpg"}


def test_path_escape_rejected(source):
    with pytest.raises(ValueError):
        acq.source_path(source, "../private.jpg")


def test_exiftool_metadata(monkeypatch, tmp_path):
    monkeypatch.setattr(acq, "exiftool_path", lambda: "exiftool")
    data = {"Orientation": 6, "DateTimeOriginal": "2026:10:18 11:12:13", "Model": "NIKON"}
    monkeypatch.setattr(
        acq.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=json.dumps([data]).encode())
    )
    assert acq.read_metadata(tmp_path / "camera.nef") == data


def test_exif_pillow_orientation(monkeypatch, tmp_path, image):
    monkeypatch.setattr(acq, "exiftool_path", lambda: None)
    exif = Image.Exif()
    exif[274] = 6
    path = tmp_path / "rotated.jpg"
    image.save(path, exif=exif)
    assert acq.read_metadata(path)["Orientation"] == 6
    decoded, provenance = acq.decode(path, {})
    assert decoded.size == (240, 360)
    assert provenance == "original raster"


@pytest.mark.parametrize(
    "orientation,size", [(1, (360, 240)), (3, (360, 240)), (6, (240, 360)), (8, (240, 360))]
)
def test_orientation(image, orientation, size):
    assert acq.orient(image, orientation).size == size


def test_embedded_preview_largest_and_fallback(monkeypatch, tmp_path, image):
    monkeypatch.setattr(acq, "exiftool_path", lambda: "exiftool")

    def result(args, **kwargs):
        buffer = io.BytesIO()
        if "-JpgFromRaw" in args:
            return SimpleNamespace(returncode=0, stdout=b"")
        candidate = image if "-PreviewImage" in args else image.resize((60, 40))
        candidate.save(buffer, "JPEG")
        return SimpleNamespace(returncode=0, stdout=buffer.getvalue())

    monkeypatch.setattr(acq.subprocess, "run", result)
    decoded, provenance = acq.decode(tmp_path / "test.nef", {"Orientation": 6})
    assert decoded.size == (240, 360)
    assert "PreviewImage" in provenance


def test_rawpy_fallback(monkeypatch, tmp_path):
    import numpy as np

    monkeypatch.setattr(acq, "exiftool_path", lambda: None)

    class Raw:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def postprocess(self, **kwargs):
            return np.zeros((40, 60, 3), dtype=np.uint8)

    monkeypatch.setitem(sys.modules, "rawpy", SimpleNamespace(imread=lambda p: Raw()))
    im, provenance = acq.decode(tmp_path / "test.nef", {})
    assert im.size == (60, 40)
    assert "developed RAW" in provenance


def test_corrupt_nef_does_not_decode(tmp_path):
    path = tmp_path / "broken.nef"
    path.write_bytes(b"broken file")
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        acq.acquire(path, "test", "corrupt")


def test_jpeg_cache_outside_originals(source):
    original = next(source.glob("*.JPG"))
    before = original.read_bytes()
    im, metadata, provenance, width, height = acq.acquire(original, "test", "jpeg")
    assert (width, height) == (360, 240)
    assert im.size == (360, 240)
    assert original.read_bytes() == before
    for p in acq.cache_paths("test", "jpeg"):
        assert p.exists() and source not in p.parents


def test_cache_identity_model_and_modification(source):
    path = next(source.glob("*.JPG"))
    first = acq.identity(path, "model-a")
    assert first == acq.identity(path, "model-a")
    assert first != acq.identity(path, "model-b")
    path.write_bytes(path.read_bytes() + b"extra")
    assert first != acq.identity(path, "model-a")
