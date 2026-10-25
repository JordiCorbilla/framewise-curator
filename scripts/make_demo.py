"""Generate project-owned geometric studies, explicitly labelled as a demo."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from framewise.core.config import DATA  # noqa: E402


def main():
    folder = DATA / "demo-generated"
    folder.mkdir(exist_ok=True)
    for index in range(8):
        image = Image.new("RGB", (1200, 800), "#a3b1ae")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 470, 1200, 800), fill="#343b37")
        for column in range(9):
            x = column * 160 - 140 + (index // 2) * 27
            height = 180 + (column * 71 + (index // 2) * 37) % 380
            draw.rectangle((x, 470 - height, x + 120, 480), fill="#465650")
            for y in range(490 - height, 430, 28):
                draw.line((x + 10, y, x + 105, y), fill="#a8bca4", width=3)
        draw.ellipse((840, 75, 940, 175), fill="#ded5b8")
        if index % 2:
            image = image.filter(ImageFilter.GaussianBlur(1.5))
        ImageDraw.Draw(image).text(
            (30, 760), "FRAMEWISE DEMO / GENERATED GEOMETRIC STUDY", fill="white"
        )
        image.save(folder / f"DEMO-generated-{index + 1:02}.jpg", quality=90)
    print(
        f"Generated 8 original demo illustrations at {folder}. Scan this folder as DEMO — generated studies."
    )


if __name__ == "__main__":
    main()
