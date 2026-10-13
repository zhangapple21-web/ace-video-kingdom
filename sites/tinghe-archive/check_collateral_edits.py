#!/usr/bin/env python3
"""Compare each work.json against its newest backup, per episode.

A repair is instructed to touch one episode. Nothing verified that, and the
evidence says it was not respected: while repairing fanguan/ep03, fanguan/ep08's
blocks changed too, and ep08's audit verdict flipped as a result. Silent
collateral edits to chapters nobody asked about are worse than a failed repair,
because they are invisible until an unrelated verdict moves.

Prints exactly which episodes differ, so the guard can be judged against a real
case rather than a hypothetical one.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent / "originals_source"


def load(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    any_diff = False
    for work_dir in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        work = work_dir / "work.json"
        if not work.is_file():
            continue
        backups = sorted(work_dir.glob("work.json.bak-*"))
        if not backups:
            print(f"{work_dir.name:<12} (no backup to compare against)")
            continue
        try:
            now = load(work)
            before = load(backups[-1])
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{work_dir.name:<12} UNREADABLE: {exc}")
            any_diff = True
            continue

        def by_id(data):
            return {e["id"]: e for e in data.get("episodes", [])}

        a, b = by_id(before), by_id(now)
        changed = [eid for eid in sorted(a) if eid in b and a[eid] != b[eid]]
        added = sorted(set(b) - set(a))
        removed = sorted(set(a) - set(b))
        if changed or added or removed:
            any_diff = True
            print(f"{work_dir.name:<12} CHANGED: {', '.join(changed) or '-'}"
                  f"  added={added or '-'} removed={removed or '-'}"
                  f"  (vs {backups[-1].name})")
        else:
            print(f"{work_dir.name:<12} unchanged")
    return 1 if any_diff else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
