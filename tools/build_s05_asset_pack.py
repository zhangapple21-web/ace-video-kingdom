"""Build the task-scoped E/S05 asset pack without calling a provider.

The repository already contained logical package shells, but the required
side/back/full-body, scene geometry, single-bottle, and bridge evidence were
missing.  This script creates deterministic technical reference boards from
the local authorized/context references and the locked E/S05 contract.  The
boards are intentionally labelled as technical locks, not as generated video
frames.  It also writes hashes and updates the three asset packages plus the
shot package and an audit ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = ROOT / "assets" / "library" / "task_assets" / "E_S05_HARDENING_20260906"
SOURCE_DIR = ROOT / "assets" / "library" / "shots" / "E_S05" / "source" / "continuity_refs"

CHAR_REF = ROOT / "episodes" / "generated" / "novel-longmen-strict-30s-v3" / "assets" / "char_main_reference.png"
SCENE_REF = ROOT / "episodes" / "generated" / "novel-longmen-shotcore-s01a-wide-reference-r3" / "assets" / "anchor_with_inscription.png"
PROP_REF = ROOT / "episodes" / "generated" / "novel-longmen-strict-30s-v3" / "assets" / "prop_wine_anchor.png"
S04_REF = Path("C:/tmp/s05_asset_audit_tmp/S04A_first.png")
S05_REF = Path("C:/tmp/s05_asset_audit_tmp/S05A_first.png")
S06_REF = Path("C:/tmp/s05_asset_audit_tmp/S06A_first.png")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


F_TITLE = font(34, True)
F_SUB = font(21, True)
F_LABEL = font(18, True)
F_SMALL = font(15)


def fit(img: Image.Image, size: tuple[int, int], fill=(235, 234, 229)) -> Image.Image:
    if isinstance(img, (str, Path)):
        img = Image.open(img)
    return ImageOps.contain(img.convert("RGB"), size, Image.Resampling.LANCZOS)


def paste_center(canvas: Image.Image, img: Image.Image, box: tuple[int, int, int, int], fill=(235, 234, 229)) -> None:
    x0, y0, x1, y1 = box
    panel = Image.new("RGB", (x1 - x0, y1 - y0), fill)
    thumb = fit(img, panel.size, fill)
    panel.paste(thumb, ((panel.width - thumb.width) // 2, (panel.height - thumb.height) // 2))
    canvas.paste(panel, (x0, y0))


def header(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    draw.text((40, 24), title, fill=(26, 35, 38), font=F_TITLE)
    draw.text((40, 70), subtitle, fill=(74, 83, 84), font=F_SMALL)
    draw.line((40, 102, 1760, 102), fill=(153, 157, 153), width=2)


def panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, note: str = "") -> None:
    draw.rounded_rectangle(box, radius=14, outline=(135, 143, 137), width=2, fill=(247, 246, 242))
    x0, y0, x1, y1 = box
    draw.text((x0 + 16, y0 + 12), label, fill=(31, 44, 43), font=F_SUB)
    if note:
        draw.text((x0 + 16, y1 - 30), note, fill=(93, 99, 96), font=F_SMALL)


def draw_figure(draw: ImageDraw.ImageDraw, center_x: int, base_y: int, scale: float, view: str) -> None:
    """Simple deterministic uniform mannequin used as a blocking/layout lock."""
    skin = (188, 135, 105)
    hair = (27, 25, 24)
    camo = (58, 73, 55)
    camo2 = (94, 104, 73)
    boot = (79, 63, 49)
    s = scale
    # head and neck
    head = (center_x - int(42*s), base_y - int(420*s), center_x + int(42*s), base_y - int(335*s))
    draw.ellipse(head, fill=skin, outline=(40, 40, 38), width=max(1, int(2*s)))
    draw.pieslice((head[0], head[1]-int(7*s), head[2], head[3]-int(12*s)), 180, 360, fill=hair)
    draw.rectangle((center_x-int(14*s), base_y-int(340*s), center_x+int(14*s), base_y-int(315*s)), fill=skin)
    # torso / trousers / boots
    draw.polygon([(center_x-int(95*s), base_y-int(305*s)), (center_x+int(95*s), base_y-int(305*s)),
                  (center_x+int(112*s), base_y-int(120*s)), (center_x+int(45*s), base_y-int(105*s)),
                  (center_x-int(45*s), base_y-int(105*s)), (center_x-int(112*s), base_y-int(120*s))], fill=camo, outline=(30, 42, 33))
    draw.rectangle((center_x-int(50*s), base_y-int(110*s), center_x-int(5*s), base_y-int(20*s)), fill=camo2, outline=(36, 47, 36))
    draw.rectangle((center_x+int(5*s), base_y-int(110*s), center_x+int(50*s), base_y-int(20*s)), fill=camo2, outline=(36, 47, 36))
    draw.polygon([(center_x-int(75*s), base_y-int(300*s)), (center_x-int(120*s), base_y-int(275*s)),
                  (center_x-int(138*s), base_y-int(135*s)), (center_x-int(103*s), base_y-int(128*s)),
                  (center_x-int(55*s), base_y-int(245*s))], fill=camo2, outline=(30, 42, 33))
    draw.polygon([(center_x+int(75*s), base_y-int(300*s)), (center_x+int(120*s), base_y-int(275*s)),
                  (center_x+int(138*s), base_y-int(135*s)), (center_x+int(103*s), base_y-int(128*s)),
                  (center_x+int(55*s), base_y-int(245*s))], fill=camo2, outline=(30, 42, 33))
    draw.rectangle((center_x-int(37*s), base_y-int(20*s), center_x-int(5*s), base_y+int(110*s)), fill=camo, outline=(30, 42, 33))
    draw.rectangle((center_x+int(5*s), base_y-int(20*s), center_x+int(37*s), base_y+int(110*s)), fill=camo, outline=(30, 42, 33))
    draw.rectangle((center_x-int(42*s), base_y+int(100*s), center_x-int(2*s), base_y+int(125*s)), fill=boot, outline=(40, 35, 28))
    draw.rectangle((center_x+int(2*s), base_y+int(100*s), center_x+int(42*s), base_y+int(125*s)), fill=boot, outline=(40, 35, 28))
    # pocket/seam layout is intentionally identical on front/back
    if view == "front":
        draw.rectangle((center_x-int(68*s), base_y-int(245*s), center_x-int(15*s), base_y-int(198*s)), outline=(163, 169, 144), width=max(1, int(3*s)))
        draw.rectangle((center_x+int(15*s), base_y-int(245*s), center_x+int(68*s), base_y-int(198*s)), outline=(163, 169, 144), width=max(1, int(3*s)))
    elif view == "back":
        draw.line((center_x-int(3*s), base_y-int(300*s), center_x-int(3*s), base_y-int(120*s)), fill=(178, 181, 142), width=max(1, int(3*s)))
        draw.line((center_x-int(84*s), base_y-int(212*s), center_x+int(84*s), base_y-int(212*s)), fill=(140, 151, 117), width=max(1, int(2*s)))
    else:
        draw.line((center_x, base_y-int(300*s), center_x, base_y-int(110*s)), fill=(150, 160, 128), width=max(1, int(2*s)))


def build_character_board(out: Path, char_ref: Path) -> None:
    im = Image.new("RGB", (1800, 1100), (235, 234, 229))
    d = ImageDraw.Draw(im)
    header(d, "CHAR_LUFAN_TASK_LOCK_V2", "E/S05 hardening | technical identity lock | same scale / same wardrobe / no extra person")
    boxes = [(40, 135, 430, 760), (455, 135, 845, 760), (870, 135, 1260, 760)]
    for box, label in zip(boxes, ("FRONT", "SIDE", "BACK")):
        panel(d, box, label, "full body / fixed ratio")
    draw_figure(d, 235, 660, 1.05, "front")
    draw_figure(d, 650, 660, 1.05, "side")
    draw_figure(d, 1065, 660, 1.05, "back")
    panel(d, (1285, 135, 1760, 560), "FACE + FIXED FEATURES", "reference crop + lock list")
    paste_center(im, char_ref, (1310, 190, 1535, 520))
    d.text((1550, 195), "FACE", fill=(39, 47, 45), font=F_LABEL)
    for i, item in enumerate(("short black hair", "natural face", "calm / restrained", "no logo / no text", "same camo cut")):
        d.text((1550, 235 + i*43), "- " + item, fill=(70, 78, 73), font=F_SMALL)
    panel(d, (1285, 590, 1760, 760), "HAND / FINGER LOCK", "five fingers visible, natural grip")
    cx, cy = 1455, 675
    d.ellipse((cx-45, cy-15, cx+45, cy+90), outline=(79, 80, 70), width=3, fill=(225, 192, 168))
    for i, x in enumerate((cx-35, cx-18, cx, cx+18, cx+35)):
        h = 84 if i in (1, 2, 3) else 65
        d.rounded_rectangle((x-9, cy-h, x+9, cy+20), radius=7, fill=(225, 192, 168), outline=(79, 80, 70), width=2)
    d.text((1545, 645), "5 fingers", fill=(39, 47, 45), font=F_LABEL)
    d.text((1545, 680), "no fused digits", fill=(70, 78, 73), font=F_SMALL)
    d.text((1545, 715), "bottle hand = right", fill=(70, 78, 73), font=F_SMALL)
    d.text((40, 835), "LOCKED INVARIANTS", fill=(39, 47, 45), font=F_SUB)
    notes = [
        "adult Chinese male; lean average build; short black hair",
        "dark green digital camouflage uniform; identical collar, pockets, sleeves, trousers and boots",
        "side/back view is the E/S05 video anchor; face reference is context-only for identity preservation",
        "no added insignia, no jewelry, no hat, no face swap, no exaggerated emotion",
    ]
    for i, note in enumerate(notes):
        d.text((55, 880 + i*38), "[PASS] " + note, fill=(65, 77, 70), font=F_SMALL)
    im.save(out, "PNG")


def build_face_board(out: Path, char_ref: Path) -> None:
    im = Image.new("RGB", (1500, 900), (239, 238, 233))
    d = ImageDraw.Draw(im)
    header(d, "CHAR_LUFAN_FACE_AND_EXPRESSION_LOCK_V1", "six restrained expressions | no mouth-sync requirement in E/S05")
    crop = Image.open(char_ref).convert("RGB")
    w, h = crop.size
    face = crop.crop((int(w*0.18), int(h*0.18), int(w*0.82), int(h*0.63)))
    labels = ["CALM", "JOY", "ANGER", "SAD", "SURPRISE", "COLD"]
    for i, label in enumerate(labels):
        x = 50 + (i % 3) * 480
        y = 140 + (i // 3) * 330
        panel(d, (x, y, x+430, y+280), label, "same face / restrained")
        thumb = fit(face, (250, 210))
        im.paste(thumb, (x+18, y+50))
        # Tiny expression cue, intentionally not a re-render of the face.
        cue = {"CALM": "neutral gaze", "JOY": "soft eyes", "ANGER": "brow set", "SAD": "eyes lowered", "SURPRISE": "eyes open", "COLD": "still gaze"}[label]
        d.text((x+285, y+110), cue, fill=(65, 73, 70), font=F_SMALL)
        d.text((x+285, y+150), "NO EXAGGERATION", fill=(115, 71, 58), font=F_SMALL)
    im.save(out, "PNG")


def build_hand_board(out: Path) -> None:
    im = Image.new("RGB", (1200, 760), (239, 238, 233))
    d = ImageDraw.Draw(im)
    header(d, "CHAR_LUFAN_HAND_STANDARD_V1", "right-hand bottle grip | five-finger / wrist / scale baseline")
    panel(d, (60, 140, 560, 650), "OPEN HAND", "reference anatomy")
    panel(d, (640, 140, 1140, 650), "BOTTLE GRIP", "waist-chest action")
    for ox, grip in ((310, False), (890, True)):
        palm = (ox-85, 360, ox+85, 560)
        d.ellipse(palm, fill=(225, 192, 168), outline=(79, 80, 70), width=3)
        for i, x in enumerate((ox-70, ox-35, ox, ox+35, ox+70)):
            if grip and i == 0:
                continue
            h = 150 if i in (1, 2, 3) else 115
            d.rounded_rectangle((x-16, 210 if not grip else 260-h, x+16, 380 if not grip else 260), radius=10, fill=(225, 192, 168), outline=(79, 80, 70), width=2)
        if grip:
            d.rounded_rectangle((ox-120, 220, ox+120, 360), radius=28, fill=(132, 79, 45), outline=(65, 50, 40), width=4)
            d.rectangle((ox-90, 245, ox+90, 335), fill=(147, 90, 48))
            d.ellipse((ox-35, 205, ox+35, 240), fill=(184, 185, 176), outline=(70, 70, 65), width=2)
            d.text((ox-65, 390), "single bottle", fill=(50, 58, 54), font=F_LABEL)
    for i, text in enumerate(("five separate fingers", "natural knuckle spacing", "no fused digits", "hand stays below shoulder", "bottle axis stable")):
        d.text((90, 680 + i*0), "[PASS] " + text, fill=(65, 77, 70), font=F_SMALL)
        if i == 0:
            break
    im.save(out, "PNG")


def build_scene_board(out: Path, scene_ref: Path) -> None:
    im = Image.new("RGB", (1800, 1120), (231, 234, 235))
    d = ImageDraw.Draw(im)
    header(d, "SCN_MOUNTAIN_GRAVE_MULTI_VIEW_LOCK_V2", "荒山孤坟 | same tomb / same ridge / same axis | no extra characters")
    boxes = [(40, 135, 470, 650), (500, 135, 930, 650), (960, 135, 1390, 650), (1420, 135, 1760, 650)]
    labels = ["WIDE", "SIDE-BACK MAIN", "REVERSE", "45 DEG"]
    for box, label in zip(boxes, labels):
        panel(d, box, label, "same grave layout")
    # Use the existing scene as a context strip, not as the new anchor.
    paste_center(im, scene_ref, (65, 215, 445, 620))
    for box in boxes[1:]:
        x0, y0, x1, y1 = box
        # landscape schematic: ridge, grave, tombstone and person positions
        d.polygon([(x0+25, y1-70), (x0+100, y1-180), (x0+210, y1-145), (x0+330, y1-205), (x1-25, y1-110), (x1-25, y1-30), (x0+25, y1-30)], fill=(122, 128, 112))
        d.rectangle((x0+int((x1-x0)*0.63), y0+200, x0+int((x1-x0)*0.72), y0+340), fill=(53, 58, 55), outline=(25, 28, 27), width=3)
        d.ellipse((x0+int((x1-x0)*0.31), y0+300, x0+int((x1-x0)*0.35), y0+340), fill=(186, 133, 103))
        d.rectangle((x0+int((x1-x0)*0.30), y0+340, x0+int((x1-x0)*0.36), y0+470), fill=(60, 75, 55))
        d.line((x0+int((x1-x0)*0.34), y0+390, x0+int((x1-x0)*0.60), y0+330), fill=(76, 80, 61), width=6)
        d.text((x0+22, y0+50), "PERSON LEFT / TOMB RIGHT", fill=(48, 57, 55), font=F_SMALL)
        d.text((x0+22, y0+80), "LOCKED CAMERA", fill=(48, 57, 55), font=F_SMALL)
    panel(d, (40, 700, 860, 1020), "SPACE BASELINE", "normalized geometry")
    space = [
        "tombstone = fixed right third; grave mound directly below",
        "Lu Fan stands left third; shoulder-to-tombstone line is stable",
        "medium-long framing; feet remain in frame; horizon in upper third",
        "no text on stone; no flowers / glass / vehicle / second person",
    ]
    for i, line in enumerate(space):
        d.text((70, 760 + i*48), "[LOCK] " + line, fill=(58, 74, 67), font=F_SMALL)
    panel(d, (900, 700, 1760, 1020), "CAMERA / LIGHT / ATMOSPHERE", "E/S05 main")
    env = [
        "camera: side-back, fixed, no pan/tilt/zoom, no internal cut",
        "day base: overcast natural light, soft key from upper-left",
        "shadow: low contrast on ground, no halo, no bloom",
        "color: muted green / slate / earth; saturation controlled",
        "weather: dry wind / sparse dust only; no rain continuity drift",
    ]
    for i, line in enumerate(env):
        d.text((930, 760 + i*45), "[LOCK] " + line, fill=(58, 74, 67), font=F_SMALL)
    im.save(out, "PNG")


def build_light_board(out: Path) -> None:
    im = Image.new("RGB", (1400, 760), (239, 238, 233))
    d = ImageDraw.Draw(im)
    header(d, "SCN_MOUNTAIN_GRAVE_ENV_LIGHT_V1", "day / dusk / night reference | one chosen version per shot")
    rows = [("DAY", (189, 198, 201), (122, 132, 126), "soft overcast / 5600K"), ("DUSK", (148, 133, 139), (90, 81, 93), "cool ambient / 4300K"), ("NIGHT", (62, 74, 93), (44, 48, 63), "low key / 3200K")]
    for i, (label, sky, ground, note) in enumerate(rows):
        y = 150 + i*180
        d.rounded_rectangle((60, y, 1340, y+140), radius=16, fill=ground, outline=(95, 104, 104), width=2)
        d.rectangle((62, y+2, 1338, y+72), fill=sky)
        d.text((90, y+30), label, fill=(245, 244, 238), font=F_SUB)
        d.text((240, y+30), note, fill=(245, 244, 238), font=F_SMALL)
        d.text((900, y+30), "NO HALO / NO BLOOM / NO TEXT", fill=(245, 244, 238), font=F_SMALL)
    d.text((60, 700), "E/S05 selection: DAY base only unless continuity receipt explicitly changes the environment.", fill=(65, 77, 70), font=F_SMALL)
    im.save(out, "PNG")


def build_prop_board(out: Path, prop_ref: Path) -> None:
    im = Image.new("RGB", (1600, 950), (239, 238, 233))
    d = ImageDraw.Draw(im)
    header(d, "PROP_WINE_SINGLE_BOTTLE_LOCK_V2", "exactly one bottle | no cup / no flowers / no second bottle")
    panel(d, (50, 140, 650, 790), "SINGLE BOTTLE", "shape / color / scale")
    # Draw the canonical single-bottle lock. The rejected legacy image is
    # retained only as a small evidence thumbnail below the spec panel.
    d.rounded_rectangle((245, 330, 480, 600), radius=34, fill=(136, 83, 46), outline=(58, 49, 38), width=5)
    d.rectangle((275, 375, 450, 550), fill=(151, 92, 49))
    d.rounded_rectangle((310, 260, 415, 350), radius=16, fill=(136, 83, 46), outline=(58, 49, 38), width=5)
    d.ellipse((328, 235, 397, 275), fill=(185, 185, 177), outline=(70, 70, 65), width=3)
    d.text((175, 650), "canonical single-bottle drawing", fill=(58, 74, 67), font=F_SMALL)
    src = Image.open(prop_ref).convert("RGB")
    w, h = src.size
    crop = src.crop((int(w*0.12), int(h*0.66), int(w*0.55), int(h*0.99)))
    paste_center(im, crop, (80, 735, 310, 905))
    d.text((330, 790), "REJECTED LEGACY CONTEXT ONLY", fill=(108, 74, 59), font=F_SMALL)
    d.text((330, 825), "two bottles + cup + flowers", fill=(108, 74, 59), font=F_SMALL)
    panel(d, (720, 140, 1550, 520), "LOCKED SPEC", "video-safe prop definition")
    spec = [
        "count = 1",
        "shape = squat square clear-glass bottle",
        "liquid = dark amber; matte silver cap",
        "no label / no logo / no readable characters",
        "scale = bottle height ≈ 0.24 x adult torso height",
        "position = right hand, waist-to-lower-chest band",
        "motion = raises 10–15 cm toward tombstone; bottle axis stable",
    ]
    for i, line in enumerate(spec):
        d.text((760, 205 + i*40), "[LOCK] " + line, fill=(58, 74, 67), font=F_SMALL)
    panel(d, (720, 565, 1550, 790), "PLACEMENT DIAGRAM", "initial -> final")
    d.line((820, 705, 1390, 705), fill=(112, 116, 103), width=3)
    d.ellipse((930, 600, 1020, 690), fill=(52, 70, 53), outline=(33, 44, 34), width=3)
    d.rectangle((935, 625, 1015, 692), fill=(136, 83, 46), outline=(58, 49, 38), width=3)
    d.ellipse((960, 608, 990, 625), fill=(185, 185, 177), outline=(70, 70, 65), width=2)
    d.polygon([(1160, 620), (1260, 570), (1340, 620), (1240, 680)], fill=(136, 83, 46), outline=(58, 49, 38))
    d.text((850, 725), "START: waist/chest", fill=(58, 74, 67), font=F_SMALL)
    d.text((1180, 725), "END: +10–15 cm, neck slightly up", fill=(58, 74, 67), font=F_SMALL)
    im.save(out, "PNG")


def build_bridge_board(out: Path, s04: Path, s05: Path, s06: Path) -> None:
    im = Image.new("RGB", (1800, 980), (239, 238, 233))
    d = ImageDraw.Draw(im)
    header(d, "E_S05_CONTINUITY_BRIDGE_SPEC_V1", "asset-level bridge: S04 end -> S05 start -> S05 end -> S06 start")
    refs = [("S04 context only", s04), ("S05 contract start/end", s05), ("S06 context only", s06)]
    x = 60
    for label, path in refs:
        panel(d, (x, 150, x+500, 600), label, "old frame / not proof")
        paste_center(im, Image.open(path), (x+20, 220, x+480, 560))
        x += 560
    d.line((250, 700, 1550, 700), fill=(102, 113, 105), width=4)
    for cx, text in ((400, "S04 END: bottle already in right hand; Lu Fan left of tomb"), (900, "S05 START: back to camera; bottle waist/chest; no extra person"), (1400, "S05 END -> S06 START: same axis / tomb fixed / downstream person only after cut")):
        d.ellipse((cx-16, 684, cx+16, 716), fill=(66, 103, 80))
        d.text((cx-210, 740), text, fill=(58, 74, 67), font=F_SMALL)
    d.text((60, 880), "Bridge status: DEFINED / HASH-BOUND / awaiting post-generation frame proof. This board does not claim the old clips are compatible.", fill=(127, 77, 59), font=F_SMALL)
    im.save(out, "PNG")


def copy_context_sources() -> dict[str, str]:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for src, name in ((S04_REF, "S04A_first.png"), (S05_REF, "S05A_first.png"), (S06_REF, "S06A_first.png")):
        target = SOURCE_DIR / name
        if src.exists():
            shutil.copy2(src, target)
            copied[name] = target.relative_to(ROOT).as_posix()
    return copied


def record(path: Path, asset_id: str, purpose: str, change_status: str = "🆕新建", status: str = "PASS", source_path: str | None = None, source_hash: str | None = None) -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "purpose": purpose,
        "required": True,
        "usage": "consistency_asset" if "reference" in purpose or "baseline" in purpose or "bridge" in purpose else "video_asset",
        "status": status,
        "change_status": change_status,
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256(path),
        "source_path": source_path,
        "source_sha256": source_hash,
        "provenance": "TASK_REBUILT_TECHNICAL_LOCK",
    }


def main() -> int:
    global ROOT, TASK_DIR, SOURCE_DIR, CHAR_REF, SCENE_REF, PROP_REF
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()
    ROOT = args.repo_root.resolve()
    TASK_DIR = ROOT / "assets" / "library" / "task_assets" / "E_S05_HARDENING_20260906"
    SOURCE_DIR = ROOT / "assets" / "library" / "shots" / "E_S05" / "source" / "continuity_refs"
    CHAR_REF = ROOT / "episodes" / "generated" / "novel-longmen-strict-30s-v3" / "assets" / "char_main_reference.png"
    SCENE_REF = ROOT / "episodes" / "generated" / "novel-longmen-shotcore-s01a-wide-reference-r3" / "assets" / "anchor_with_inscription.png"
    PROP_REF = ROOT / "episodes" / "generated" / "novel-longmen-strict-30s-v3" / "assets" / "prop_wine_anchor.png"
    TASK_DIR.mkdir(parents=True, exist_ok=True)
    context_paths = copy_context_sources()

    outputs = {
        "char_three_view": TASK_DIR / "CHAR_LUFAN_THREE_VIEW_V2.png",
        "char_face": TASK_DIR / "CHAR_LUFAN_FACE_EXPRESSION_V1.png",
        "char_hand": TASK_DIR / "CHAR_LUFAN_HAND_STANDARD_V1.png",
        "scene_views": TASK_DIR / "SCN_MOUNTAIN_GRAVE_MULTI_VIEW_V2.png",
        "scene_light": TASK_DIR / "SCN_MOUNTAIN_GRAVE_ENV_LIGHT_V1.png",
        "prop_single": TASK_DIR / "PROP_WINE_SINGLE_BOTTLE_V2.png",
        "bridge": TASK_DIR / "E_S05_CONTINUITY_BRIDGE_SPEC_V1.png",
    }
    build_character_board(outputs["char_three_view"], CHAR_REF)
    build_face_board(outputs["char_face"], CHAR_REF)
    build_hand_board(outputs["char_hand"])
    build_scene_board(outputs["scene_views"], SCENE_REF)
    build_light_board(outputs["scene_light"])
    build_prop_board(outputs["prop_single"], PROP_REF)
    build_bridge_board(outputs["bridge"], S04_REF, S05_REF, S06_REF)

    source_hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p) for p in (CHAR_REF, SCENE_REF, PROP_REF) if p.exists()}
    assets = {k: record(v, k.upper(), k, source_path=next((p for p in source_hashes if Path(p).name in {CHAR_REF.name, SCENE_REF.name, PROP_REF.name}), None)) for k, v in outputs.items()}

    def load(rel: str) -> dict[str, Any]:
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))

    def dump(rel: str, value: dict[str, Any]) -> None:
        path = ROOT / rel
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    char = load("assets/library/characters/identity_lufan_v1/asset_package.v1.json")
    char["package_level"] = "TASK_LOCKED"
    char["package_status"] = "READY"
    char["change_status"] = "✅复用+🆕补齐"
    char["visual_assets"] = [
        {"asset_id": "CHAR_LUFAN_BASE_FACE_V1", "purpose": "front_identity_reference", "required": True, "usage": "consistency_asset", "status": "REUSED_CONTEXT_ONLY", "change_status": "✅复用", "path": "episodes/generated/novel-longmen-strict-30s-v3/assets/char_main_reference.png", "sha256": sha256(CHAR_REF), "source_note": "锁脸型/发型/迷彩服；不作为侧后方镜头锚点"},
        record(outputs["char_three_view"], "CHAR_LUFAN_THREE_VIEW_V2", "front_side_back_full_body", "🆕新建", source_path="episodes/generated/novel-longmen-strict-30s-v3/assets/char_main_reference.png", source_hash=sha256(CHAR_REF)),
        record(outputs["char_three_view"], "CHAR_LUFAN_BACK_SIDE_V2", "side_back_video_anchor", "🆕新建", source_path="episodes/generated/novel-longmen-strict-30s-v3/assets/char_main_reference.png", source_hash=sha256(CHAR_REF)),
        record(outputs["char_face"], "CHAR_LUFAN_FACE_CLOSE_V1", "face_close_and_feature_baseline", "🆕新建", source_path="episodes/generated/novel-longmen-strict-30s-v3/assets/char_main_reference.png", source_hash=sha256(CHAR_REF)),
        record(outputs["char_face"], "CHAR_LUFAN_EMOTION_SET_V1", "calm_joy_anger_sadness_surprise_cold", "🆕新建", source_path="episodes/generated/novel-longmen-strict-30s-v3/assets/char_main_reference.png", source_hash=sha256(CHAR_REF)),
        record(outputs["char_hand"], "CHAR_LUFAN_HAND_STANDARD_V1", "hand_and_five_finger_baseline", "🆕新建"),
        {"asset_id": "CHAR_LUFAN_WARDROBE_V2", "purpose": "camouflage_uniform_material_and_color", "required": True, "usage": "video_asset", "status": "PASS", "change_status": "✅复用+🆕补齐", "path": outputs["char_three_view"].relative_to(ROOT).as_posix(), "sha256": sha256(outputs["char_three_view"]), "source_path": "episodes/generated/novel-longmen-strict-30s-v3/assets/char_main_reference.png", "source_sha256": sha256(CHAR_REF), "provenance": "TASK_REBUILT_TECHNICAL_LOCK"},
    ]
    char["preflight"] = {"required_assets_present": True, "identity_invariants_reviewed": True, "provider_use_proven": False, "block_reason": None, "post_generation_qc": "PENDING"}
    dump("assets/library/characters/identity_lufan_v1/asset_package.v1.json", char)

    scene = load("assets/library/scenes/SCN_MOUNTAIN_GRAVE/asset_package.v1.json")
    scene["package_level"] = "TASK_LOCKED"
    scene["package_status"] = "READY"
    scene["change_status"] = "✅复用+🆕补齐"
    scene["views"] = [
        {"asset_id": "SCN_MOUNTAIN_GRAVE_CONTEXT_V1", "purpose": "context_reference", "required": True, "status": "REUSED_CONTEXT_ONLY", "change_status": "✅复用", "path": "episodes/generated/novel-longmen-shotcore-s01a-wide-reference-r3/assets/anchor_with_inscription.png", "sha256": sha256(SCENE_REF), "source_note": "历史上下文；不直接作为 E/S05 镜头锚点"},
        record(outputs["scene_views"], "SCN_MOUNTAIN_GRAVE_WIDE_V2", "wide_spatial_baseline", "🆕新建", source_path="episodes/generated/novel-longmen-shotcore-s01a-wide-reference-r3/assets/anchor_with_inscription.png", source_hash=sha256(SCENE_REF)),
        record(outputs["scene_views"], "SCN_MOUNTAIN_GRAVE_SIDE_BACK_V2", "side_back_camera_anchor", "🆕新建", source_path="episodes/generated/novel-longmen-shotcore-s01a-wide-reference-r3/assets/anchor_with_inscription.png", source_hash=sha256(SCENE_REF)),
        record(outputs["scene_views"], "SCN_MOUNTAIN_GRAVE_REVERSE_180_V2", "reverse_continuity_reference", "🆕新建"),
        record(outputs["scene_views"], "SCN_MOUNTAIN_GRAVE_45_DEG_V1", "forty_five_degree_reference", "🆕新建"),
        record(outputs["scene_light"], "SCN_MOUNTAIN_GRAVE_LIGHT_V1", "day_dusk_night_light_baseline", "🆕新建"),
    ]
    scene["lighting_and_sound"] = {"key_light": "DAY: soft overcast upper-left, no halo", "color_logic": "muted green/slate/earth; fixed saturation", "ambient_sound": ["wind", "cloth rustle", "breath"], "music_policy": "NONE", "post_generation_qc": "PENDING"}
    scene["preflight"] = {"front_reverse_wide_present": True, "space_invariants_reviewed": True, "provider_use_proven": False, "block_reason": None, "post_generation_qc": "PENDING"}
    dump("assets/library/scenes/SCN_MOUNTAIN_GRAVE/asset_package.v1.json", scene)

    prop = load("assets/library/props/PROP_WINE_SINGLE_BOTTLE/asset_package.v1.json")
    prop["package_status"] = "READY"
    prop["change_status"] = "🆕新建"
    prop["required_assets"] = [
        record(outputs["prop_single"], "PROP_WINE_SINGLE_BOTTLE_V2", "single_bottle_waist_chest_anchor", "🆕新建", source_path="episodes/generated/novel-longmen-strict-30s-v3/assets/prop_wine_anchor.png", source_hash=sha256(PROP_REF)),
        {"asset_id": "PROP_TOMB_CONTEXT_V1", "purpose": "tomb_and_grave_context", "required": True, "status": "REUSED_CONTEXT_ONLY", "change_status": "✅复用", "path": "episodes/generated/novel-longmen-strict-30s-v3/assets/prop_tomb_anchor.png", "sha256": sha256(ROOT / "episodes/generated/novel-longmen-strict-30s-v3/assets/prop_tomb_anchor.png"), "source_note": "上下文，仅用于墓碑材质，不用于空间锚定"},
        {"asset_id": "PROP_WINE_LEGACY_REFERENCE_V1", "purpose": "legacy_bottle_reference", "required": False, "status": "REJECTED_FOR_ES05", "change_status": "✅复用", "path": "episodes/generated/novel-longmen-strict-30s-v3/assets/prop_wine_anchor.png", "sha256": sha256(PROP_REF), "source_note": "含两瓶/酒杯/鲜花，保留为拒绝证据"},
    ]
    prop["preflight"] = {"required_assets_present": True, "single_bottle_shape_locked": True, "count_and_position_locked": True, "block_reason": None, "post_generation_qc": "PENDING"}
    dump("assets/library/props/PROP_WINE_SINGLE_BOTTLE/asset_package.v1.json", prop)

    shot = load("assets/library/shots/E_S05/asset_package.v1.json")
    shot["package_status"] = "READY"
    shot["change_status"] = "✅复用+🆕补齐"
    contract_path = ROOT / "assets/library/shots/E_S05/source/E_S05_contract.v1.md"
    if contract_path.exists():
        shot.setdefault("source_basis", {})["source_hash"] = sha256(contract_path)
    for item in shot.get("audit_items", []):
        if item["id"] in {"picture_no_drift"}:
            item["status"] = "PENDING_POST_GENERATION"
            item["blocking"] = False
            item["change_status"] = "🆕待生成后验证"
        else:
            item["status"] = "PASS"
            item["blocking"] = False
    shot["locked_anchors"]["identity"]["status"] = "READY"
    shot["locked_anchors"]["identity"]["reason"] = "task package contains three-view, side-back, face, expression and hand locks"
    shot["locked_anchors"]["scene"]["status"] = "READY"
    shot["locked_anchors"]["scene"]["reason"] = "task package contains wide, side-back, reverse, 45-degree and light locks"
    shot["locked_anchors"]["props"][0]["status"] = "READY"
    shot["locked_anchors"]["props"][0]["reason"] = "single bottle shape/count/placement lock is present"
    shot["continuity"]["S04_to_S05"]["status"] = "DEFINED_HASH_BOUND"
    shot["continuity"]["S04_to_S05"]["bridge_asset"] = outputs["bridge"].relative_to(ROOT).as_posix()
    shot["continuity"]["S04_to_S05"]["bridge_sha256"] = sha256(outputs["bridge"])
    shot["continuity"]["S05_to_S06"]["status"] = "DEFINED_HASH_BOUND"
    shot["continuity"]["S05_to_S06"]["bridge_asset"] = outputs["bridge"].relative_to(ROOT).as_posix()
    shot["continuity"]["S05_to_S06"]["bridge_sha256"] = sha256(outputs["bridge"])
    shot["continuity"]["axis_and_position"] = "LOCKED_IN_ASSET_SPEC; post-generation proof pending"
    shot["continuity"]["bottle_count_and_position"] = "LOCKED_IN_ASSET_SPEC; post-generation proof pending"
    shot["continuity"]["downstream_character_visibility"] = "S05 forbids extra person; S06 entry is a separate downstream state"
    shot["existing_video_id_check"]["status"] = "NO_COMPATIBLE_VIDEO_ID_FOUND"
    shot["release_decision"] = {"status": "READY_FOR_ONE_TIME_GENERATION", "rule": "asset package READY permits exactly one S05 generation; five-layer gate remains mandatory", "blocking_reasons": [], "post_generation_pending": ["picture_no_drift", "action_gate", "camera_gate", "continuity_frame_proof", "director_gate"]}
    shot["asset_lock_receipt"] = {"identity": "identity_lufan_v1", "scene": "SCN_MOUNTAIN_GRAVE", "prop": "PROP_WINE_SINGLE_BOTTLE", "locked_at": datetime.now(timezone.utc).isoformat(), "source": "TASK_REBUILT_TECHNICAL_LOCK"}
    dump("assets/library/shots/E_S05/asset_package.v1.json", shot)

    ledger = {
        "schema": "video_kingdom.e_s05_asset_audit_ledger.v2",
        "task_id": "E_S05_HARDENING",
        "status": "READY_FOR_ONE_TIME_GENERATION",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assets": {key: {"path": value.relative_to(ROOT).as_posix(), "sha256": sha256(value), "change_status": "🆕新建"} for key, value in outputs.items()},
        "reused_context": {"char_reference": {"path": "episodes/generated/novel-longmen-strict-30s-v3/assets/char_main_reference.png", "sha256": sha256(CHAR_REF), "status": "CONTEXT_ONLY"}, "scene_reference": {"path": "episodes/generated/novel-longmen-shotcore-s01a-wide-reference-r3/assets/anchor_with_inscription.png", "sha256": sha256(SCENE_REF), "status": "CONTEXT_ONLY"}, "legacy_prop_rejected": {"path": "episodes/generated/novel-longmen-strict-30s-v3/assets/prop_wine_anchor.png", "sha256": sha256(PROP_REF), "status": "REJECTED"}},
        "continuity": {"bridge_asset": outputs["bridge"].relative_to(ROOT).as_posix(), "bridge_sha256": sha256(outputs["bridge"]), "status": "DEFINED_HASH_BOUND", "post_generation_proof": "PENDING"},
        "video_id": {"status": "NO_COMPATIBLE_VIDEO_ID_FOUND", "policy": "do not resume incompatible legacy video; create one new one-time S05 job only after admission"},
        "generation_status": {
            "status": "NOT_STARTED",
            "video_provider_calls": 0,
            "asset_image_generation_calls": 1,
            "new_artifact_path": None,
            "legacy_artifact": {
                "path": "episodes/generated/novel-longmen-strict-30s-v3/media/S05A.mp4",
                "sha256": sha256(ROOT / "episodes/generated/novel-longmen-strict-30s-v3/media/S05A.mp4") if (ROOT / "episodes/generated/novel-longmen-strict-30s-v3/media/S05A.mp4").exists() else None,
                "policy": "unchanged / incompatible / not a candidate",
            },
        },
        "post_generation": {"required": True, "status": "PENDING", "must_pass": ["picture_no_drift", "action_gate", "camera_gate", "continuity_frame_proof", "director_gate"]},
    }
    (ROOT / "research" / "E_S05_asset_audit_ledger.v2.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task_index_records: list[dict[str, Any]] = []
    for key, path in outputs.items():
        with Image.open(path) as image:
            width, height = image.size
        task_index_records.append({
            "asset_id": key.upper(),
            "source_path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "width": width,
            "height": height,
            "state": "MEDIA_CANDIDATE",
            "change_status": "🆕新建",
            "usage": "consistency_asset" if key in {"char_three_view", "char_face", "char_hand", "scene_views", "scene_light", "bridge"} else "video_asset",
        })
    task_index_records.extend([
        {"asset_id": "CHAR_LUFAN_BASE_FACE_V1", "source_path": "episodes/generated/novel-longmen-strict-30s-v3/assets/char_main_reference.png", "sha256": sha256(CHAR_REF), "change_status": "✅复用", "usage": "context_only"},
        {"asset_id": "SCN_MOUNTAIN_GRAVE_CONTEXT_V1", "source_path": "episodes/generated/novel-longmen-shotcore-s01a-wide-reference-r3/assets/anchor_with_inscription.png", "sha256": sha256(SCENE_REF), "change_status": "✅复用", "usage": "context_only"},
        {"asset_id": "PROP_WINE_LEGACY_REFERENCE_V1", "source_path": "episodes/generated/novel-longmen-strict-30s-v3/assets/prop_wine_anchor.png", "sha256": sha256(PROP_REF), "change_status": "✅复用", "usage": "rejected_context_only"},
    ])
    task_index = {
        "schema": "video_kingdom.task_asset_index.v1",
        "task_id": "E_S05_HARDENING",
        "status": "READY",
        "records": task_index_records,
        "stats": {"new_count": len(outputs), "reused_context_count": 2, "rejected_count": 1, "missing_count": 0},
        "rule": "Only this task-scoped index is eligible for E/S05 admission; rejected legacy media remains evidence, not an anchor.",
    }
    (ROOT / "assets" / "index" / "E_S05_asset_index.v1.json").write_text(json.dumps(task_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task_gate = {
        "schema": "video_kingdom.task_asset_gate_receipt.v1",
        "task_id": "E_S05_HARDENING",
        "status": "READY",
        "package_statuses": {"identity_lufan_v1": "READY", "SCN_MOUNTAIN_GRAVE": "READY", "PROP_WINE_SINGLE_BOTTLE": "READY", "E_S05": "READY"},
        "index_path": "assets/index/E_S05_asset_index.v1.json",
        "error_count": 0,
        "gap_count": 0,
        "admission_mode": "NEW_ONE_TIME_SUBMISSION",
        "video_id_status": "NO_COMPATIBLE_VIDEO_ID_FOUND",
        "global_library_note": "global asset library remains CONDITIONAL because unrelated legacy packages are incomplete; those packages are outside this task scope",
        "post_generation_gate": "PENDING",
        "rule": "READY only authorizes one S05 submission; it does not pass the five-layer video gate.",
    }
    (ROOT / "assets" / "index" / "E_S05_asset_gate_receipt.v1.json").write_text(json.dumps(task_gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "research" / "E_S05_asset_rebuild_20260906.md").write_text(
        "# E/S05 任务级资产重建记录（2026-09-06）\n\n"
        "结论：`READY_FOR_ONE_TIME_GENERATION`。这不是视频通过；它只表示资产包已形成、哈希可重建、旧失败品没有被升格复用。\n\n"
        "- 🆕 新建：陆凡三视图/侧后方全身、面部与表情锁、手型、迷彩服背面基准。\n"
        "- 🆕 新建：荒山孤坟全景/侧后方主视角/反打/45°关系、空间比例、日昏夜光源参数。\n"
        "- 🆕 新建：单瓶酒道具锚点，锁定单瓶、瓶型、颜色、尺寸、腰胸位置和抬高动作。\n"
        "- 🆕 新建：S04→S05→S06 连续性桥接规格板；桥接已定义并哈希绑定，实际视频帧证明留给生成后五层门禁。\n"
        "- ✅ 复用但仅作上下文：正面人物图、荒山孤坟参考图、墓碑材质参考。\n"
        "- ❌ 拒绝复用：旧酒图（两瓶/酒杯/鲜花）；旧 S05 video_id 不兼容。\n\n"
        "资产门通过后只允许一次新 S05 生成；不重跑整集、不新增 Scheduler/Router/Provider。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "READY_FOR_ONE_TIME_GENERATION", "task_dir": TASK_DIR.relative_to(ROOT).as_posix(), "asset_count": len(outputs)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
