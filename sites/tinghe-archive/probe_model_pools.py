#!/usr/bin/env python3
"""Probe the writer and audit model pools for availability.

Tomorrow's 08:00 run depends on at least one model in each pool answering. The
audit pool already proved itself by recovering from a dead endpoint mid-run, but a
pool is only as good as its healthiest member *now* — and provider outages are not
predictable from here. A cheap probe of every model turns "the 08:00 run might
fail" into "N of 6 answered", which is worth knowing before 08:00 rather than
after.

This only sends a one-line prompt. It writes nothing.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
CLI = pathlib.Path(os.environ.get("USERPROFILE", "")) / ".local" / "bin" / "opencode.exe"
TIMEOUT = 150


def writer_models() -> list[str]:
    import importlib.util
    spec_env = os.environ.get("TINGHE_WRITER_MODELS")
    if spec_env:
        return [m.strip() for m in spec_env.split(",") if m.strip()]
    spec = importlib.util.spec_from_file_location("rdt", HERE / "run_daily_task.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.WRITER_MODELS)


def audit_models() -> list[str]:
    import importlib.util
    spec = importlib.util.spec_from_file_location("ra", HERE / "run_audit.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.audit_models())


def probe(model: str) -> tuple[bool, int, str]:
    cmd = [str(CLI), "run", "--model", model, "只回复两个字：可用"]
    started = time.time()
    try:
        p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, TIMEOUT, "timeout"
    took = int(time.time() - started)
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        first = out.strip().splitlines()[-1][:90] if out.strip() else f"exit {p.returncode}"
        return False, took, first
    return True, took, ""


def main() -> int:
    if not CLI.is_file():
        print(f"opencode CLI missing at {CLI}")
        return 2

    pools = {"writer": writer_models(), "audit": audit_models()}
    dead: list[str] = []
    for pool, models in pools.items():
        print(f"=== {pool} pool ({len(models)}) ===")
        for model in models:
            ok, took, why = probe(model)
            print(f"  [{'OK  ' if ok else 'DEAD'}] {model:<46} {took:>4}s {why}")
            if not ok:
                dead.append(model)
        print()

    if dead:
        print(f"{len(dead)} model(s) unavailable right now: {', '.join(dead)}")
        print("Rotation still works as long as one model per pool answers, so this")
        print("is not automatically fatal. It does mean the pool should be trimmed")
        print("of dead members so a slot is not spent discovering the same outage")
        print("again every run.")
        return 1
    print("every model in both pools answers")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
