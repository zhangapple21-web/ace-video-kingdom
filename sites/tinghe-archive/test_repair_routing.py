#!/usr/bin/env python3
"""The repair runner must not send a writer to an episode that needs no writing.

Five of the eight episodes held on the night of 2026-10-10 were held only because
a PASS had not been corroborated a second time. The runner handed them to a
writer anyway; the writer found nothing wrong, changed nothing, and the runner
moved on without ever auditing — `repair_one` does `continue` on an unchanged
write, so the second look that would have released the episode never happened.

These assertions are about routing and about what confirm_only is allowed to do,
run against the real module with subprocess stubbed. Nothing here calls a model.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("r", HERE / "repair_episodes.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


class Result:
    def __init__(self, code: int = 0, out: str = "", err: str = ""):
        self.returncode = code
        self.stdout = out
        self.stderr = err


def main() -> int:
    # A fixture, not the live hold list. The previous version read quarantine.json
    # and failed the moment a background deploy rewrote it, which is not a test of
    # routing — it is a test of what happened to be held tonight.
    FIXTURE = [
        ("work_a", "ep11", ["PASS_STREAK"]),          # nothing wrong, needs a look
        ("work_b", "ep08", ["PASS_STREAK"]),          # nothing wrong, needs a look
        ("work_c", "ep11", ["CONNECTIVE_SKELETON"]),  # real style defect
        ("work_d", "ep08", ["CLUE_MISPLACED"]),        # real continuity defect
        ("work_e", "ep11", ["OTHER"]),                 # infrastructure failure
    ]

    original_codes, original_reason = m.hold_codes, m.hold_reason

    def fake_codes(work_id: str, ep_id: str) -> list[str]:
        for w, e, codes in FIXTURE:
            if (w, e) == (work_id, ep_id):
                return codes
        return []

    def fake_reason(work_id: str, ep_id: str) -> str | None:
        for w, e, codes in FIXTURE:
            if (w, e) == (work_id, ep_id):
                return f"{w}/{e} held for {codes}"
        return None

    m.hold_codes, m.hold_reason = fake_codes, fake_reason
    try:
        held = [(w, e) for w, e, _ in FIXTURE]
        print("--- holds split by what they are actually for ---")
        need_confirm = [t for t in held if m.needs_corroboration(*t)]
        need_repair = [t for t in held if t not in need_confirm]
        print(f"    corroboration: {len(need_confirm)}   repair: {len(need_repair)}")
        check(len(need_confirm) == 2,
              f"PASS_STREAK goes to corroboration, the rest to repair "
              f"(got {len(need_confirm)}/{len(need_repair)})")
        check(len(need_repair) == 3, f"the three defect holds need a writer")
        check(not (set(need_confirm) & set(need_repair)), "the two groups do not overlap")

        print("\n--- the split reads the hold codes, not the audit verdict ---")
        for w, e in held:
            codes = m.hold_codes(w, e)
            streak = "PASS_STREAK" in codes
            check(m.needs_corroboration(w, e) == streak,
                  f"{w}/{e} codes={codes} -> corroboration={streak}")
    finally:
        m.hold_codes, m.hold_reason = original_codes, original_reason

    print("\n--- an episode not on the list is never routed ---")
    check(not m.needs_corroboration("fanguan", "ep01"),
          "a released episode does not ask for corroboration")

    print("\n--- confirm_only audits; it never asks a writer ---")
    calls: list[list[str]] = []

    def stub_run(cmd, **kwargs):
        calls.append(list(cmd))
        return Result(0, "{}")

    original = m.subprocess.run
    m.subprocess.run = stub_run

    class FakeVerdict:
        @staticmethod
        def status_of(w, e):
            return "PASS"

        @staticmethod
        def issues_of(w, e):
            return []

        @staticmethod
        def settled_pass(w, e, required=2):
            return True

    real_verdict = sys.modules.get("verdict")
    sys.modules["verdict"] = FakeVerdict
    try:
        out = m.confirm_only("fanguan", "ep11", rounds=2)
    finally:
        sys.modules["verdict"] = real_verdict
        m.subprocess.run = original

    check(out == "PASS", f"a settled PASS returns PASS (got {out})")
    check(len(calls) == 1, f"it stops as soon as the PASS settles (ran {len(calls)} audit(s))")
    check(all(any("run_audit.py" in part for part in c) for c in calls),
          f"it shells out to the auditor: {calls}")
    check(not any("ep11" in c and "blocks" in " ".join(c) for c in calls),
          "no writer prompt was constructed")

    print("\n--- a FAIL from the auditor is reported, and is now actionable ---")
    calls2: list[list[str]] = []

    class FailingVerdict:
        @staticmethod
        def status_of(w, e):
            return "FAIL"

        @staticmethod
        def issues_of(w, e):
            return [{"type": "CLUE_MISPLACED", "severity": "CRITICAL",
                     "description": "x", "evidence_before": "", "evidence_after": ""}]

        @staticmethod
        def settled_pass(w, e, required=2):
            return False

    m.subprocess.run = lambda cmd, **kw: (calls2.append(list(cmd)), Result(0))[1]
    sys.modules["verdict"] = FailingVerdict
    try:
        out2 = m.confirm_only("tuiqun", "ep08", rounds=2)
    finally:
        sys.modules["verdict"] = real_verdict
        m.subprocess.run = original

    check(out2 == "STILL_FAILING", f"a FAIL returns STILL_FAILING (got {out2})")
    check(len(calls2) == 1, f"it stops at the first FAIL ({len(calls2)} audit(s)), "
                            f"since repeating cannot help")

    print("\n--- the prompt no longer claims a defect was found ---")
    block = m.issues_block({"status": "PASS", "issues": []}, "同一个转折骨架用了 11 处。")
    check("没有被指出剧情缺陷" in block, "the block says no plot defect was found")
    check("不要凭空发挥" in block and "那一条改" in block,
          f"it tells the writer to make the one named change only: {block[:60]!r}")
    check("真正的问题" not in block,
          "it no longer asserts that a real problem follows")

    print()
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: corroboration holds are audited, defects are written")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())