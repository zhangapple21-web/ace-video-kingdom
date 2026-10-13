#!/usr/bin/env python3
"""Prove run() bounds a hung child instead of tearing down the day.

Regression guard for the 2026-10-06 failure: an uncaught TimeoutExpired killed
the whole daily run, so episodes the writer had already finished never shipped.
Exit 0 only if a slow child is reported as a failed step and the caller keeps
running.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("run_daily_task", ROOT / "run_daily_task.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

print("--- case 1: child slower than the timeout ---")
code, out = mod.run(
    [sys.executable, "-c", "import time; print('starting', flush=True); time.sleep(60)"],
    "selftest_hang",
    timeout=3,
)
print(f"returned code={code}")
print(f"out={out!r}")
ok_timeout = code == 124 and "timeout after 3s" in out
print(f"[{'PASS' if ok_timeout else 'FAIL'}] hung child reported as code 124, not an exception")

print()
print("--- case 2: normal child still passes through ---")
code, out = mod.run(
    [sys.executable, "-c", "print('all good')"],
    "selftest_ok",
    timeout=30,
)
ok_ok = code == 0 and "all good" in out
print(f"[{'PASS' if ok_ok else 'FAIL'}] healthy child unaffected (code={code})")

print()
print("--- case 3: failing child still reports its exit code ---")
code, out = mod.run(
    [sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"],
    "selftest_fail",
    timeout=30,
)
ok_fail = code == 3
print(f"[{'PASS' if ok_fail else 'FAIL'}] failing child keeps its code (code={code})")

all_ok = ok_timeout and ok_ok and ok_fail
print()
print("RESULT:", "all cases passed" if all_ok else "SOME CASES FAILED")
sys.exit(0 if all_ok else 1)
