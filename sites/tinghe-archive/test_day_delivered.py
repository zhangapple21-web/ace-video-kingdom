#!/usr/bin/env python3
"""Pin the rule that decides whether today actually shipped.

Two real bugs motivated this, both of which made a checker report success for a
day that produced nothing:

1. Judging only the newest receipt. A `--no-write` reconcile carries no new
   content but overwrites a stalled morning and reads as success.
2. Reading only the `delivered_episodes` key. Receipts written before that field
   existed have no `delivered`, and "unknown" was being treated as "delivered" —
   the precise failure the receipt mechanism exists to prevent. The authored-count
   delta is the fallback.

The cases below use the actual receipt shapes recorded on 2026-10-08.
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
    base = {"date": "2026-10-08", "finished_at": "2026-10-08T08:00:39+08:00",
            "status": "DEPLOYED", "ok": True}
    base.update(kw)
    return base


def main() -> int:
    print("--- delivered_episodes: explicit field, then count delta, then unknown ---")
    check(m.delivered_episodes({"delivered_episodes": 5}) == 5, "explicit field wins")
    check(m.delivered_episodes({"eps_authored_before": 42,
                                "eps_authored_after": 43}) == 1,
          "delta is used when the field is absent (old receipt format)")
    check(m.delivered_episodes({"eps_authored_before": 42,
                                "eps_authored_after": 40}) == 0,
          "a shrinking count is never reported as negative delivery")
    check(m.delivered_episodes({"status": "DEPLOYED"}) is None,
          "no signal at all reads as unknown, not zero")

    print("\n--- day_delivered: a real delivery anywhere in the day counts ---")
    served, why = m.day_delivered([
        receipt(finished_at="2026-10-08T08:00:39+08:00", mode="full",
                delivered_episodes=0, stalled=True),
        receipt(finished_at="2026-10-08T10:19:36+08:00", mode="no-write",
                delivered_episodes=0),
    ])
    check(not served, "a no-write reconcile after a stalled morning does NOT count")
    check("no full or catch-up run" in why or "none reached" in why,
          f"reason names the real cause: {why}")

    served, _ = m.day_delivered([
        receipt(finished_at="2026-10-08T08:00:39+08:00", mode="full", delivered_episodes=0),
        receipt(finished_at="2026-10-08T09:21:05+08:00", mode="full", delivered_episodes=1,
                status="DEPLOYED", ok=True),
        receipt(finished_at="2026-10-08T10:19:36+08:00", mode="no-write", delivered_episodes=0),
    ])
    check(served, "a real published delivery earlier in the day is remembered")

    print("\n--- old-format receipts only (no delivered field) ---")
    served, _ = m.day_delivered([
        {"date": "2026-10-08", "finished_at": "2026-10-08T08:00:39+08:00",
         "status": "DEPLOYED", "ok": True, "mode": "full",
         "eps_authored_before": 42, "eps_authored_after": 42},
    ])
    check(not served, "old-format receipt with 0 growth is read as no delivery")
    served, _ = m.day_delivered([
        {"date": "2026-10-08", "finished_at": "2026-10-08T09:21:05+08:00",
         "status": "DEPLOYED", "ok": True, "mode": "full",
         "eps_authored_before": 42, "eps_authored_after": 43},
    ])
    check(served, "old-format receipt with growth and a completed deploy is served")

    print("\n--- no runs at all ---")
    served, why = m.day_delivered([])
    check(not served, "an empty day is not a served day")
    served, why = m.day_delivered([receipt(mode="no-write", delivered_episodes=0)])
    check(not served, "only no-write runs means nothing was delivered")

    print()
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: today counts as served only when content was really written")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
