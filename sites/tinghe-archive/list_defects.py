#!/usr/bin/env python3
"""Print the audit issues for the quarantined episodes, compactly.

Purpose is to decide how each defect must be repaired. A wrong name or a
contradicting clause is a local edit; a structural problem (a hook that cannot
work because the previous chapter already answered it) needs the beat rewritten.
Knowing which is which before opening 15 files by hand is the difference between
an afternoon and a week.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
LEDGER = HERE / "audit_failures.json"
QUARANTINE = HERE / "quarantine.json"

# Codes that are almost always a local text fix, because the episode's own beat
# still works; the defect is in how a detail was rendered.
LOCAL = {"CHARACTER_INCONSISTENCY", "CLUE_MISPLACED", "OTHER"}


def main() -> int:
    rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        latest[(r.get("work"), r.get("episode"))] = r

    held: list[tuple[str, str]] = []
    q = json.loads(QUARANTINE.read_text(encoding="utf-8-sig"))
    for item in q.get("held") or []:
        held.append((item["work"], item["episode"]))

    structural = 0
    local_only = 0
    for work, ep in held:
        audit = (latest.get((work, ep)) or {}).get("audit") or {}
        issues = audit.get("issues") or []
        codes = {i.get("type") for i in issues}
        kind = "local" if codes <= LOCAL else "structural"
        if kind == "structural":
            structural += 1
        else:
            local_only += 1
        print("=" * 78)
        print(f"{work}/{ep}   issues={len(issues)}   {kind}   {sorted(codes)}")
        print("=" * 78)
        for i, issue in enumerate(issues, 1):
            print(f"  [{i}] {issue.get('type')} / {issue.get('severity')}")
            desc = " ".join(str(issue.get("description", "")).split())
            print(f"      {desc}")
            for key in ("evidence_before", "evidence_after"):
                val = " ".join(str(issue.get(key, "")).split())
                if val:
                    print(f"      {key:<16} {val}")
            print()
        print()

    print("=" * 78)
    print(f"local-only defects     : {local_only}")
    print(f"structural defects     : {structural}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
