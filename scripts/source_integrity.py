"""Read-only SHA256 source inventory; never writes inside the source folder."""

import argparse
import hashlib
import json
from pathlib import Path


def inventory(source):
    records = {}
    for n, path in enumerate(sorted(source.rglob("*"))):
        if path.is_file():
            stat = path.stat()
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            records[str(path.relative_to(source))] = {
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": digest,
            }
            if len(records) % 50 == 0:
                print(f"Hashed {len(records)} files", flush=True)
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["capture", "verify"])
    parser.add_argument("source", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    source, manifest = args.source.resolve(), args.manifest.resolve()
    if source == manifest or source in manifest.parents:
        raise ValueError("Manifest must be outside the source folder")
    records = inventory(source)
    if args.mode == "capture":
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(f"Captured {len(records)} files")
    else:
        baseline = json.loads(manifest.read_text(encoding="utf-8"))
        if baseline != records:
            raise SystemExit("SOURCE INTEGRITY MISMATCH")
        print(f"VERIFIED: all {len(records)} files have identical SHA256, size and modification time")


if __name__ == "__main__":
    main()
