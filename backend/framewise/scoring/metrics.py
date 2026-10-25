import cv2
import imagehash
import numpy as np
from PIL import Image


def classical(image: Image.Image):
    sample = image.copy()
    sample.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    rgb = np.asarray(sample.convert("RGB"), dtype=np.float32) / 255
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    contrast = float(gray.std())
    lap = float(cv2.Laplacian(gray, cv2.CV_32F).var())
    gradient = cv2.magnitude(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1))
    edge_density = float((gradient > 0.08).mean())
    normalized = lap / max(contrast**2, 0.0025)
    # Resolution bounded, contrast normalized, texture-aware heuristic; not a probability of focus.
    sharpness = float(np.clip(100 * (1 - np.exp(-normalized * 2.0)), 0, 100))
    highlights = float((gray >= 0.985).mean())
    shadows = float((gray <= 0.015).mean())
    exposure = float(np.clip(100 - highlights * 100 - shadows * 35, 0, 100))
    raw = {
        "laplacian_variance": lap,
        "normalized_detail": normalized,
        "edge_density": edge_density,
        "contrast": contrast,
        "mean_luminance": float(gray.mean()),
        "highlight_clipping": highlights,
        "shadow_clipping": shadows,
        "mean_rgb": [float(v) for v in rgb.mean(axis=(0, 1))],
    }
    calibrated = {
        "sharpness": round(sharpness, 3),
        "exposure": round(exposure, 3),
        "focus_risk": "uncertain: low texture"
        if edge_density < 0.04
        else ("inspect" if sharpness < 30 else "lower risk"),
    }
    return raw, calibrated, str(imagehash.phash(sample))
