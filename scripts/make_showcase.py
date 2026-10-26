"""Project-owned procedural illustrations for public UI screenshots, never personal photos."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from framewise.core.config import DATA  # noqa: E402


def main():
    folder = DATA / "demo-generated"
    folder.mkdir(exist_ok=True)
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    font = (
        ImageFont.truetype(str(font_path), 17)
        if font_path.exists()
        else ImageFont.load_default(17)
    )
    palettes = [
        ("#b8cbc5", "#435d57", "#233c38", "#e7c695"),
        ("#d1b7a0", "#846c59", "#403d35", "#eee0bd"),
        ("#8fadb5", "#415f73", "#253d51", "#eac5a0"),
    ]
    names = [
        "City in layers",
        "A quiet crossing",
        "Light through the facade",
        "The long way home",
    ]
    for index in range(12):
        sky, mid, dark, light = palettes[index // 4]
        image = Image.new("RGB", (1200, 800), sky)
        draw = ImageDraw.Draw(image)
        variation = index // 4
        scene = index % 4
        if scene == 0:
            draw.ellipse((840, 90, 970, 220), fill=light)
            for layer in range(3):
                for col in range(9):
                    x = col * 167 - layer * 38 - 40
                    height = 160 + (col * 97 + layer * 37 + variation * 81) % 320
                    bottom = 510 + layer * 90
                    draw.rectangle(
                        (x, bottom - height, x + 128, bottom),
                        fill=mid if layer < 2 else dark,
                    )
                    if layer == 2:
                        for y in range(bottom - height + 24, bottom - 20, 37):
                            for dx in (22, 53, 84):
                                draw.rectangle(
                                    (x + dx, y, x + dx + 8, y + 14), fill=sky
                                )
            draw.rectangle((0, 715, 1200, 800), fill=dark)
        elif scene == 1:
            draw.rectangle((0, 510, 1200, 800), fill=mid)
            for y in range(550, 800, 32):
                draw.line((0, y, 1200, y), fill=sky, width=2)
            draw.polygon([(0, 515), (1200, 395), (1200, 440), (0, 560)], fill=dark)
            for x in (235, 895):
                draw.rectangle((x, 130, x + 35, 670), fill=dark)
                draw.line(
                    (x + 17, 130, -40 if x == 235 else 1240, 500), fill=dark, width=7
                )
                for anchor in range(0, 1200, 75):
                    draw.line(
                        (x + 17, 150, anchor, 515 - anchor // 10), fill=dark, width=2
                    )
            draw.ellipse((545, 200, 630, 285), fill=light)
        elif scene == 2:
            draw.polygon([(130, 0), (1050, 0), (1170, 800), (10, 800)], fill=mid)
            for row in range(8):
                for col in range(7):
                    x = 150 + col * 129 - row * 8
                    y = 48 + row * 100
                    draw.rectangle((x, y, x + 72, y + 66), fill=dark)
                    if (row + col + variation) % 4 == 0:
                        draw.polygon(
                            [(x, y), (x + 72, y), (x + 72, y + 66), (x + 58, y + 66)],
                            fill=light,
                        )
            draw.polygon([(880, 0), (1200, 0), (1200, 800), (1080, 800)], fill=dark)
        else:
            draw.rectangle((0, 490, 1200, 800), fill=mid)
            draw.polygon([(580, 425), (660, 425), (1180, 800), (120, 800)], fill=light)
            for row in range(7):
                for side in (-1, 1):
                    x = 620 + side * (row * 74 + 80)
                    y = 430 + row * 27
                    draw.line(
                        (x, y, x, y + row * 24 + 85), fill=dark, width=9 + row * 2
                    )
                    radius = 45 + row * 8
                    draw.ellipse(
                        (x - radius, y - radius * 2, x + radius, y + 10), fill=dark
                    )
            draw.ellipse((595, 574, 609, 589), fill=dark)
            draw.rectangle((598, 587, 606, 616), fill=dark)
        draw.rectangle((0, 757, 1200, 800), fill=dark)
        draw.text(
            (25, 770),
            f"FRAMEWISE DEMO / PROCEDURAL ILLUSTRATION {index + 1:02} / {names[scene].upper()}",
            fill="#eeeadd",
            font=font,
        )
        image.save(folder / f"Study-{index + 1:02}.jpg", quality=94)
    print(folder)


if __name__ == "__main__":
    main()
