#!/usr/bin/env python3
"""Prove the staleness watchdog stops waiting on a corpse and stays audible.

Two real faults on 2026-10-08, both found by watching the task fail:

1. It waited out the full budget on a lock left by a crashed 02:30 repair — it
   treated lock *existence* as proof of a live run.
2. It logged one line and then went silent for the rest of the wait, so a healthy
   wait and a hang looked identical from outside.

These cases drive `wait_for_pipeline` directly with a real lock file, so the
pid path is exercised rather than mocked.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cs", HERE / "check_staleness.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def main() -> int:
    original_root = m.ROOT
    original_log = m.LOG
    original_budget = m.WAIT_BUDGET
    original_poll = m.POLL_SECONDS
    lock = m.ROOT / ".writing.lock"
    backup = lock.read_text(encoding="utf-8") if lock.is_file() else None
    try:
        # A dead pid must not hold the watchdog. 999999 is not a live process.
        lock.write_text(f"started=2026-10-08T02:30:00+08:00 pid=999999\n",
                        encoding="utf-8")
        m.WAIT_BUDGET = 2
        started = time.time()
        m.wait_for_pipeline()
        took = time.time() - started
        check(took < 30, f"a lock from a dead pid does not hold the watchdog ({took:.1f}s)")

        # A live pid (this process) must hold it, and it must keep saying so.
        lock.write_text(f"started={time.strftime('%Y-%m-%dT%H:%M:%S')} pid={os.getpid()}\n",
                        encoding="utf-8")
        m.WAIT_BUDGET = 4
        m.POLL_SECONDS = 1          # drive the real loop quickly
        seen: list[str] = []
        original_log_fn = m.log
        m.log = lambda msg: seen.append(msg) or original_log_fn(msg)
        started = time.time()
        try:
            m.wait_for_pipeline()
        finally:
            m.log = original_log_fn
        took = time.time() - started
        check(took >= 3, f"a live lock does hold the watchdog ({took:.1f}s)")
        check(any("still waiting" in s for s in seen),
              "it keeps logging while waiting (silence looks like a hang)")
        check(any("lock=True" in s for s in seen),
              "it says what it is waiting on")

        # No lock at all: returns immediately.
        lock.unlink(missing_ok=True)
        m.WAIT_BUDGET = 600
        started = time.time()
        m.wait_for_pipeline()
        check(time.time() - started < 5, "no lock means no waiting")

    finally:
        m.WAIT_BUDGET = original_budget
        m.POLL_SECONDS = original_poll
        m.ROOT, m.LOG = original_root, original_log
        if backup is not None:
            lock.write_text(backup, encoding="utf-8")
        else:
            lock.unlink(missing_ok=True)

    print()
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: the watchdog waits on live runs only, and never goes silent")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
