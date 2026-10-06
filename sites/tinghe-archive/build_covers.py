"""Generate one cover image per original-desk work.

The public desk listing is text-only, which makes ten short stories look like a
spreadsheet. This adds a portrait cover per work so the catalogue reads like a
bookshelf.

Routing follows the project rule: image work goes through the Shenwen adapter
(``tools/imagegen_shenwen.ps1`` → the bundled imagegen CLI) on the default
model ``gpt-image-2``. No silent model switching, no other provider.

Every prompt is scanned with ``production_control.privacy_scan`` before it is
sent anywhere; a non-PASS status blocks generation outright.

Covers are text-free on purpose: the image model cannot render CJK glyphs
reliably, so the title is overlaid in HTML instead.

Output is written to ``public/assets/originals/<work_id>/cover.jpg`` at 600x900
JPEG, which keeps the whole set well under 1MB. The public path is declared as
``assets.cover`` — for works that have an ``originals_source`` it is declared
there so ``build_originals.py`` propagates it, and for legacy works that only
exist inside ``desk.json`` it is patched directly (the builder never rewrites
those slots).

Run:  py -3 build_covers.py [--force] [--only work_id,work_id]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PUBLIC = HERE / "public"
ASSETS = PUBLIC / "assets" / "originals"
DESK = PUBLIC / "data" / "originals" / "desk.json"
SOURCE = HERE / "originals_source"

sys.path.insert(0, str(ROOT))
from production_control.privacy_scan import scan_value  # noqa: E402
from tools.atomic_io import atomic_write_text

sys.stdout.reconfigure(encoding="utf-8")  # Bug #1 fix: prevent UnicodeEncodeError on GBK console

MODEL = "gpt-image-2"
SIZE = "1024x1536"          # portrait; the provider snaps to this natively
FINAL = (600, 900)          # shipped size
JPEG_QUALITY = 84

# One shared look so ten covers read as one shelf. No text: CJK glyphs are
# unreliable in-image and the title is rendered by the site instead.
STYLE = (
    "cinematic film still, 35mm, volumetric light, shallow depth of field, "
    "restrained teal-and-amber palette, fine film grain, no text, no letters, "
    "no logo, no watermark, vertical composition"
)

PROMPTS: dict[str, str] = {
    "shuangdu": (
        "a winter river dock at night, thick ice on the mooring rope, half a sheet of "
        "oiled paper frozen to a silver handrail, an empty wooden sampan tied to a post, "
        "one dim lantern, cold blue mist over black water"
    ),
    "tuixi": (
        "a grand winter banquet hall, an overturned black name card on a lacquered table, "
        "a bowl of snow sliding off the edge, guests frozen mid-turn, brazier firelight "
        "fighting cold blue daylight through a tall window"
    ),
    "shigong": (
        "the back corridor of a cheap restaurant after closing, a mop bucket and a wall "
        "clipboard with a printed hiring form, one fluorescent tube, steam in the air"
    ),
    "bieying": (
        "a dim hospital ward at night, one neatly made empty bed, a water glass on the "
        "bedside table, moonlight through venetian blinds, a curtain stirring, uneasy quiet"
    ),
    "dibao": (
        "a cyberpunk slum street in the rain, a huge holographic advertisement showing a "
        "fake suburban house with a smiling fake father, a girl in a patched coat standing "
        "below it, stacked shacks, neon reflections in puddles"
    ),
    "fanguan": (
        "a repurposed diner on a junk planet, a battered woman ladling steaming soup into a "
        "bowl for a customer, a crate of alien beast spines beside the stove, warm lamp "
        "light inside against cold scrap and dust outside"
    ),
    "liufang": (
        "a night salvageyard, a derelict starship hull half buried in scrap, a lone young "
        "man in a torn work coat with his hand on the plating, cold blue rim light, amber "
        "sparks drifting, volumetric fog"
    ),
    "tingjijia": (
        "a vast dim hangar, a young female mechanic with her palm flat on the glass of an "
        "idle mech cockpit, teal emergency lighting, dust in the air, other mechs looming "
        "in the background"
    ),
    "tuiqun": (
        "a grand departure terminal at night, a broken engagement ring lying on polished "
        "floor between two figures seen from a distance, huge flight boards glowing, cold "
        "white light, one figure turning to walk away"
    ),
    "zhenqianjin": (
        "the surface of a mining asteroid, a young woman in a dusty mining suit holding a "
        "raw mineral in her palm, ochre dust in the air, an expensive transport descending "
        "in the sky far behind her"
    ),
}


def cover_path(work_id: str) -> Path:
    return ASSETS / work_id / "cover.jpg"


def declared_cover(work_id: str) -> str:
    return f"assets/originals/{work_id}/cover.jpg"


def image_cli() -> Path:
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    cli = home / "skills" / ".system" / "imagegen" / "scripts" / "image_gen.py"
    if not cli.is_file():
        raise SystemExit(f"imagegen CLI not found: {cli}")
    return cli


def provider_env() -> dict[str, str]:
    key = (os.environ.get("SHENWEN_IMAGE_API_KEY")
           or os.environ.get("SHENWEN_API_KEY") or "")
    if not key:
        raise SystemExit("SHENWEN_IMAGE_API_KEY is not set in this process")
    return {
        **os.environ,
        "OPENAI_API_KEY": key,
        "OPENAI_BASE_URL": os.environ.get("SHENWEN_IMAGE_BASE_URL",
                                         "https://api.shenwenai.com/v1").rstrip("/"),
    }


def generate_one(work_id: str, scene: str) -> bool:
    from PIL import Image

    target = cover_path(work_id)
    raw = target.with_name("cover-raw.png")
    raw.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(image_cli()), "generate",
        "--model", MODEL, "--no-augment",
        "--prompt", f"{scene}, {STYLE}",
        "--size", SIZE, "--quality", "high",
        "--out", str(raw), "--force",
    ]
    print(f"  [{work_id}] calling {MODEL} …", flush=True)
    result = subprocess.run(cmd, env=provider_env(), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=300)
    if not raw.is_file():
        print(f"  [{work_id}] FAILED rc={result.returncode}")
        print((result.stdout or "")[-400:])
        print((result.stderr or "")[-400:])
        return False

    with Image.open(raw) as img:
        img = img.convert("RGB")
        if img.height < img.width:
            print(f"  [{work_id}] WARNING provider returned landscape {img.size}; "
                  "re-run for a portrait cover")
        img = img.resize(FINAL, Image.Resampling.LANCZOS)
        img.save(target, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    raw.unlink(missing_ok=True)
    print(f"  [{work_id}] ok -> {target.name} ({target.stat().st_size // 1024} KB, {FINAL[0]}x{FINAL[1]})")
    return True


def declare(desk: dict, work_ids: list[str]) -> None:
    """Publish the cover path so the reader knows a cover exists."""
    for work in desk.get("works", []):
        if work["id"] not in work_ids:
            continue
        src = SOURCE / work["id"] / "work.json"
        if src.is_file():
            # Authoritative place: the builder copies `assets` into desk.json.
            data = json.loads(src.read_text(encoding="utf-8"))
            assets = dict(data.get("assets") or {})
            assets["cover"] = declared_cover(work["id"])
            ordered = {"cover": assets.pop("cover"), **assets}
            data["assets"] = ordered
            atomic_write_text(src, json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
            print(f"  declared in source: {src.relative_to(HERE)}")
        else:
            # Legacy work: it exists only inside desk.json, and build_originals
            # never rewrites those slots, so patch it in place.
            assets = dict(work.get("assets") or {})
            assets["cover"] = declared_cover(work["id"])
            work["assets"] = {"cover": assets.pop("cover"), **assets}
            print(f"  declared in desk.json: {work['id']} (legacy, no source)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="regenerate existing covers")
    ap.add_argument("--only", help="comma-separated work ids")
    ap.add_argument("--declare-only", action="store_true",
                    help="only (re)declare cover paths, generate nothing")
    args = ap.parse_args()

    desk = json.loads(DESK.read_text(encoding="utf-8"))
    works = {w["id"]: w for w in desk.get("works", [])}

    targets = ([s.strip() for s in args.only.split(",")] if args.only
               else sorted(PROMPTS))
    unknown = [w for w in targets if w not in works]
    if unknown:
        raise SystemExit(f"unknown work id(s): {unknown}")
    missing_prompt = [w for w in targets if w not in PROMPTS]
    if missing_prompt:
        raise SystemExit(f"no authored prompt for: {missing_prompt}")

    generated: list[str] = []
    if not args.declare_only:
        for work_id in targets:
            if cover_path(work_id).is_file() and not args.force:
                print(f"  [{work_id}] cover exists, skipping")
                generated.append(work_id)
                continue
            # Gate: nothing reaches the provider without a clean privacy scan.
            verdict = scan_value(f"{PROMPTS[work_id]}, {STYLE}")
            if verdict.get("status") != "PASS":
                print(f"  [{work_id}] BLOCKED_PRIVACY {verdict.get('findings')}")
                continue
            if generate_one(work_id, PROMPTS[work_id]):
                generated.append(work_id)

    declare(desk, generated)
    if generated and not args.declare_only:
        atomic_write_text(DESK, json.dumps(desk, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print("  desk.json updated")

    print(f"\ncovers ready: {len(generated)}/{len(targets)}")
    if args.declare_only:
        return 0
    return 0 if len(generated) == len(targets) else 1


if __name__ == "__main__":
    sys.exit(main())