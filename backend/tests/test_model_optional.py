from framewise.scoring import aesthetic


def test_no_model_keeps_aesthetic_unavailable(tmp_path, image, monkeypatch):
    monkeypatch.setattr(aesthetic, "MODELS", tmp_path)
    analyzer = aesthetic.AestheticAnalyzer()
    assert analyzer.status()["status"] == "download_required"
    assert analyzer.analyze_batch([image]) == [None]


def test_installed_files_without_optional_dependencies_do_not_infer(tmp_path, image, monkeypatch):
    monkeypatch.setattr(aesthetic, "MODELS", tmp_path)
    for filename in ("clip.pt", "aesthetic.pth", "manifest.json"):
        (tmp_path / filename).write_text("fixture file, never loaded")
    monkeypatch.setattr(aesthetic.importlib.util, "find_spec", lambda name: None)
    analyzer = aesthetic.AestheticAnalyzer()
    assert analyzer.status()["status"] == "unavailable"
    assert analyzer.analyze_batch([image, image]) == [None, None]
