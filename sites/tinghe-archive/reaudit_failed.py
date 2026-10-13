#!/usr/bin/env python3
"""Re-audit episodes that are live but carry an unresolved FAIL verdict.

Context on 2026-10-07: the audit gate turned out to be bypassable, so eight
published episodes were still carrying FAIL verdicts when they shipped. The gate
is fixed and now blocks new failures, but it cannot un-publish history. This
re-audits them against the *current* bundle — which now includes the facts table
and per-episode summaries that did not exist when they were first judged — so the
verdict reflects what a reader would hit today, not a stale snapshot.

Writes nothing to public/ and deploys nothing. It only updates the verdict
ledger; quarantining the survivors is a separate, explicit decision.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "audit_failures.json"
AUDIT = HERE / "run_audit.py"


def latest_verdicts() -> dict[tuple[str, str], str]:
    if not LEDGER.is_file():
        return {}
    out: dict[tuple[str, str], str] = {}
    for row in json.loads(LEDGER.read_text(encoding="utf-8")):
        out[(row.get("work"), row.get("episode"))] = (row.get("audit") or {}).get("status", "?")
    return out


def failing_episodes() -> list[tuple[str, str]]:
    return [k for k, v in sorted(latest_verdicts().items()) if v == "FAIL"]


def main() -> int:
    targets = failing_episodes()
    if not targets:
        print("no FAIL verdicts in the ledger; nothing to re-audit")
        return 0

    print(f"re-auditing {len(targets)} episode(s) that are live with a FAIL verdict:\n")
    still_failing: list[tuple[str, str]] = []
    for work, ep in targets:
        print(f"=== {work}/{ep} ===")
        code = subprocess.run(
            [sys.executable, str(AUDIT), work, ep],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=HERE, timeout=1800,
        ).returncode
        verdict = latest_verdicts().get((work, ep), "?")
        print(f"  -> {verdict} (exit {code})")
        if verdict != "PASS":
            still_failing.append((work, ep))

    print()
    print("=" * 60)
    if still_failing:
        print(f"still FAILING ({len(still_failing)}) - candidates for quarantine:")
        for work, ep in still_failing:
            print(f"  {work}/{ep}")
    else:
        print("all previously-failing episodes now PASS")
    print("\nnothing was deployed or unpublished by this script")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
