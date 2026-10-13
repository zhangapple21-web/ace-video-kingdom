#!/usr/bin/env python3
"""Find pending entries that restate the same fact, before they become table rows.

promote_facts is about to start working again — it classified 0 entries for weeks
because the author was never asked for a `section` key. The first promotion will
therefore flush a backlog of 65 entries into the tables at once.

Some of those restate the same fact at different points in the story:

  fanguan #3  复写联：顾冬三年前借印时垫复写纸所留；ep10后由顾冬带走
  fanguan #11 复写联：顾冬三年前借印垫复写纸所留；ep12后联在卢茨怀里，背面拓下小票红印第二份…

Promoted side by side as "established facts", those two read as a contradiction
and the writer is told not to break established facts. So a naive promotion would
manufacture exactly the continuity damage the table exists to prevent.

This groups entries by a shared prefix within a work, and prints the groups for a
human to look at. It deliberately stops short of deciding which one wins, because
"which version is current" is a reading of the episodes, not a string operation.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
WORKS = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")

# Two entries whose first N characters agree are probably the same fact. Short
# enough to catch "复写联：顾冬三年前借印" against "复写联：顾冬三年前借印垫复写纸",
# long enough not to merge unrelated entries that share an opening phrase.
PREFIX = 10


def payload(entry: dict) -> str:
    for key in ("hook", "fact", "entry", "text", "note"):
        val = entry.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def main() -> int:
    total_groups = 0
    for wid in WORKS:
        p = SOURCE / wid / "facts.json"
        if not p.is_file():
            continue
        facts = json.loads(p.read_text(encoding="utf-8-sig"))
        pending = [e for e in (facts.get("pending") or []) if isinstance(e, dict)]
        groups: dict[str, list[tuple[int, str, str]]] = {}
        for i, entry in enumerate(pending):
            text = payload(entry)
            if not text:
                continue
            groups.setdefault(text[:PREFIX], []).append(
                (i, str(entry.get("source", "?")), text))
        dupes = {k: v for k, v in groups.items() if len(v) > 1}
        if not dupes:
            continue
        total_groups += len(dupes)
        print(f"\n{wid}: {len(dupes)} 组疑似同一事实")
        for key, items in dupes.items():
            print(f"  「{key}…」")
            for idx, src, text in items:
                print(f"     #{idx:<3} {src:<5} {text[:88]}")

    print()
    print("=" * 74)
    if total_groups:
        print(f"{total_groups} 组需要人判「哪一版是当前版本」，再提升。")
        print("不在这里替人做决定——那是读剧本，不是比字符串。")
    else:
        print("没有同前缀碰撞，提升不会造出自相矛盾的行。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
