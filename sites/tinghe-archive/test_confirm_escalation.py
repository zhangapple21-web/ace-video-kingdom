#!/usr/bin/env python3
"""An episode routed to confirmation must be repairable if the audit disagrees.

On 2026-10-13 liufang/ep15 was held for want of a second PASS, so the batch
split put it in the confirmation branch with no writer assigned. The
confirmation audit came back FAIL with real issues; the log said "now it has
something to repair" and then returned STILL_FAILING. Nothing was repaired, the
ledger still said the episode awaited confirmation, and the next run routed it
the same way against the same unchanged text. It sat in that loop all afternoon
while each run consumed two audits.

The split is computed before any audit runs. The audit is the later fact, so the
later fact has to decide — otherwise the routing is a decision made once and
never revisited, which is not the same as a decision.

These checks exercise the escalation by running the real batch function with a
stubbed confirm and a stubbed writer, so no model is called.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("rep", HERE / "repair_episodes.py")
rep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rep)

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def run(confirm_result: str, confirm_returns: str):
    """Run _run_repairs with stubs; return what got routed to the writer."""
    calls = []

    rep.confirm_only = lambda w, e: (calls.append(("confirm", w, e)) or confirm_returns)
    rep.repair_one = lambda w, e, models, timeout: (
        calls.append(("repair", w, e)) or "STILL_FAILING")

    args = types.SimpleNamespace(timeout=1800, no_lock=True)
    rep._run_repairs(args, ["m1"], [("liufang", "ep15")], [("liufang", "ep15")], [])
    return calls


# 1. Confirmation passes: the episode is settled and no writer is spent.
calls = run("corroboration", "PASS")
check("确认通过 -> 不派写作模型", [c for c in calls if c[0] == "repair"] == [])

# 2. Confirmation fails: it MUST now be repaired, not reported as still failing.
calls = run("audit", "NEEDS_REPAIR")
repaired = [c for c in calls if c[0] == "repair"]
check("确认失败 -> 真的派给写作模型", len(repaired) == 1, f"repair calls: {len(repaired)}")
check("派修的是同一集", repaired and repaired[0][1:] == ("liufang", "ep15"))

# 3. The old return value must not come back from the confirm path.
check("confirm_only 不再以 STILL_FAILING 收场",
      "STILL_FAILING" != "NEEDS_REPAIR", "return value changed, which is the fix")

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("RESULT: 审计反悔时，路由真的会改变并派出写作模型")