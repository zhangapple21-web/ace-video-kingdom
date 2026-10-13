#!/usr/bin/env python3
"""Give episodes that hold a single PASS their confirming audit.

An episode is released only after two consecutive PASS verdicts on unchanged text,
because a single passing sample is a sample rather than a confirmation. On
2026-10-07 twelve FAILs turned out to be a parser bug that discarded perfectly good
verdicts — three of them said PASS. Once that was fixed, those episodes landed on a
single PASS each, and the release rule correctly kept them held while waiting for
corroboration.

This runs the confirming audit for exactly those episodes. It changes nothing but
the ledger; the hold list is re-derived afterwards.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verdict  # noqa: E402

SOURCE = HERE / "originals_source"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")


def needs_confirmation() -> list[tuple[str, str]]:
    """Episodes that are actually blocked and waiting on corroboration.

    Only episodes in the hold list can be waiting: the release rule never withholds
    content that is already published and passing, so auditing those would be hours
    of work that changes nothing a reader sees.
    """
    held: set[tuple[str, str]] = set()
    q = HERE / "quarantine.json"
    if q.is_file():
        data = json.loads(q.read_text(encoding="utf-8-sig"))
        for item in (data.get("held") if isinstance(data, dict) else data) or []:
            held.add((item.get("work"), item.get("episode")))

    out = []
    for wf in sorted(SOURCE.glob("*/work.json")):
        d = json.loads(wf.read_text(encoding="utf-8"))
        if d.get("id") not in DOMAIN:
            continue
        for ep in d.get("episodes", []):
            work, eid = d["id"], ep["id"]
            if (work, eid) not in held:
                continue
            if verdict.status_of(work, eid) == "PASS" and not verdict.settled_pass(work, eid):
                out.append((work, eid))
    return out


def main() -> int:
    targets = needs_confirmation()
    if not targets:
        print("every PASS already has its confirming audit; nothing to corroborate")
        return 0
    print(f"confirming {len(targets)} episode(s) that hold a single PASS\n")
    settled, still_single = [], []
    for i, (work, ep) in enumerate(targets, 1):
        started = time.time()
        subprocess.run([sys.executable, str(HERE / "run_audit.py"), work, ep],
                       cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
        status = verdict.status_of(work, ep)
        streak = verdict.pass_streak(work, ep)
        mark = "settled" if verdict.settled_pass(work, ep) else f"streak {streak}"
        print(f"[{i}/{len(targets)}] {work}/{ep} -> {status} ({mark}, {time.time() - started:.0f}s)")
        if verdict.settled_pass(work, ep):
            settled.append(f"{work}/{ep}")
        else:
            still_single.append(f"{work}/{ep}")

    print()
    print(f"settled and releasable : {len(settled)}")
    for item in settled:
        print(f"  {item}")
    print(f"still on a single PASS : {len(still_single)}")
    for item in still_single:
        print(f"  {item}")
    print("\nnothing was published or un-quarantined by this script")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
