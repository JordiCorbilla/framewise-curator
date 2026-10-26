"""Build a whitelist-only, downloadable Docker bundle; never include app data or photographs."""

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-image",
        action="store_true",
        help="Include the locally built linux/amd64 image; no build required for recipients",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".local/releases/Framewise-0.2.0-Docker.zip",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError(
            "Choose a new output filename; existing bundles are never overwritten"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    files = [
        ROOT / name
        for name in (
            "Dockerfile",
            ".dockerignore",
            "compose.yaml",
            "Start Framewise.cmd",
            "Stop Framewise.cmd",
            "README.md",
            "LICENSE",
            "backend/pyproject.toml",
            "backend/uv.lock",
            "frontend/package.json",
            "frontend/package-lock.json",
            "frontend/index.html",
        )
    ]
    for folder in (
        "backend/framewise",
        "backend/tests",
        "frontend/src",
        "frontend/public",
        "docs",
    ):
        files.extend(
            p
            for p in (ROOT / folder).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        )
    files.extend((ROOT / "frontend").glob("tsconfig*.json"))
    files.extend((ROOT / "frontend").glob("vite.config.*"))
    files.extend(
        p
        for p in (ROOT / "scripts").iterdir()
        if p.is_file() and p.suffix in (".py", ".ps1", ".sh")
    )
    manifest = {
        "version": "0.2.0",
        "platform": "linux/amd64",
        "includes_image": args.include_image,
        "includes_weights": False,
        "image_id": subprocess.check_output(
            ["docker", "image", "inspect", "framewise:0.2.0", "--format", "{{.Id}}"],
            text=True,
        ).strip()
        if args.include_image
        else None,
        "files": {},
    }
    with tempfile.TemporaryDirectory(prefix="framewise-bundle-") as temporary:
        image = Path(temporary) / "framewise-image.tar"
        if args.include_image:
            print("Saving the prebuilt image…", flush=True)
            subprocess.run(
                ["docker", "image", "save", "framewise:0.2.0", "--output", str(image)],
                check=True,
            )
            files.append(image)
        with zipfile.ZipFile(
            output,
            "x",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=True,
        ) as archive:
            for path in sorted(set(files)):
                name = (
                    "framewise-image.tar"
                    if path == image
                    else path.relative_to(ROOT).as_posix()
                )
                with path.open("rb") as stream:
                    manifest["files"][name] = hashlib.file_digest(
                        stream, "sha256"
                    ).hexdigest()
                archive.write(path, f"Framewise/{name}")
            archive.writestr(
                "Framewise/bundle-manifest.json", json.dumps(manifest, indent=2)
            )
        with zipfile.ZipFile(output) as archive:
            bad = archive.testzip()
            if bad:
                raise ValueError(f"Bundle integrity check failed: {bad}")
    with output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    output.with_suffix(".zip.sha256").write_text(
        f"{digest}  {output.name}\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "bundle": str(output),
                "bytes": output.stat().st_size,
                "sha256": digest,
                "files": len(manifest["files"]),
                "includes_weights": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
