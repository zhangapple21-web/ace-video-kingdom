"""Publish only the validated work state used by the public Drama Studio.

This is deliberately a small, deterministic boundary between the evolving
workspace and the reader-facing site. Sandbox files are never copied into the
public tree by this command; only the latest formal chapter pointer and the
curated state document are refreshed.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "sites" / "tinghe-archive" / "public"
DATA = PUBLIC / "data"
STATE = DATA / "story-state.v1.json"
BOOK = DATA / "book.json"
CHAPTERS = DATA / "chapters"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def numeric_chapters() -> list[dict[str, Any]]:
    book = read_json(BOOK)
    chapters = [item for item in book.get("chapters", []) if re.fullmatch(r"c\d+", str(item.get("id", ""))) and item.get("id") != "c999"]
    return sorted(chapters, key=lambda item: float(item.get("no", 0)))


def validate_state(state: dict[str, Any], chapters: list[dict[str, Any]]) -> None:
    if not chapters:
        raise SystemExit("No formal chapters found; refusing to publish an empty work state.")
    latest = chapters[-1]
    source = state.get("source_chapter")
    if source and source != latest.get("id"):
        raise SystemExit(f"State points at {source}, but latest formal chapter is {latest.get('id')}; update the curated state first.")
    if state.get("publication_status") != "LIVE":
        raise SystemExit("Public state must remain LIVE; sandbox status cannot be published as the work.")


def publish(check_only: bool = False) -> dict[str, Any]:
    state = read_json(STATE)
    chapters = numeric_chapters()
    validate_state(state, chapters)
    latest = chapters[-1]
    state["source_chapter"] = latest["id"]
    state["generated_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    progress = state.setdefault("progress", {})
    progress["completed_scenes"] = int(float(latest.get("no", len(chapters))))
    progress["published_units"] = len(chapters)
    progress["current_label"] = latest.get("title") or latest["id"]
    progress["current_time"] = latest.get("time") or progress.get("current_time", "UNKNOWN")
    latest_public = state.setdefault("production", {}).setdefault("latest_public", {})
    latest_public.update({"kind": "正式小说场", "label": latest.get("title") or latest["id"], "href": f"#/read/{latest['id']}"})
    if not check_only:
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"source_chapter": state["source_chapter"], "completed_scenes": progress["completed_scenes"], "published_units": progress["published_units"], "check_only": check_only}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="validate the formal/public boundary without writing")
    args = parser.parse_args()
    print(json.dumps(publish(check_only=args.check_only), ensure_ascii=False))


if __name__ == "__main__":
    main()
