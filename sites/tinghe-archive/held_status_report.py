#!/usr/bin/env python3
"""What is the true state of every held episode, after this repair round?

Three episodes logged "exhausted N models; last state kept" — which reads like
failure — while a later check showed their latest audit verdict was PASS. The
model runs its own audit (the directive tells it to), so the ledger can hold a
PASS the repair script never got to confirm.

Settled PASS is what releases a hold, and it takes two consecutive PASSes on
unchanged text. This reports, per episode: the latest verdict, its pass streak,
whether the text has changed since that audit, and what that means for the hold.
Deciding is apply_quarantine's job; this only reads.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
LEDGER = HERE / "audit_failures.json"


def main() -> int:
    rows = [r for r in json.loads(LEDGER.read_text(encoding="utf-8")) if isinstance(r, dict)]
    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        k = (r.get("work"), r.get("episode"))
        if k not in latest or str(r.get("timestamp", "")) > str(latest[k].get("timestamp", "")):
            latest[k] = r

    try:
        q = json.loads((HERE / "quarantine.json").read_text(encoding="utf-8-sig"))
        held = [(h["work"], h["episode"]) for h in (q.get("held") or [])]
    except (OSError, json.JSONDecodeError):
        held = []

    print(f"{'episode':<22}{'verdict':<8}{'streak':>7}  {'held':<6} note")
    print("-" * 74)
    releasable = []
    for work, ep in sorted(held):
        row = latest.get((work, ep), {})
        a = row.get("audit") or {}
        verdict = str(a.get("status"))
        streak = row.get("pass_streak")
        note = ""
        if verdict == "PASS" and (streak or 0) >= 2:
            note = "settled PASS -> releasable on the next apply_quarantine"
            releasable.append(f"{work}/{ep}")
        elif verdict == "PASS":
            note = "one PASS only -> needs one more on unchanged text"
        else:
            n = len(a.get("issues") or [])
            note = f"{n} issue(s) still open -> needs another repair"
        print(f"  {work + '/' + ep:<20}{verdict:<8}{str(streak):>7}  {'yes':<6} {note}")

    print()
    if releasable:
        print("ready to release:", ", ".join(releasable))
    else:
        print("none releasable yet")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())