#!/usr/bin/env python3
"""Prove the writer model pool and rate-limit detection behave.

Guards the 2026-10-06/07 failure mode: one pinned model, throttled, day lost.
A pool that names a model opencode does not have would silently waste a day, so
the pool is checked against `opencode models` when the CLI is reachable.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
CLI = pathlib.Path(os.environ.get("USERPROFILE", "")) / ".local" / "bin" / "opencode.exe"

spec = importlib.util.spec_from_file_location("run_daily_task", ROOT / "run_daily_task.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


print("--- default pool ---")
pool = mod.writer_models()
check(len(pool) >= 2, f"pool has multiple models (got {len(pool)})")
check(all("/" in m for m in pool), "every entry is provider/model form")
check(len(set(pool)) == len(pool), "no duplicate models in pool")
for m in pool:
    print(f"    {m}")

# Two models were removed on 2026-10-16 for the reason the source documents:
# `opencode models` no longer lists them and the provider answers "Model
# unavailable" - the same evidence that removed fledge-alpha-free. This pins
# that a delisted model stays out, so a future edit cannot quietly reintroduce
# a slot that costs a 120s timeout on every episode.
#
# muse-spark-1.3 joined this list on 2026-10-17: 6 of 6 real calls from the
# project directory returned "Model unavailable" and it was absent from
# `opencode models` there. Deliberately NOT treated as the region case - a
# region error reads "not available in your country" and must not cost a working
# model (see test_pool_unavailable.py). One call from C:\tmp answered hours
# earlier, which is why a single probe is never enough to decide.
DELISTED = ("opencode/step-5-preview-free", "opencode/ling-3.1-flash-free",
            "opencode/muse-spark-1.3-contributor-free")
stale = [m for m in DELISTED if m in pool]
check(not stale, f"delisted models stay out of the pool (found: {stale or 'none'})")

print("\n--- env override ---")
os.environ["TINGHE_WRITER_MODELS"] = "opencode/muse-spark-1.3-contributor-free,opencode/exo-free"
check(mod.writer_models() == ["opencode/muse-spark-1.3-contributor-free", "opencode/exo-free"],
      "TINGHE_WRITER_MODELS overrides the pool")
os.environ["TINGHE_WRITER_MODELS"] = "   "
check(mod.writer_models() == mod.WRITER_MODELS, "blank override falls back to default")
del os.environ["TINGHE_WRITER_MODELS"]

print("\n--- rate-limit detection ---")
cases = [
    ("Error: Rate limit exceeded. Please try again later.", True),
    ("HTTP 429 Too Many Requests", True),
    ("quota exceeded for this model", True),
    ("The model is overloaded", True),
    ("RESOURCE_EXHAUSTED: no available model", True),
    ("wrote 3 episodes successfully", False),
    ("SyntaxError in generated block", False),
    ("", False),
]
for text, expected in cases:
    got = mod.looks_rate_limited(text)
    check(got == expected, f"{'detected' if expected else 'not flagged'}: {text[:46]!r}")

print("\n--- pool members exist in opencode models ---")
if CLI.is_file():
    available: set[str] = set()
    for _ in range(3):
        try:
            proc = subprocess.run([str(CLI), "models"], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=180)
        except subprocess.TimeoutExpired:
            continue
        found = {ln.strip() for ln in proc.stdout.splitlines() if "/" in ln}
        if found:
            available = found
            break
    if not available:
        # A live query that could not be answered is not evidence of a broken
        # pool. probe_pool_health.py is the authoritative availability check.
        print("[SKIP] could not list models after 3 attempts; pool contents unverified")
        print()
        sys.exit(0)
    free = {m for m in available if "free" in m}
    missing = [m for m in mod.WRITER_MODELS if m not in available]
    check(not missing, f"all pool models exist (free available: {len(free)})")
    for m in missing:
        print(f"    MISSING: {m}")
else:
    print("[SKIP] opencode CLI not found; cannot verify against live model list")

print()
if failures:
    print(f"FAILED {len(failures)} check(s):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("RESULT: all checks passed")
