# -*- coding: utf-8 -*-
"""Render the Open Graph share card for《残荷诡影》.

The site ships static SVG artwork; social platforms do not render SVG in
``og:image``, so this paints the same moon-over-lotus motif once into a
1200x630 PNG. Output is committed; this script only needs re-running when the
title or palette changes.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent / "public" / "assets" / "og-cover.png"
W, H = 1200, 630

INK = (18, 58, 49)
INK_DEEP = (10, 34, 29)
JADE = (31, 81, 69)
RUST = (166, 73, 56)
GOLD = (182, 129, 78)
PAPER = (246, 236, 210)
SERIF = r"C:\Windows\Fonts\msyh.ttc"


def vertical(draw, text, font, x, y, fill, gap=6):
    """Stack characters top-to-bottom (CJK title treatment)."""
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        y += font.size + gap
    return y


def main() -> None:
    img = Image.new("RGB", (W, H), INK_DEEP)
    d = ImageDraw.Draw(img)

    # Sky: cool ink at the top easing into warm dusk at the waterline.
    for y in range(H):
        t = y / H
        if t < 0.58:
            k = t / 0.58
            col = tuple(int(a + (b - a) * k) for a, b in zip((16, 44, 47), (52, 78, 74)))
        else:
            k = (t - 0.58) / 0.42
            col = tuple(int(a + (b - a) * k) for a, b in zip((52, 78, 74), (108, 92, 68)))
        d.line([(0, y), (W, y)], fill=col)

    # Moon with a soft halo: blur a bright disc, then screen it back over the sky.
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse([806, 44, 1046, 284], fill=(250, 240, 205))
    glow = glow.filter(ImageFilter.GaussianBlur(46)).convert("L")
    halo = Image.blend(img, Image.new("RGB", (W, H), (250, 240, 205)), 0.34)
    img = Image.composite(halo, img, glow.point(lambda v: min(255, v * 3)))
    d = ImageDraw.Draw(img)
    d.ellipse([846, 84, 1006, 244], fill=(250, 243, 214))

    # Waterline, then a reflection broken into short ripples under the moon.
    water_y = 392
    d.rectangle([0, water_y, W, H], fill=(30, 62, 58))
    for i in range(9):
        yy = water_y + 20 + i * 24
        half = 150 - i * 12
        d.line([(926 - half, yy), (926 + half, yy)], fill=(206, 226, 205), width=3)

    # Broken lotus stems rising out of the water, clear of the title panel.
    for cx, lean, stem in ((566, -8, (58, 112, 100)), (700, 7, (46, 96, 86))):
        top = 250
        d.line([(cx, H - 10), (cx + lean, top + 34)], fill=stem, width=8)
        d.ellipse([cx + lean - 15, top + 20, cx + lean + 15, top + 50], fill=stem)
        d.ellipse([cx + lean - 10, top - 6, cx + lean + 8, top + 24], fill=(201, 158, 112))
    d.ellipse([812, 268, 842, 298], fill=RUST)

    # Framed paper panel holding the vertical title.
    PX0, PY0, PX1, PY1 = 64, 84, 500, 546
    d.rectangle([PX0, PY0, PX1, PY1], fill=(243, 232, 207))
    d.rectangle([PX0 + 14, PY0 + 14, PX1 - 14, PY1 - 14], outline=(136, 119, 85), width=2)
    d.rectangle([PX0 + 28, PY0 + 28, PX1 - 28, PY1 - 28], outline=(166, 145, 105), width=1)

    title = ImageFont.truetype(SERIF, 62)
    mid = ImageFont.truetype(SERIF, 38)
    small = ImageFont.truetype(SERIF, 25)
    lead = ImageFont.truetype(SERIF, 23)

    vertical(d, "残荷诡影", title, 142, 138, JADE, gap=6)
    vertical(d, "听荷轩", mid, 262, 152, RUST, gap=8)
    vertical(d, "莲蓬鬼话", small, 332, 164, (112, 104, 84), gap=6)

    d.line([(142, 462), (400, 462)], fill=(136, 119, 85), width=2)
    d.text((142, 476), "月下见影，水中藏局", font=lead, fill=(92, 86, 70))

    # Seal, tucked into the panel's top-right corner.
    d.rectangle([396, 128, 444, 176], outline=RUST, width=3)
    seal = ImageFont.truetype(SERIF, 22)
    d.text((404, 133), "听", font=seal, fill=RUST)
    d.text((404, 155), "荷", font=seal, fill=RUST)

    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT.name} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()