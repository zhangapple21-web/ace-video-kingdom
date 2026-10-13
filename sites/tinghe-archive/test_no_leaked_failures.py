#!/usr/bin/env python3
"""Fail loudly when a published episode's latest audit verdict is not PASS.

Found on 2026-10-13. liufang/ep15.json was built and published at 08:28; its
audit came back FAIL with three real continuity problems at 11:17. Because the
whole deploy chain had already stopped at 08:57 with AUDIT_FAILED,
apply_quarantine.py never ran again, so the failure was never turned into a hold.
The result was bad text sitting on the live site with nothing recording that it
was bad — the one state this whole hold-list mechanism exists to prevent.

The hold list itself was never wrong; it was simply never recomputed after a
late audit. This check runs independently of the deploy chain and reports the
mismatch, so the condition cannot pass unnoticed again. It reports rather than
rewrites: deciding to unpublish is a call for apply_quarantine, which knows
about the stability rule.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
PUBLIC = HERE / "public" / "data" / "originals"


def main() -> int:
    recs = [r for r in json.loads((HERE / "audit_failures.json").read_text(encoding="utf-8"))
            if isinstance(r, dict)]

    latest: dict[tuple[str, str], dict] = {}
    for r in recs:
        key = (r.get("work"), r.get("episode"))
        if key[0] is None or key[1] is None:
            continue
        if key not in latest or str(r.get("timestamp", "")) > str(latest[key].get("timestamp", "")):
            latest[key] = r

    try:
        held = {(h.get("work"), h.get("episode"))
                for h in (json.loads((HERE / "quarantine.json").read_text(encoding="utf-8-sig"))
                          .get("held") or [])}
    except (OSError, json.JSONDecodeError):
        held = set()

    published = {(d.name, p.stem)
                 for d in PUBLIC.iterdir() if d.is_dir()
                 for p in d.glob("ep*.json")}
    # The published tree is keyed by directory name, which matches the work id.

    problems: list[str] = []
    print(f"published episodes on disk: {len(published)}")
    print(f"audited episodes:           {len(latest)}")
    print(f"currently held:             {len(held)}")
    print()

    for (work, ep), row in sorted(latest.items()):
        audit = row.get("audit") or {}
        if audit.get("status") == "PASS":
            continue
        published_here = (work, ep) in published
        held_here = (work, ep) in held
        if published_here and not held_here:
            issues = audit.get("issues") or []
            first = str(issues[0].get("description", "")).strip() if issues else ""
            first = " ".join(first.split())[:120]
            problems.append(f"{work}/{ep}")
            print(f"[LEAKED] {work}/{ep}  verdict={audit.get('status')} "
                  f"issues={len(issues)}  audit_at={str(row.get('timestamp',''))[:19]}")
            print(f"         published but NOT on the hold list")
            if first:
                print(f"         {first}")

    print()
    if problems:
        print(f"FAIL: {len(problems)} published episode(s) carry a non-PASS verdict "
              f"without being held: {', '.join(problems)}")
        print("Run apply_quarantine.py to recompute the hold list, then rebuild.")
        return 1
    print("PASS: every published episode's latest verdict is PASS or it is held")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
