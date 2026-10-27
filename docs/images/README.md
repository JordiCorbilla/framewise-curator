# Public screenshot assets

Captured from the actual built React application on 26 October 2026. All image content comes from
`scripts/make_showcase.py`: twelve project-owned procedural illustrations, each labelled **FRAMEWISE DEMO /
PROCEDURAL ILLUSTRATION**. No user photographs, NEFs, private source paths, weights or databases are included.

- `curate.png`: gallery, budget presets, filters, ratings and selections.
- `highlights.png`: finalists, evidence and alternatives.
- `compare.png`: side-by-side demo frames and actual feature measurements.
- `preferences.png`: cold-start controls; no invented personal validation score.
- `library.png`: collection management and Framewise identity.
- `folder-picker.png`: Docker 0.2 folder browsing inside the read-only mount, using owned demo folders.

The isolated workspace used installed model files with real CPU inference. Configuration: 12 JPEGs,
25% editing budget, competition aesthetic/technical floors **0**, Flickr floor **0**, percentile **50**,
maximum **6**, Exactly three **off**. Lower floors let schematic illustrations exercise the layout.
They are not recommended photographic settings or a curation-quality benchmark. Compare shows a
temporary manual replacement used for UI verification; automatic rankings were subsequently restored.

To reproduce without reading private photographs:

```powershell
$env:FRAMEWISE_DATA_DIR = 'C:\Temp\Framewise-public-demo'
.\backend\.venv\Scripts\python.exe .\scripts\make_showcase.py
# Install optional dependencies/models in this workspace if desired, with explicit consent.
.\backend\.venv\Scripts\python.exe -m uvicorn framewise.api.app:app --app-dir backend --host 127.0.0.1 --port 8765
```

Scan the printed `demo-generated` path, name it clearly as a demo, configure the example floors and
capture the UI. Stop your normal server first if 8765 is occupied, or use the development port 5173 when
free. Keep app data outside Git and bind to localhost. `showcase_server.ps1` is a guarded helper for the
ignored `.local/showcase-data` workspace on 5173; its data directory and optional model files must exist.
