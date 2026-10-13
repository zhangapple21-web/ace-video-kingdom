#!/usr/bin/env python3
"""Sync each work's `status` string with what is actually readable.

The desk card prints `status` verbatim, so a stale value is a reader-visible lie.
Two things have to be true at once:

  * count what a reader can open, not what has been authored — an episode listed
    in ``quarantine.json`` is held out of the public tree;
  * do not imply a contiguous range when there are gaps. "EP01–05 可读" under a
    work whose ep03 is held back promises a chapter that is not there, and the
    reader only finds out by clicking it.

So held-back numbers are rendered explicitly as ranges: `EP01–02, EP04–06 可读`.
A gap in the numbering is honest information; hiding it behind a count is not.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
base = ROOT / "originals_source"

held: set[tuple[str, str]] = set()
_qpath = ROOT / "quarantine.json"
if _qpath.is_file():
    _q = json.loads(_qpath.read_text(encoding="utf-8-sig"))
    held = {(i.get("work"), i.get("episode"))
            for i in ((_q.get("held") if isinstance(_q, dict) else _q) or [])}


def ranges(numbers: list[int]) -> str:
    """[1,2,4,5,6] -> 'EP01–02, EP04–06' with an en dash, matching the site's style.

    Every span carries its own ``EP`` prefix. Emitting ``EP01–02, 04–06`` reads
    as one list until someone spots that ``04`` is not an episode number, and the
    status string is the one field a reader takes literally.
    """
    if not numbers:
        return ""
    spans: list[list[int]] = []
    for n in sorted(numbers):
        if spans and n == spans[-1][1] + 1:
            spans[-1][1] = n
        else:
            spans.append([n, n])
    parts = []
    for lo, hi in spans:
        span = f"{lo:02d}" if lo == hi else f"{lo:02d}\u2013{hi:02d}"
        parts.append(f"EP{span}")
    return ", ".join(parts)


changed = 0
for w in sorted(base.glob("*/work.json")):
    d = json.loads(w.read_text(encoding="utf-8"))
    wid = d.get("id", w.parent.name)
    episodes = d.get("episodes", [])
    if not episodes:
        continue

    def num_of(ep: dict) -> int:
        n = ep.get("no")
        if n is None:
            digits = "".join(c for c in ep.get("id", "") if c.isdigit())
            n = int(digits) if digits else 0
        return int(n)

    live = sorted(num_of(ep) for ep in episodes
                  if (wid, ep.get("id")) not in held)
    if not live:
        continue

    new = f"{ranges(live)} 可读"
    old = d.get("status", "")
    if old != new:
        d["status"] = new
        w.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        gap = f"  ({len(episodes) - len(live)} quarantined)" if len(live) != len(episodes) else ""
        print(f"{wid:<12} {old!r} -> {new!r}{gap}")
        changed += 1
    else:
        print(f"{wid:<12} already correct: {new!r}")
print(f"\nchanged: {changed}")
