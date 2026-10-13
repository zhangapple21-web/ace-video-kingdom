#!/usr/bin/env python3
"""Written is not published. Pin both halves of that distinction.

On 2026-10-09 the writer produced five episodes in 3.5 minutes, the audit blocked
the deploy, and the pipeline reported the day as served — five episodes the reader
could not open. Two separate faults let that pass:

  1. `day_delivered` counted *authored* episodes, so a blocked deploy looked
     like a delivery.
  2. The catch-up guard listed `PENDING_PUBLISH` (written, not live) as a reason
     to SKIP — the one state that most needs the retry.

Both are asserted here against the real receipt shape from that morning.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("v", HERE / "verify_daily_sync.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def receipt(**kw) -> dict:
    base = {"date": "2026-10-09", "finished_at": "2026-10-09T08:30:59+08:00",
            "status": "AUDIT_FAILED", "ok": False, "mode": "full",
            "delivered_episodes": 5, "eps_authored_before": 45,
            "eps_authored_after": 50}
    base.update(kw)
    return base


def main() -> int:
    print("--- the real case: 5 written, deploy blocked ---")
    served, why = m.day_delivered([receipt()])
    check(not served, "authored-but-blocked is NOT served")
    check("not reach" in why or "written today" in why, f"reason says why: {why}")

    print("\n--- the same 5, this time published ---")
    served, why = m.day_delivered([receipt(status="DEPLOYED", ok=True)])
    check(served, "the same 5 published IS served")
    check("live" in why, f"reason says it is live: {why}")

    print("\n--- a later reconcile must not fake a publish ---")
    served, _ = m.day_delivered([
        receipt(),
        receipt(finished_at="2026-10-09T11:00:02+08:00", mode="no-write",
                status="DEPLOYED", ok=True, delivered_episodes=0),
    ])
    check(not served, "a no-write reconcile after a blocked deploy is not a publish")

    print("\n--- writing nothing at all ---")
    served, why = m.day_delivered([
        receipt(status="DEPLOYED", ok=True, delivered_episodes=0),
    ])
    check(not served, "a run that delivered nothing is not served")
    check("written today" not in why, f"reason does not claim writing: {why}")

    print()
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: the day counts as served only when the reader can open it")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
