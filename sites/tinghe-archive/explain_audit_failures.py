#!/usr/bin/env python3
"""Explain why audited episodes fail, grouped by issue code.

A sudden mass-FAIL rate is a signal about the auditor, not about the episodes. If
27 backfilled episodes fail on one shared technicality, the correct action is to
fix the auditor — not to retract a quarter of the published catalogue. This
script prints the distribution so that distinction can be made on evidence.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
LEDGER = HERE / "audit_failures.json"


def main() -> None:
    rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        latest[(r.get("work"), r.get("episode"))] = r

    by_status = collections.Counter(r["audit"]["status"] for r in latest.values())
    print("latest verdict per episode:", dict(by_status))

    failing = {k: r for k, r in latest.items() if r["audit"]["status"] != "PASS"}
    codes: collections.Counter = collections.Counter()
    for r in failing.values():
        for issue in (r["audit"].get("issues") or r["audit"].get("issues_detail") or []):
            if isinstance(issue, dict):
                codes[issue.get("code") or issue.get("type") or "?"] += 1
            else:
                codes[str(issue)[:40]] += 1
    print(f"\nissue codes across {len(failing)} failing episode(s):")
    for code, n in codes.most_common():
        print(f"  {n:>3}  {code}")

    print("\naudit keys present:", sorted(next(iter(latest.values()))["audit"].keys()))

    print("\n--- full audit payload for the first 3 failures ---")
    for (work, ep), r in list(failing.items())[:3]:
        print(f"\n### {work}/{ep}")
        print(json.dumps(r["audit"], ensure_ascii=False, indent=2)[:1600])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
