#!/usr/bin/env python3
"""Fix the repair runner's opening log line: it printed twice and lied.

Two defects in one line, both found by reading a 3am log:

  duplicated   _run_repairs contained the identical log(...) call twice, so every
               run opened with its first line repeated. Harmless to read once you
               know, and it trains you to skim past the opening of a repair log,
               which is exactly where the routing decision is stated.

  misleading   it said "repairing N held episode(s) with model pool: <writer
               models>" even when most of N were going to the auditor and no
               writer would run at all. After the corroboration split, a run can
               touch zero writer models and still announce a writer pool.

The replacement reports what will actually happen, which differs by batch.

Idempotent.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE / "repair_episodes.py"

OLD = '''    log(f"repairing {len(targets)} held episode(s) with model pool: {', '.join(models)}")

    log(f"repairing {len(targets)} held episode(s) with model pool: {', '.join(models)}")
'''

NEW = '''    # Say what will actually happen. A batch can be all corroboration, in which
    # case no writer model runs and announcing a writer pool is a lie the reader
    # of the log has to notice and correct.
    if to_confirm:
        log(f"auditing {len(to_confirm)} held episode(s) for corroboration "
            f"(no writer): {', '.join(f'{w}/{e}' for w, e in to_confirm)}")
    if to_repair:
        log(f"repairing {len(to_repair)} held episode(s) with model pool: "
            f"{', '.join(models)}")
    if not to_confirm and not to_repair:
        log("nothing to do")
'''

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if "auditing {len(to_confirm)} held episode(s) for corroboration" in text:
        print("already patched")
        return 0
    check(OLD in text, "found the duplicated, misleading log line")
    if OLD not in text:
        return 1
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("\npatched")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())