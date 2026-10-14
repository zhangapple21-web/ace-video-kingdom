#!/usr/bin/env python3
"""Generate a real cover for 残荷诡影 instead of drawing one with circles.

The hero image was assets/cover.svg: a <circle> for the moon, <ellipse> blobs for
lotus pads, a few bezier strokes for stems. At the size the hero renders it, it
reads as clip art — and no amount of CSS around it fixes that, because the
problem is the image.

The ten desk covers under assets/originals/ are photographic and were never
complained about. They were made by build_covers.py, which routes through the
Shenwen adapter to gpt-image-2. This does the same thing for the hero rather
than inventing a second path: same CLI, same model, same privacy scan, same
600x900 JPEG spec, so the two sets sit on one shelf.

Two outputs:
  assets/cover-hero.jpg   600x900  — the hero figure, same spec as desk covers
  assets/og-cover.jpg    1200x630  — the social card, which was the same SVG
                                    rasterised and looked equally flat

The old SVG is left on disk. Nothing references it after this runs, and the
deploy step decides whether to drop it — deleting art in the same commit that
replaces it leaves nothing to fall back to if the new one reads wrong.

No text in either prompt: the image model cannot render CJK reliably, and the
site sets the title in HTML anyway.

Run: py -3 build_hero_cover.py [--force] [--og-only|--hero-only]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSETS = HERE / "public" / "assets"

sys.path.insert(0, str(ROOT))
from production_control.privacy_scan import scan_value  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

MODEL = "gpt-image-2"

# One style across both outputs so the hero and the social card are the same
# picture, not two drawings of the same idea.
STYLE = (
    "cinematic film still, 35mm anamorphic, volumetric moonlight through mist, "
    "shallow depth of field, restrained teal-and-amber palette, fine film grain, "
    "no text, no letters, no logo, no watermark, no border"
)

# 残荷诡影: a lotus garden at night, the reflection in the water not quite
# matching the person casting it. The subject is the discrepancy, not the pond.
HERO = (
    "a half-frozen lotus pond at night inside a walled garden, dead lotus stems "
    "standing in black water, a pale full moon low and hazy behind drifting mist, "
    "and in the water a second figure that does not match the one standing on "
    "the bank — seen from behind, small in frame, the real figure at the far "
    "shore, cool teal shadows against one warm lantern glow, vertical composition"
)

OG = (
    "a half-frozen lotus pond at night inside a walled garden, dead lotus stems "
    "in black water, a pale full moon through mist, and in the reflection a "
    "second figure that does not match the one on the bank, cool teal shadows "
    "against one warm lantern glow, wide cinematic composition with empty space "
    "on the left, vertical stems crossing the frame"
)

HERO_SIZE = (600, 900)
OG_SIZE = (1200, 630)


def image_cli() -> Path:
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    cli = home / "skills" / ".system" / "imagegen" / "scripts" / "image_gen.py"
    if not cli.is_file():
        raise SystemExit(f"imagegen CLI not found: {cli}")
    return cli


def provider_env() -> dict[str, str]:
    key = os.environ.get("SHENWEN_IMAGE_API_KEY") or os.environ.get("SHENWEN_API_KEY") or ""
    if not key:
        raise SystemExit("SHENWEN_IMAGE_API_KEY is not set in this process")
    return {
        **os.environ,
        "OPENAI_API_KEY": key,
        "OPENAI_BASE_URL": os.environ.get("SHENWEN_IMAGE_BASE_URL",
                                         "https://api.shenwenai.com/v1").rstrip("/"),
    }


def generate(label: str, scene: str, size: str, out: Path,
             final: tuple[int, int], fmt: str, quality: int) -> bool:
    """One prompt -> one file. The privacy scan gates the send, not the write."""
    verdict = scan_value(f"{scene}, {STYLE}")
    status = getattr(verdict, "status", None) or (
        verdict.get("status") if isinstance(verdict, dict) else "?")
    if str(status) != "PASS":
        print(f"  [{label}] BLOCKED by privacy scan: {status}")
        return False

    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_name(out.stem + "-raw.png")
    cmd = [
        sys.executable, str(image_cli()), "generate",
        "--model", MODEL, "--no-augment",
        "--prompt", f"{scene}, {STYLE}",
        "--size", size, "--quality", "high",
        "--out", str(raw), "--force",
    ]
    print(f"  [{label}] calling {MODEL} …", flush=True)
    try:
        result = subprocess.run(cmd, env=provider_env(), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=420)
    except subprocess.TimeoutExpired:
        print(f"  [{label}] timed out after 420s")
        return False

    if not raw.is_file():
        print(f"  [{label}] FAILED rc={result.returncode}")
        print("   ", (result.stdout or "")[-300:].replace("\n", "\n    "))
        print("   ", (result.stderr or "")[-300:].replace("\n", "\n    "))
        return False

    from PIL import Image
    with Image.open(raw) as img:
        img = img.convert("RGB")
        # Centre-crop to the target ratio rather than squashing: the provider
        # snaps to its own sizes, so a 3:2 request would otherwise be squeezed
        # into 2:3 and the moon would end up oval.
        tw, th = final
        want, have = tw / th, img.width / img.height
        if have > want:                      # too wide -> trim the sides
            nw = int(img.height * want)
            img = img.crop(((img.width - nw) // 2, 0, (img.width - nw) // 2 + nw, img.height))
        elif have < want:                    # too tall -> trim top/bottom, keep the top
            nh = int(img.width / want)
            img = img.crop((0, 0, img.width, min(nh, img.height)))
        img = img.resize(final, Image.Resampling.LANCZOS)
        if fmt == "JPEG":
            img.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
        else:
            img.save(out, "PNG", optimize=True)

    raw.unlink(missing_ok=True)
    kb = out.stat().st_size // 1024
    print(f"  [{label}] ok -> {out.name} ({final[0]}x{final[1]}, {kb} KB)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="regenerate even if present")
    ap.add_argument("--og-only", action="store_true")
    ap.add_argument("--hero-only", action="store_true")
    args = ap.parse_args()

    jobs = []
    if not args.og_only:
        jobs.append(("hero", HERO, "1024x1536", ASSETS / "cover-hero.jpg", HERO_SIZE, "JPEG", 86))
    if not args.hero_only:
        jobs.append(("og", OG, "1536x1024", ASSETS / "og-cover.jpg", OG_SIZE, "PNG", 90))

    print(f"model={MODEL}  cli={image_cli()}")
    done = 0
    for label, scene, size, out, final, fmt, q in jobs:
        if out.exists() and not args.force:
            print(f"  [{label}] already exists ({out.stat().st_size // 1024} KB), skipping")
            continue
        done += generate(label, scene, size, out, final, fmt, q)
    print(f"\n{done} of {len(jobs)} generated")
    return 0 if done == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
