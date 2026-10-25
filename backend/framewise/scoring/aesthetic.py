"""Offline-only OpenAI CLIP ViT-B/32 + LAION V1 512-dimensional linear head."""

import hashlib
import importlib.util
import json
from typing import Protocol

from PIL import Image

from framewise.core.config import MODELS


class PhotoAnalyzer(Protocol):
    def analyze_batch(self, images: list[Image.Image]) -> list[float | None]: ...


class AestheticAnalyzer:
    def __init__(self):
        self.model = None
        self.head = None
        self.transform = None
        self.error = None
        self.loading = False

    def status(self):
        paths = [MODELS / "clip.pt", MODELS / "aesthetic.pth", MODELS / "manifest.json"]
        installed = all(p.is_file() for p in paths)
        deps = (
            importlib.util.find_spec("open_clip") is not None
            and importlib.util.find_spec("torch") is not None
        )
        status = (
            "loading"
            if self.loading
            else "failed"
            if self.error
            else "ready"
            if installed and deps
            else "unavailable"
            if installed
            else "download_required"
        )
        return {
            "status": status,
            "installed": installed,
            "dependencies": deps,
            "error": self.error,
            "model_id": self.model_id(),
            "directory": str(MODELS),
            "device": "cpu",
        }

    def model_id(self):
        manifest = MODELS / "manifest.json"
        return (
            "openai-ViT-B-32-laion-v1:" + hashlib.sha256(manifest.read_bytes()).hexdigest()[:16]
            if manifest.exists()
            else "classical-only-v1"
        )

    def load(self):
        if self.model is not None:
            return
        self.loading = True
        try:
            import open_clip
            import torch

            manifest = json.loads((MODELS / "manifest.json").read_text())
            for filename in ("clip.pt", "aesthetic.pth"):
                digest = hashlib.file_digest((MODELS / filename).open("rb"), "sha256").hexdigest()
                if digest != manifest["sha256"][filename]:
                    raise ValueError(f"Model checksum mismatch: {filename}")
            torch.set_num_threads(min(4, torch.get_num_threads()))
            model, _, transform = open_clip.create_model_and_transforms(
                "ViT-B-32", pretrained=str(MODELS / "clip.pt"), device="cpu", force_quick_gelu=True
            )
            head = torch.nn.Linear(512, 1)
            head.load_state_dict(torch.load(MODELS / "aesthetic.pth", map_location="cpu", weights_only=True))
            self.model, self.head, self.transform = model.eval(), head.eval(), transform
        except Exception as exc:
            self.error = str(exc)
            raise
        finally:
            self.loading = False

    def analyze_batch(self, images):
        if self.status()["status"] not in ("ready", "loading"):
            return [None] * len(images)
        try:
            import torch

            self.load()
            with torch.inference_mode():
                embeddings = self.model.encode_image(
                    torch.stack([self.transform(im) for im in images])
                ).float()
                embeddings /= embeddings.norm(dim=-1, keepdim=True).clamp_min(1e-12)
                return [float(v) for v in self.head(embeddings).flatten().tolist()]
        except Exception as exc:
            self.error = str(exc)
            return [None] * len(images)


analyzer = AestheticAnalyzer()
