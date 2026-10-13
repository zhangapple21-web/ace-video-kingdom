#!/usr/bin/env python3
"""Dump the repaired episodes for reading, because a PASS is not a verdict.

Two episodes have now reached a settled PASS and two more are one audit away.
Both numbers come from audits the repair models ran themselves, and on this
project an audit has already fabricated a defect once. Reading the prose is the
cheapest independent check there is: a rewrite that satisfies the auditor by
being blander, shorter or more repetitive than the original passes cleanly and is
still worse.

Reports length and beat changes against the pre-repair backup when one exists,
so a compression is visible rather than inferred.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
BACKUPS = HERE / "backup_rewrite"

TARGETS = (("fanguan", "ep14"), ("fanguan", "ep15"),
           ("liufang", "ep15"), ("tuiqun", "ep14"))


def narration(ep: dict) -> str:
    return "".join(str(b.get("t", "")) for b in ep.get("blocks") or []
                   if isinstance(b, dict) and b.get("k") in {"para", "line", "hook"})


def dump(work: str, ep_id: str, out: pathlib.Path) -> tuple[int, str]:
    data = json.loads((SOURCE / work / "work.json").read_text(encoding="utf-8"))
    ep = next(e for e in data["episodes"] if e.get("id") == ep_id)
    lines = [f"WORK {work}  {ep_id}", f"BEAT: {ep.get('beat')}", ""]
    for b in ep.get("blocks") or []:
        if not isinstance(b, dict):
            continue
        k = b.get("k")
        if k == "scene":
            lines.append(f"[场景] {b.get('place')} | {b.get('time')}")
        elif k == "cast":
            lines.append(f"[出场] {b.get('present')}  未出场 {b.get('absent')}")
        elif k in ("para", "hook"):
            lines.append(str(b.get("t", "")))
        elif k == "line":
            lines.append(f"{b.get('who')}：{b.get('t', '')}")
    body = "\n".join(lines)
    out.write_text(body, encoding="utf-8")
    return len(narration(ep)), str(ep.get("beat") or "")


def old_length(work: str, ep_id: str) -> int | None:
    """Length before the repair round, from the oldest backup of this episode."""
    cands = sorted(BACKUPS.glob(f"*_{work}_{ep_id}_work.json"))
    if not cands:
        return None
    try:
        data = json.loads(cands[0].read_text(encoding="utf-8"))
        ep = next((e for e in data.get("episodes", []) if e.get("id") == ep_id), None)
        return len(narration(ep)) if ep else None
    except (OSError, json.JSONDecodeError):
        return None


def main() -> int:
    print(f"{'episode':<20}{'now':>7}{'before':>9}{'delta':>8}   file")
    print("-" * 74)
    for work, ep_id in TARGETS:
        out = HERE / f"_read_{work}_{ep_id}.txt"
        now, beat = dump(work, ep_id, out)
        before = old_length(work, ep_id)
        if before is None:
            delta, before_s = "?", "?"
        else:
            delta, before_s = f"{now - before:+d}", str(before)
        print(f"  {work + '/' + ep_id:<18}{now:>7}{before_s:>9}{delta:>8}   {out.name}")
    print()
    print("A negative delta on an episode with several defects is the one to read")
    print("closely: it may have been shortened into passing.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())