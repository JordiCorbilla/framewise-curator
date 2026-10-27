import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from framewise.core.folders import display_path, verify_mount_identity
from framewise.db.models import Library, ScanJob, Session
from framewise.workers.models import ModelInstaller, installer


def test_browse_choose_folder_filter_and_no_escape(client, source, monkeypatch):
    monkeypatch.setenv("FRAMEWISE_PHOTO_ROOTS", json.dumps([str(source)]))
    locations = client.get("/api/folders").json()
    assert locations["restricted"] and locations["items"][0]["path"] == str(source.resolve())
    root = client.get("/api/folders", params={"path": str(source)}).json()
    assert root["parent"] is None and [item["name"] for item in root["items"]] == ["nested"]
    assert client.get("/api/folders", params={"path": str(source), "q": "NO MATCH"}).json()["items"] == []
    assert client.get("/api/folders", params={"path": str(source / "nested")}).json()["parent"] == str(
        source.resolve()
    )
    assert client.get("/api/folders", params={"path": str(source / "..")}).status_code == 403
    assert client.post("/api/libraries", json={"source": str(source.parent)}).status_code == 403
    assert client.post("/api/libraries", json={"source": str(source / "nested")}).status_code == 200
    assert client.get("/api/folders", params={"path": str(source / "not-there")}).status_code == 404
    assert client.get("/api/folders?page=0").status_code == 422


def test_folder_pagination_hides_files_and_dotfolders(client, source, monkeypatch):
    monkeypatch.setenv("FRAMEWISE_PHOTO_ROOTS", json.dumps([str(source)]))
    for n in range(105):
        (source / f"Trip-{n:03}").mkdir()
    (source / ".hidden").mkdir()
    first = client.get("/api/folders", params={"path": str(source)}).json()
    second = client.get("/api/folders", params={"path": str(source), "page": 2}).json()
    assert first["total"] == 106 and len(first["items"]) == 100 and len(second["items"]) == 6
    assert not {i["path"] for i in first["items"]} & {i["path"] for i in second["items"]}


def test_host_original_paths_and_mount_identity(source, tmp_path, monkeypatch):
    monkeypatch.setenv("FRAMEWISE_PHOTO_ROOTS", json.dumps([str(source)]))
    monkeypatch.setenv("FRAMEWISE_HOST_PHOTO_ROOT", "C:\\Photos, café")
    assert display_path(source, "nested/portrait.PNG") == "C:\\Photos, café\\nested\\portrait.PNG"
    with pytest.raises(ValueError):
        display_path(source, "../outside.jpg")
    data = tmp_path / "volume"
    data.mkdir()
    verify_mount_identity(data)
    verify_mount_identity(data)
    monkeypatch.setenv("FRAMEWISE_HOST_PHOTO_ROOT", "C:\\Different photos")
    with pytest.raises(RuntimeError, match="different photographs"):
        verify_mount_identity(data)


def test_model_download_needs_explicit_consent_and_blocks_during_scans(client, source, monkeypatch):
    from framewise.scoring.aesthetic import analyzer

    assert client.post("/api/models/install", json={}).status_code == 422
    monkeypatch.setattr(analyzer, "status", lambda: {"dependencies": False, "installed": False})
    assert client.post("/api/models/install", json={"approve_download": True}).status_code == 409
    monkeypatch.setattr(analyzer, "status", lambda: {"dependencies": True, "installed": False})
    with Session.begin() as db:
        lib = Library(name="Active", source=str(source))
        db.add(lib)
        db.flush()
        db.add(ScanJob(library_id=lib.id, status="running"))
    assert client.post("/api/models/install", json={"approve_download": True}).status_code == 409


def test_model_installer_verified_subprocess_and_retry(monkeypatch):
    import framewise.workers.models as module

    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", run)
    value = ModelInstaller()
    value.run()
    assert value.state["status"] == "complete"
    assert calls[0][-1] == "--approve-download" and Path(calls[0][1]).is_file()
    monkeypatch.setattr(
        module.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1, stderr="network unavailable")
    )
    value.run()
    assert value.state == {"status": "failed", "message": "network unavailable"}


def test_scan_refuses_to_run_during_model_install(client, source, monkeypatch):
    library = client.post("/api/libraries", json={"source": str(source)}).json()
    monkeypatch.setattr(installer, "state", {"status": "running"})
    response = client.post(f"/api/libraries/{library['id']}/scan", json={})
    assert response.status_code == 409
