#!/usr/bin/env python3
"""Print the raw material for the gap audit so a human can judge it directly.

The regex classifier in gap_audit.py was too crude to be trusted: it read
"把汤色清改成浑浊的人一直没点名" as action rather than as a mystery, which is the
exact opposite. And its scene-name pattern matched nothing, which would have
reported "no place names at all" from a broken pattern rather than from the text.

Both errors point the same way: an unvalidated instrument producing a confident
zero. So this prints the text and stops.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
WORKS = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")


def main() -> int:
    print("=" * 78)
    print("open_hooks 原文（方向由人判，正则不参与）")
    print("=" * 78)
    for wid in WORKS:
        p = SOURCE / wid / "facts.json"
        if not p.is_file():
            continue
        facts = json.loads(p.read_text(encoding="utf-8-sig"))
        hooks = facts.get("open_hooks") or []
        print(f"\n--- {wid}  （{len(hooks)} 条）")
        for h in hooks:
            s = h if isinstance(h, str) else h.get("hook", "")
            print(f"    * {s[:92]}")

    print()
    print("=" * 78)
    print("场景行真实格式（修正则前先看真的长什么样）")
    print("=" * 78)
    seen = 0
    for wid in WORKS:
        wf = SOURCE / wid / "work.json"
        if not wf.is_file():
            continue
        data = json.loads(wf.read_text(encoding="utf-8"))
        names = []
        for ep in data["episodes"]:
            for b in ep.get("blocks") or []:
                t = b.get("t", "") if isinstance(b, dict) else ""
                if isinstance(t, str) and t.startswith("场景"):
                    names.append(t[:76])
        print(f"\n--- {wid}  共 {len(names)} 条场景行")
        for t in names[:4]:
            print(f"    {t}")
        seen += len(names)
    print(f"\n场景行总数 {seen}；若为 0 则说明格式与假设不同，不是没有场景。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
