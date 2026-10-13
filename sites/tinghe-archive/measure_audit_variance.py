#!/usr/bin/env python3
"""Measure how often the auditor flips its verdict on unchanged text.

Before spending hours of model time repairing sixteen FAIL verdicts, it is worth
knowing how many of those verdicts are noise. The auditor is a model reading a
long context; its output has already been seen flipping on identical text
(tingjijia/ep05 PASS then FAIL ten minutes apart; fanguan/ep08 FAIL then PASS with
no edit at all).

If repeated audits of the same bytes disagree often, then a FAIL is weak evidence
and automated repair is chasing a moving target — the honest response is to say so,
not to burn the budget. If they agree, the sixteen failures are real and worth
fixing. Either answer is useful; not measuring is not.

Each repetition is recorded with the content hash it judged, so a change in the
text mid-run is detectable rather than silently mixed in.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPEATS = 3
TARGETS = [
    ("fanguan", "ep03"),
    ("fanguan", "ep09"),
    ("liufang", "ep08"),
    ("tuiqun", "ep07"),
]


def main() -> int:
    spec = importlib.util.spec_from_file_location("v", HERE / "verdict.py")
    verdict = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verdict)

    print(f"auditing {len(TARGETS)} episode(s) x {REPEATS} times, unchanged text\n")
    print(f"{'episode':<22}{'results':<26}{'agree?'}")
    print("-" * 62)

    unstable: list[str] = []
    for work, ep in TARGETS:
        seen: list[str] = []
        hashes: set[str] = set()
        for _ in range(REPEATS):
            subprocess.run([sys.executable, str(HERE / "run_audit.py"), work, ep],
                           cwd=HERE, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
            row = verdict.verdicts().get((work, ep)) or {}
            seen.append(str(row.get("audit", {}).get("status", "?")))
            if row.get("content_sha"):
                hashes.add(row["content_sha"])
        agree = len(set(seen)) == 1
        if not agree:
            unstable.append(f"{work}/{ep}")
        hnote = "" if len(hashes) <= 1 else "  (TEXT CHANGED MID-RUN)"
        print(f"{work}/{ep:<15}{','.join(seen):<26}{'yes' if agree else 'NO'}{hnote}")

    print()
    total = len(TARGETS) * REPEATS
    print(f"{len(unstable)} of {len(TARGETS)} episodes changed verdict on unchanged text "
          f"across {total} audits")
    if unstable:
        print("\nunstable: " + ", ".join(unstable))
        print("\nA FAIL from this auditor is weak evidence. Repairing against it is")
        print("chasing a moving target; the fix is a less noisy gate or a human, not")
        print("more model attempts. Report this rather than spending the budget.")
        return 1
    print("\nverdicts are reproducible on unchanged text; the FAILs are real and")
    print("worth repairing.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
