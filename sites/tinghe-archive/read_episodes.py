#!/usr/bin/env python3
"""Print episodes as readable prose, so the genre question can be judged by reading.

Word-count measures are not an argument about whether something is fun. A payoff
can be written without any of the words a payoff-word list contains. This exists
because the vocabulary measurement said "32 payoff words across 55 episodes" and
that number needs to be checked against the actual text before anyone acts on it —
the list itself was written by the same party that wants the conclusion.

Usage:  py -3 read_episodes.py [work] [count] [--from N]
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")


def render(work: str, count: int, start: int) -> None:
    data = json.loads((SOURCE / work / "work.json").read_text(encoding="utf-8"))
    print("=" * 72)
    print(f"{data.get('title')}   [tone: {data.get('tone')}]")
    if data.get("logline"):
        print(f"logline: {data['logline']}")
    print("=" * 72)
    eps = sorted(data.get("episodes", []), key=lambda e: e.get("no") or 0)
    for ep in eps[start:start + count]:
        print()
        print(f"--- {ep['id']}  第{ep.get('no')}集《{ep.get('title')}》")
        if ep.get("beat"):
            print(f"    beat: {ep['beat']}")
        print()
        for b in ep.get("blocks") or []:
            if not isinstance(b, dict):
                continue
            k = b.get("k")
            if k == "scene":
                print(f"  场景｜{b.get('place')}｜{b.get('time')}｜{b.get('light')}")
            elif k == "cast":
                print(f"  在场：{'、'.join(b.get('present') or [])}"
                      f"　缺席：{'、'.join(b.get('absent') or [])}")
            elif k == "line":
                who = b.get("who") or b.get("speaker") or ""
                print(f"  {who}：{b.get('t','')}")
            elif k == "hook":
                print(f"  〔钩子〕{b.get('t','')}")
            else:
                print(f"  {b.get('t','')}")


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--from"]
    start = 0
    if "--from" in sys.argv:
        try:
            start = int(sys.argv[sys.argv.index("--from") + 1])
        except (IndexError, ValueError):
            start = 0
    work = args[0] if args else "zhenqianjin"
    count = int(args[1]) if len(args) > 1 else 1
    if work not in DOMAIN:
        print(f"unknown work {work}; choose from {', '.join(DOMAIN)}")
        return 1
    render(work, count, start)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())