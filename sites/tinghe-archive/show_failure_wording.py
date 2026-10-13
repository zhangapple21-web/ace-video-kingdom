#!/usr/bin/env python3
"""Print the raw first issue for each failing episode, grouped by classification.

`classify_failures.py` decides whether a FAIL is a content defect or a tool
failure by matching wording. That is a judgement about the auditor's own output,
so it needs to be checkable rather than trusted: this prints what each verdict
actually said, so the split can be eyeballed against the real descriptions.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
LEDGER = HERE / "audit_failures.json"

import importlib.util
spec = importlib.util.spec_from_file_location("cf", HERE / "classify_failures.py")
cf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cf)


def main() -> int:
    rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        latest[(r.get("work"), r.get("episode"))] = r

    tool, content = [], []
    for (work, ep), row in sorted(latest.items()):
        audit = row.get("audit") or {}
        if audit.get("status") == "PASS":
            continue
        issues = audit.get("issues") or []
        kinds = {cf.classify(str(i.get("description", ""))) for i in issues}
        entry = (f"{work}/{ep}", issues)
        (content if "CONTENT" in kinds else tool).append(entry)

    for title, group in (("TOOL FAILURE (no verdict was reached)", tool),
                         ("CONTENT DEFECT", content)):
        print(f"===== {title} — {len(group)} =====")
        for label, issues in group:
            i = issues[0]
            print(f"\n{label}  [{i.get('type')}/{i.get('severity')}]")
            print("  " + " ".join(str(i.get("description", "")).split())[:230])
            if len(issues) > 1:
                print(f"  (+{len(issues) - 1} more issue(s))")
        print()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
