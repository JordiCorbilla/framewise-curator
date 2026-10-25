import os
import shutil
from pathlib import Path

from platformdirs import user_data_path

DATA = Path(os.environ.get("FRAMEWISE_DATA_DIR", user_data_path("Framewise", appauthor=False)))
DATA.mkdir(parents=True, exist_ok=True)
CACHE = DATA / "cache"
MODELS = DATA / "models"
for folder in (CACHE, MODELS):
    folder.mkdir(exist_ok=True)
VERSION = "preview-v1-metrics-v1"
DEFAULT_WEIGHTS = {"aesthetic": 0.60, "sharpness": 0.25, "exposure": 0.15}


def exiftool_path():
    candidates = [
        os.environ.get("FRAMEWISE_EXIFTOOL"),
        shutil.which("exiftool"),
        str(DATA / "tools" / "exiftool.exe"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/ExifTool/exiftool.exe"),
        "C:/Program Files/ExifTool/exiftool.exe",
    ]
    return next((p for p in candidates if p and Path(p).is_file()), None)
