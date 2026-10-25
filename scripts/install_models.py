"""Run only with explicit download consent: python scripts/install_models.py --approve-download."""

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from framewise.core.config import MODELS  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--approve-download",
        action="store_true",
        required=True,
        help="Explicit consent to download model weights from OpenAI and LAION",
    )
    parser.parse_args()
    import open_clip

    cfg = open_clip.get_pretrained_cfg("ViT-B-32", "openai")
    encoder_url = cfg["url"]
    # Exact baseline validated against OpenAI CLIP embeddings; never follow a moving branch.
    commit = "6d122adad522ab246644d9dc1c6d7a3810ee255f"
    head_sha256 = "c7b14cead230694acc7b9447974d3cad78003c72da032e402a303b6c2429e85f"
    urls = {
        "clip.pt": encoder_url,
        "aesthetic.pth": f"https://raw.githubusercontent.com/LAION-AI/aesthetic-predictor/{commit}/sa_0_4_vit_b_32_linear.pth",
    }
    digests = {}
    for name, url in urls.items():
        destination = MODELS / name
        print(f"Downloading {name} from {url}", flush=True)
        temporary = destination.with_suffix(".partial")
        urllib.request.urlretrieve(url, temporary)
        digest = hashlib.file_digest(temporary.open("rb"), "sha256").hexdigest()
        if name == "clip.pt" and digest != encoder_url.split("/")[-2]:
            temporary.unlink()
            raise ValueError("OpenAI CLIP checksum verification failed")
        if name == "aesthetic.pth" and digest != head_sha256:
            temporary.unlink()
            raise ValueError("LAION aesthetic predictor checksum verification failed")
        temporary.replace(destination)
        digests[name] = digest
    manifest = {
        "encoder": "OpenAI CLIP ViT-B/32 (QuickGELU)",
        "embedding_dimensions": 512,
        "normalization": "L2",
        "head": "LAION aesthetic predictor V1 linear (512 -> 1)",
        "laion_commit": commit,
        "urls": urls,
        "sha256": digests,
        "installed": datetime.now(UTC).isoformat(),
        "consent": "--approve-download",
    }
    (MODELS / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Installed. Provenance: {MODELS / 'manifest.json'}")


if __name__ == "__main__":
    main()
