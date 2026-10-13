#!/usr/bin/env python3
"""Print one authored episode as plain text, for reading.

Everything built so far has measured rather than read: counts, verdicts, gates.
Prose quality cannot be measured by any of those, and the brief explicitly asks
for human-sounding writing with some literary weight. That can only be checked by
reading the output, so this renders a single episode for that purpose.

Reads from originals_source, not public/, so an episode that is currently held
back can still be read.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: show_episode.py <work_id> <ep_id>")
        return 2
    work_id, ep_id = sys.argv[1], sys.argv[2]

    wf = SOURCE / work_id / "work.json"
    if not wf.is_file():
        print(f"no such work: {work_id}")
        return 1
    data = json.loads(wf.read_text(encoding="utf-8"))
    ep = next((e for e in data.get("episodes", []) if e["id"] == ep_id), None)
    if ep is None:
        print(f"no such episode: {work_id}/{ep_id}")
        return 1

    print("=" * 72)
    print(f"{data.get('title')}  ·  {ep_id}  第{ep.get('no')}集  《{ep.get('title')}》")
    if ep.get("beat"):
        print(f"beat: {ep['beat']}")
    print("=" * 72)
    print()

    for b in ep.get("blocks", []):
        k = b.get("k")
        if k == "scene":
            print(f"【场景】{b.get('place')}  ·  {b.get('time')}  ·  {b.get('light')}")
        elif k == "cast":
            present = "、".join(b.get("present") or [])
            absent = "、".join(b.get("absent") or [])
            line = f"【在场】{present}"
            if absent:
                line += f"    【未出场】{absent}"
            print(line)
        elif k == "para":
            print()
            print(b.get("t", ""))
        elif k == "line":
            print(f"  {b.get('t', '')}")
        elif k == "hook":
            print()
            print("─" * 40)
            print("【钩子】")
            print(b.get("t", ""))
    print()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
