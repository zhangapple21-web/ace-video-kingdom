#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Republish chapter bodies from the consolidated world_live_full_script.

Discovered bug: canon_scene_pass.py's _strip_meta_blocks was stripping 其他人：
lines that actually contain narrative. Result: 79+ published chapters have
only the "环境" line. This tool re-derives the chapter body from the
consolidated script using the fixed regex.

Idempotent. Dry-run by default. Apply with --apply.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.canon_scene_pass import META_LINE_PATTERNS, _strip_meta_blocks  # noqa: E402

CHAPTERS_DIR = ROOT / "sites" / "tinghe-archive" / "public" / "data" / "chapters"
SOURCE = (
    ROOT
    / "research"
    / "persona_dna_library"
    / "20260920_canheguiying_reincarnation_v2"
    / "world_live_full_script.v1.md"
)
BACKUP_DIR = ROOT / ".migration_backups" / "republish_chapter_bodies"


def load_source_scenes(path: Path) -> dict[int, dict]:
    """Parse source into {scene_no: {header, lines}}."""
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"^第(\d+)场[^\n]*\n(.*?)(?=^第\d+场|\Z)",
        re.M | re.S,
    )
    out: dict[int, dict] = {}
    for m in pattern.finditer(text):
        no = int(m.group(1))
        body = m.group(2)
        # split first line (header line) if present
        lines = body.split("\n")
        # no separate header inside the body — header is in the lookbehind group
        out[no] = {"raw": body.strip("\n"), "lines": lines}
    return out


def chapter_id_to_no(cid: str) -> int:
    m = re.match(r"c0*(\d+)", cid)
    if not m:
        raise ValueError(f"bad chapter id: {cid}")
    return int(m.group(1))


def body_to_html(body: str) -> str:
    """Convert stripped body lines into HTML paragraphs.

    Lines already meta-stripped by _strip_meta_blocks. Wrap each non-empty
    remaining line in a <p>. Preserve line breaks within a logical paragraph
    by joining soft-newlines.
    """
    paragraphs: list[str] = []
    buf: list[str] = []
    for line in body.split("\n"):
        stripped = line.rstrip()
        if not stripped:
            if buf:
                paragraphs.append("<p>" + "<br>".join(buf) + "</p>")
                buf = []
            continue
        # If the line starts with 环境, 在场 etc — keep as paragraph break
        if any(stripped.startswith(p) for p in ("环境：", "在场：", "本场变化：", "第")):
            if buf:
                paragraphs.append("<p>" + "<br>".join(buf) + "</p>")
                buf = []
            buf.append(_escape(stripped))
            continue
        buf.append(_escape(stripped))
    if buf:
        paragraphs.append("<p>" + "<br>".join(buf) + "</p>")
    return "".join(paragraphs)


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--source", default=str(SOURCE))
    parser.add_argument("--threshold", type=int, default=200,
                        help="chapters with html shorter than this are candidates")
    args = parser.parse_args()

    src_path = Path(args.source)
    if not src_path.is_file():
        print(f"ERR source not found: {src_path}")
        return 2
    scenes = load_source_scenes(src_path)
    print(f"loaded {len(scenes)} scenes from source")

    candidates: list[tuple[str, int, int, int]] = []  # (cid, no, old_len, new_len)
    skipped_long: list[tuple[str, int]] = []
    no_source: list[str] = []

    for cjson in sorted(CHAPTERS_DIR.glob("c*.json")):
        cid = cjson.stem
        try:
            no = chapter_id_to_no(cid)
        except ValueError:
            continue
        with cjson.open("r", encoding="utf-8") as f:
            data = json.load(f)
        old_html = data.get("html", "")
        old_len = len(old_html)
        scene = scenes.get(no)
        if not scene:
            no_source.append(cid)
            continue
        body_raw = scene["raw"]
        body_stripped = _strip_meta_blocks(body_raw).strip("\n").strip()
        new_html = body_to_html(body_stripped)
        new_len = len(new_html)
        # If published html is suspiciously short but source provides more
        if old_len < args.threshold and new_len > old_len + 50:
            candidates.append((cid, no, old_len, new_len))
        else:
            skipped_long.append((cid, old_len))

    candidates.sort(key=lambda x: x[1])
    print(f"candidates to republish: {len(candidates)}")
    print(f"chapters already healthy: {len(skipped_long)}")
    if no_source:
        print(f"chapters without source: {len(no_source)} (first 5: {no_source[:5]})")

    if not args.apply:
        print("\nDRY-RUN, sample of changes:")
        for cid, no, old, new in candidates[:8]:
            print(f"  {cid} scene={no}  {old} -> {new} chars  (delta {new-old:+d})")
        return 0

    if not candidates:
        print("nothing to do")
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_zip = BACKUP_DIR / f"chapters_{ts}.jsonl"
    print(f"backing up to {backup_zip}")
    with backup_zip.open("w", encoding="utf-8") as f:
        for cid, no, old, new in candidates:
            p = CHAPTERS_DIR / f"{cid}.json"
            with p.open("r", encoding="utf-8") as src:
                row = {"id": cid, "scene_no": no, "old_html_len": old,
                       "new_html_len": new, "content": src.read()}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    changed = 0
    for cid, no, old, new in candidates:
        p = CHAPTERS_DIR / f"{cid}.json"
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        scene = scenes[no]
        body_stripped = _strip_meta_blocks(scene["raw"]).strip("\n").strip()
        data["html"] = body_to_html(body_stripped)
        # atomic write
        tmp = p.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, p)
        changed += 1

    print(f"republished {changed} chapters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())