#!/usr/bin/env python3
"""Separate infrastructure noise from real content defects in the verdict table.

`OTHER` is the catch-all issue code, and the auditor also uses it for its own
failures: JSON parse errors, provider errors, timeouts. Those are not statements
about the episode — they mean no verdict was reached. Counting them as defects
inflates the failure count and holds back readable content for the wrong reason,
which is the exact mistake of quarantining on a broken instrument.

This classifies every `OTHER` by its own description, so the split is visible
rather than assumed. Content-like wording counts as a defect; anything naming a
tool, transport or parse failure does not.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
LEDGER = HERE / "audit_failures.json"

# Wording that means the auditor could not do its job.
TOOL_FAILURE = re.compile(
    r"JSON parse error|Extra data|opencode exited|Upstream request failed|"
    r"provider|timed out|timeout|Subprocess error|No JSON line|"
    r"not found|File not found|rate limit|429|500",
    re.IGNORECASE,
)
# Wording that means a real, readable observation about the text.
CONTENT_LIKE = re.compile(
    r"h3|场景|结构|字数|字数不足|字|段落|对白|钩子|未出场|在场|"
    r"前文|后文|本集|上一集|下一集|矛盾|冲突|不一致",
)


def classify(desc: str) -> str:
    if TOOL_FAILURE.search(desc):
        return "TOOL"
    if CONTENT_LIKE.search(desc):
        return "CONTENT"
    return "UNKNOWN"


def main() -> int:
    rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        latest[(r.get("work"), r.get("episode"))] = r

    real_fail: list[str] = []
    tool_only: list[str] = []
    unknown: list[tuple[str, str, str]] = []

    for (work, ep), row in sorted(latest.items()):
        audit = row.get("audit") or {}
        if audit.get("status") == "PASS":
            continue
        issues = audit.get("issues") or []
        kinds = {classify(str(i.get("description", ""))) for i in issues}
        if "CONTENT" in kinds:
            real_fail.append(f"{work}/{ep}")
        elif "TOOL" in kinds:
            tool_only.append(f"{work}/{ep}")
        else:
            unknown.append((work, ep, str(issues[0].get("description", ""))[:110]))

    print(f"failing episodes          : {len(real_fail) + len(tool_only) + len(unknown)}")
    print(f"  real content defects    : {len(real_fail)}")
    print(f"  tool failures only      : {len(tool_only)}")
    print(f"  unclassified            : {len(unknown)}\n")

    if tool_only:
        print("held for a TOOL failure, not a content defect "
              "(these should NOT be quarantined):")
        for item in tool_only:
            print(f"  {item}")
        print()

    if unknown:
        print("unclassified OTHER — needs a human eye:")
        for work, ep, desc in unknown:
            print(f"  {work}/{ep}: {desc}")
        print()

    print("real content defects:")
    for item in real_fail:
        print(f"  {item}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
