import hashlib
import io
import json
import subprocess
from pathlib import Path

from PIL import ExifTags, Image, ImageOps

from framewise.core.config import CACHE, VERSION, exiftool_path

SUPPORTED = {".nef", ".jpg", ".jpeg", ".png"}


def discover(root: Path, recursive=True):
    for p in (root.rglob("*") if recursive else root.iterdir()):
        if p.is_file() and p.suffix.lower() in SUPPORTED and not p.is_symlink():
            try:
                p.resolve().relative_to(root.resolve())
            except ValueError:
                continue
            yield p


def source_path(root, relative):
    path = (Path(root) / relative).resolve()
    path.relative_to(Path(root).resolve())
    return path


def identity(path, model_id):
    stat = path.stat()
    return hashlib.sha256(f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{VERSION}:{model_id}".encode()).hexdigest()


def read_metadata(path):
    tool = exiftool_path()
    if tool:
        result = subprocess.run([tool, "-json", "-n", "-charset", "filename=UTF8", "-DateTimeOriginal",
                                 "-Make", "-Model", "-LensModel", "-ISO", "-ExposureTime", "-FNumber",
                                 "-FocalLength", "-Orientation", "-ExposureCompensation", "-ImageWidth",
                                 "-ImageHeight", str(path)], capture_output=True, timeout=40, check=True)
        return json.loads(result.stdout.decode("utf-8"))[0]
    if path.suffix.lower() == ".nef":
        return {}
    with Image.open(path) as im:
        exif = im.getexif()
        values = dict(exif)
        try:
            values.update(exif.get_ifd(ExifTags.IFD.Exif))
        except (KeyError, TypeError):
            pass
        return {ExifTags.TAGS.get(k, str(k)): str(v) if not isinstance(v, (int, float)) else v
                for k, v in values.items()}


def orient(image, orientation):
    operations = {2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180,
                  4: Image.Transpose.FLIP_TOP_BOTTOM, 5: Image.Transpose.TRANSPOSE,
                  6: Image.Transpose.ROTATE_270, 7: Image.Transpose.TRANSVERSE, 8: Image.Transpose.ROTATE_90}
    return image.transpose(operations[int(orientation)]) if int(orientation or 1) in operations else image.copy()


def decode(path, metadata):
    if path.suffix.lower() != ".nef":
        with Image.open(path) as im:
            return ImageOps.exif_transpose(im).convert("RGB"), "original raster"
    tool = exiftool_path()
    candidates = []
    if tool:
        for tag in ("JpgFromRaw", "PreviewImage", "OtherImage"):
            result = subprocess.run([tool, "-b", f"-{tag}", str(path)], capture_output=True, timeout=60)
            if result.returncode == 0 and result.stdout:
                try:
                    with Image.open(io.BytesIO(result.stdout)) as im:
                        im.load()
                        candidates.append((im.width * im.height, im.copy(), tag))
                except (OSError, ValueError):
                    continue
    if candidates:
        _, image, tag = max(candidates, key=lambda x: x[0])
        # Embedded Nikon JPEGs generally have no orientation tag: use RAW container orientation.
        return orient(image, metadata.get("Orientation", 1)).convert("RGB"), f"embedded JPEG ({tag})"
    try:
        import rawpy

        with rawpy.imread(str(path)) as raw:
            image = Image.fromarray(raw.postprocess(half_size=True, use_camera_wb=True))
        return image.convert("RGB"), "developed RAW (LibRaw half-size)"
    except ImportError as exc:
        raise ValueError("No embedded JPEG available. Install ExifTool or optional rawpy RAW fallback.") from exc
    except Exception as exc:
        raise ValueError(f"Unsupported/corrupt NEF or RAW compression: {exc}") from exc


def cache_paths(library_id, photo_id):
    folder = CACHE / library_id
    folder.mkdir(exist_ok=True)
    return folder / f"{photo_id}-preview.jpg", folder / f"{photo_id}-thumb.jpg"


def acquire(path, library_id, photo_id):
    metadata = read_metadata(path)
    image, provenance = decode(path, metadata)
    preview, thumb = cache_paths(library_id, photo_id)
    width, height = image.size
    image.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
    image.save(preview, "JPEG", quality=90)
    small = image.copy()
    small.thumbnail((560, 560), Image.Resampling.LANCZOS)
    small.save(thumb, "JPEG", quality=83)
    return image, metadata, provenance, width, height
