"""Create a conservative wide S01A anchor with the exact novel inscription.

The source wide frame intentionally has a blank wooden board.  This small
deterministic overlay supplies the one explicit readable detail from the
novel ("陆山河之墓") without asking the video model to invent lettering.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: build_longmen_tomb_inscription_anchor.py INPUT OUTPUT")
    src = Path(sys.argv[1]).resolve()
    dst = Path(sys.argv[2]).resolve()
    image = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(image)
    font_path = Path(r"C:\Windows\Fonts\simhei.ttf")
    # The board in the approved 360x655 wide anchor occupies approximately
    # x=289..326, y=204..346.  Keep the inscription small and vertical so it
    # remains a scene detail rather than a title card.
    font = ImageFont.truetype(str(font_path), 13)
    x, y = 303, 221
    for char in "陆山河之墓":
        draw.text((x, y), char, font=font, fill=(224, 224, 214), stroke_width=1, stroke_fill=(42, 42, 38))
        y += 19
    dst.parent.mkdir(parents=True, exist_ok=True)
    image.save(dst, format="PNG", optimize=True)
    print({"status": "CREATED", "path": str(dst), "sha256": hashlib.sha256(dst.read_bytes()).hexdigest()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
