"""Offline-only OpenAI CLIP ViT-B/32 + LAION V1 512-dimensional linear head."""

import hashlib
import importlib.util
import json
from typing import Protocol

import numpy as np
from PIL import Image

from framewise.core.config import MODELS


class PhotoAnalyzer(Protocol):
    def analyze_batch(self, images: list[Image.Image]) -> list[float | None]: ...
    def analyze_with_embeddings(
        self, images: list[Image.Image]
    ) -> list[tuple[float | None, np.ndarray | None]]: ...


class AestheticAnalyzer:
    def __init__(self):
        self.model = None
        self.head = None
        self.transform = None
        self.error = None
        self.loading = False
        self.loaded_id = None

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
        current_id = self.model_id()
        if self.model is not None and self.loaded_id == current_id:
            return
        self.loading = True
        try:
            import open_clip
            import torch

            manifest = json.loads((MODELS / "manifest.json").read_text())
            for filename in ("clip.pt", "aesthetic.pth"):
                with (MODELS / filename).open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                if digest != manifest["sha256"][filename]:
                    raise ValueError(f"Model checksum mismatch: {filename}")
            torch.set_num_threads(min(4, torch.get_num_threads()))
            model, _, transform = open_clip.create_model_and_transforms(
                "ViT-B-32", pretrained=None, device="cpu", force_quick_gelu=True
            )
            # OpenAI distributes a TorchScript archive, not a torch.load(weights_only=True) file.
            # Only load the checksum-verified local archive; no code path here can download weights.
            state = torch.jit.load(str(MODELS / "clip.pt"), map_location="cpu").state_dict()
            for key in ("input_resolution", "context_length", "vocab_size"):
                state.pop(key, None)
            model.load_state_dict(state, strict=True)
            head = torch.nn.Linear(512, 1)
            head.load_state_dict(torch.load(MODELS / "aesthetic.pth", map_location="cpu", weights_only=True))
            self.model, self.head, self.transform = model.eval(), head.eval(), transform
            self.loaded_id = current_id
        except Exception as exc:
            self.error = str(exc)
            raise
        finally:
            self.loading = False

    def retry_failed(self):
        if self.error:
            self.error = None
            self.model, self.head, self.transform = None, None, None
            self.loaded_id = None

    def analyze_batch(self, images):
        return [result[0] for result in self.analyze_with_embeddings(images)]

    def analyze_with_embeddings(self, images):
        if self.status()["status"] not in ("ready", "loading"):
            return [(None, None)] * len(images)
        try:
            import torch

            self.load()
            with torch.inference_mode():
                embeddings = self.model.encode_image(
                    torch.stack([self.transform(im) for im in images])
                ).float()
                embeddings /= embeddings.norm(dim=-1, keepdim=True).clamp_min(1e-12)
                scores = self.head(embeddings).flatten().tolist()
                vectors = embeddings.cpu().numpy().astype("float32")
                return [(float(score), vector.copy()) for score, vector in zip(scores, vectors, strict=True)]
        except Exception as exc:
            self.error = str(exc)
            return [(None, None)] * len(images)


analyzer = AestheticAnalyzer()
