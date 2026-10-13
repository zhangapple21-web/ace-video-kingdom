#!/usr/bin/env python3
"""Backfill audit verdicts for authored episodes that have none.

Context: the audit gate was found to be bypassable on 2026-10-07, so a backlog
built up — 27 authored episodes had never been judged at all, and 8 were live
carrying FAIL. The gate now blocks new failures, but only for episodes it is
asked about; history stays unknown unless someone goes and asks.

This runs the real auditor over every episode in originals_source that has no
verdict yet. Nothing is published, nothing is quarantined, nothing is deployed:
it only fills in the ledger so that "has this ever been checked?" has an answer.
Running it afterwards leaves an honest picture to decide on.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "audit_failures.json"
SOURCE = HERE / "originals_source"
AUDIT = HERE / "run_audit.py"
PROGRESS = HERE / "backfill_progress.json"


def latest() -> dict[tuple[str, str], str]:
    if not LEDGER.is_file():
        return {}
    out: dict[tuple[str, str], str] = {}
    for row in json.loads(LEDGER.read_text(encoding="utf-8")):
        out[(row.get("work"), row.get("episode"))] = (row.get("audit") or {}).get("status", "?")
    return out


def authored() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for work_file in sorted(SOURCE.glob("*/work.json")):
        data = json.loads(work_file.read_text(encoding="utf-8"))
        for ep in data.get("episodes", []):
            out.append((data["id"], ep["id"]))
    return out


def save_progress(done: list[dict]) -> None:
    PROGRESS.write_text(json.dumps(done, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = [a for a in sys.argv[1:]]
    force = "--force" in args
    only: set[str] = set()
    for a in args:
        if a.startswith("--only="):
            only = {w.strip() for w in a.split("=", 1)[1].split(",") if w.strip()}

    candidates = authored()
    if only:
        candidates = [k for k in candidates if k[0] in only]
    if force:
        # Re-audit even episodes that already have a verdict. Needed when the
        # context itself changes underneath them: a hardcoded bundle rule once hid
        # fanguan's ep04 from every later audit, so those PASS verdicts were issued
        # blind and had to be re-earned rather than trusted.
        todo = list(candidates)
    else:
        todo = [k for k in candidates if k not in latest()]
    if not todo:
        print("every authored episode already has a verdict; nothing to backfill")
        return 0

    print(f"backfilling {len(todo)} un-audited episode(s)\n")
    done: list[dict] = []
    if PROGRESS.is_file():
        try:
            done = json.loads(PROGRESS.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            done = []
    already = {(d["work"], d["episode"]) for d in done}
    todo = [k for k in todo if k not in already]

    for index, (work, ep) in enumerate(todo, 1):
        started = time.time()
        try:
            subprocess.run(
                [sys.executable, str(AUDIT), work, ep],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=HERE, timeout=1800,
            )
        except subprocess.TimeoutExpired:
            print(f"[{index}/{len(todo)}] {work}/{ep} — audit timed out")
        verdict = latest().get((work, ep), "NO_VERDICT")
        print(f"[{index}/{len(todo)}] {work}/{ep} -> {verdict} ({time.time() - started:.0f}s)")
        done.append({"work": work, "episode": ep, "status": verdict})
        save_progress(done)

    verdicts = latest()
    counts: dict[str, int] = {}
    for work, ep in authored():
        v = verdicts.get((work, ep), "NO_VERDICT")
        counts[v] = counts.get(v, 0) + 1
    print("\nfull ledger after backfill:")
    for verdict, count in sorted(counts.items()):
        print(f"  {verdict:<12} {count}")

    failing = sorted(k for k, v in verdicts.items() if v == "FAIL" and k in set(authored()))
    if failing:
        print(f"\ncurrently FAILING ({len(failing)}):")
        for work, ep in failing:
            print(f"  {work}/{ep}")
    print("\nnothing was published, quarantined or deployed by this script")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
