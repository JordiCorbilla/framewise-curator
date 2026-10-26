"""Explicit, asynchronous one-time model installation; never initiated by inference."""

import subprocess
import sys
import threading
from pathlib import Path

from framewise.db.models import ScanJob, Session
from framewise.scoring.aesthetic import analyzer
from framewise.workers.scan import ACTIVE, manager


class ModelInstaller:
    def __init__(self):
        self.state = {"status": "idle", "message": None}

    def start(self):
        with manager.lock:
            if self.state["status"] == "running":
                return dict(self.state)
            if not analyzer.status()["dependencies"]:
                raise ValueError(
                    "AI dependencies are missing. Use the Docker edition or install the ai extra first."
                )
            if analyzer.status()["installed"]:
                return {"status": "complete", "message": "Models are already installed."}
            with Session() as db:
                if db.query(ScanJob).filter(ScanJob.status.in_(ACTIVE)).first():
                    raise ValueError("Wait for the active scan to stop before installing models.")
            self.state = {
                "status": "running",
                "message": "Downloading verified model files (~350 MB). Keep Framewise running.",
            }
            threading.Thread(target=self.run, daemon=True, name="model-install").start()
            return dict(self.state)

    def run(self):
        script = Path(__file__).resolve().parents[3] / "scripts" / "install_models.py"
        try:
            result = subprocess.run(
                [sys.executable, str(script), "--approve-download"],
                capture_output=True,
                text=True,
                timeout=1800,
            )
            if result.returncode:
                raise RuntimeError(
                    result.stderr[-1500:]
                    or "Model installer failed. Retry when your connection is available."
                )
            analyzer.retry_failed()
            self.state = {
                "status": "complete",
                "message": "Models installed and verified. Scan or check for changes to fill AI scores.",
            }
        except Exception as exc:
            self.state = {"status": "failed", "message": str(exc)}


installer = ModelInstaller()
