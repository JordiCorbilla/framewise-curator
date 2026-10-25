"""Verify installed inference without network access, against OpenCLIP's OpenAI reference loader."""

import argparse
import json
import os
import socket
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

    def no_network(*args, **kwargs):
        raise AssertionError("Network connection attempted during offline inference")

    socket.socket.connect = no_network
    socket.create_connection = no_network
    import torch
    from open_clip.constants import OPENAI_DATASET_MEAN, OPENAI_DATASET_STD
    from open_clip.openai import load_openai_model
    from open_clip.transform import image_transform

    from framewise.core.config import MODELS
    from framewise.scoring.aesthetic import AestheticAnalyzer

    with Image.open(args.image) as file:
        image = file.convert("RGB")
    analyzer = AestheticAnalyzer()
    batch = analyzer.analyze_batch([image, image])
    assert all(score is not None for score in batch), analyzer.error
    assert batch[0] == batch[1]
    single = analyzer.analyze_batch([image])[0]
    assert abs(single - batch[0]) < 1e-4
    reference = load_openai_model(str(MODELS / "clip.pt"), device="cpu")
    reference.eval()
    transform = image_transform(
        224, is_train=False, mean=OPENAI_DATASET_MEAN, std=OPENAI_DATASET_STD
    )
    with torch.inference_mode():
        embeddings = reference.encode_image(transform(image).unsqueeze(0)).float()
        embeddings /= embeddings.norm(dim=-1, keepdim=True)
        expected = float(analyzer.head(embeddings).item())
    assert abs(single - expected) < 1e-4, (single, expected)
    print(
        json.dumps(
            {
                "offline": True,
                "repeated_batch_identical": True,
                "single": single,
                "reference": expected,
                "absolute_difference": abs(single - expected),
                "model_id": analyzer.model_id(),
                "device": "cpu",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
