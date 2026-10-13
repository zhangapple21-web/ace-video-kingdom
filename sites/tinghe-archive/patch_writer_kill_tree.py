#!/usr/bin/env python3
"""Make _terminate actually stop the writer's children, as its docstring claims.

The docstring has always said "Stop the writer and anything it spawned", and the
body has always been `proc.terminate()` / `proc.kill()` — which reach only the
direct child. `opencode run` forks a pair of python processes underneath the CLI
and those outlive it.

This is the same defect found and fixed in repair_episodes.py the same evening,
in the other of the two places that launches the writer. test_writer_completion
exposes it without knowing it: its fake CLIs hang forever and each full-suite run
left two of them behind on the machine.

Importing kill_tree rather than copying it keeps one definition — two
implementations of "kill the tree" is how two components drift apart, which is
the reason verdict.py exists.

Idempotent.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE / "run_daily_task.py"

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


OLD = '''def _terminate(proc) -> None:
    """Stop the writer and anything it spawned, then reap it."""
    for killer in (proc.terminate, proc.kill):
        try:
            killer()
            proc.wait(timeout=15)
            return
        except Exception:
            continue'''

NEW = '''def _terminate(proc) -> None:
    """Stop the writer and anything it spawned, then reap it.

    "Anything it spawned" used to be a claim rather than a fact: proc.terminate()
    and proc.kill() reach only the direct child, and `opencode run` forks a pair
    of python processes beneath the CLI that outlive it. Every terminated writer
    left two orphans, and test_writer_completion leaves two more behind each run
    by the same route.

    kill_tree walks the process tree on Windows; the per-process kill stays as
    the fallback for platforms without a tree walk.
    """
    from repair_episodes import kill_tree

    for killer in (lambda: kill_tree(proc.pid), proc.terminate, proc.kill):
        try:
            killer()
            proc.wait(timeout=15)
            return
        except Exception:
            continue'''

IMPORT_ANCHOR = "import subprocess\n"


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if "kill_tree(proc.pid)" in text:
        print("already patched")
        return 0
    check(OLD in text, "found _terminate")
    if OLD not in text:
        return 1
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("\npatched _terminate")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())