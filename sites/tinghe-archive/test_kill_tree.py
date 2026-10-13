#!/usr/bin/env python3
"""Prove kill_tree() reaches grandchildren, and that proc.kill() does not.

The finding this pins: `opencode run` forks, and every termination path in
repair_episodes.py used to call proc.kill()/proc.terminate(), which reach only
the direct child. Twenty-two orphaned python processes were alive on 2026-10-10,
the oldest nine hours past the run that created it.

So this builds an actual three-level tree — a parent that spawns a child that
spawns a grandchild, the grandchild heartbeating into a file and recording its
own pid — and checks both directions:

  1. killing the parent the old way leaves the grandchild alive  (the bug)
  2. kill_tree(parent) stops the grandchild                     (the fix)

Asserting only the second would let the old call sites come back unnoticed.

Note on cleanup: a first attempt at this used `taskkill /IM python.exe` to sweep
up, which matches the test process itself and killed the run before it printed
anything. Cleanup here is by recorded pid, never by image name.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("r", HERE / "repair_episodes.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


MIDDLE = r"""
import sys, time, subprocess, pathlib
beat = pathlib.Path(sys.argv[1])
subprocess.Popen([sys.executable, "-c", open(sys.argv[2], encoding="utf-8").read(), str(beat)])
time.sleep(120)
"""

BEATER = r"""
import sys, time, json, os, pathlib
beat = pathlib.Path(sys.argv[1])
while True:
    beat.write_text(json.dumps({"t": time.time(), "pid": os.getpid()}))
    time.sleep(0.3)
"""


def spawn_tree(tmp: pathlib.Path, name: str) -> tuple[subprocess.Popen, pathlib.Path]:
    beat = tmp / name
    beater = tmp / f"{name}_beater.py"
    beater.write_text(BEATER, encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-c", MIDDLE, str(beat), str(beater)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        if beat.is_file() and beat.read_text():
            return proc, beat
        time.sleep(0.25)
    return proc, beat


def heartbeat(beat: pathlib.Path) -> float:
    try:
        return json.loads(beat.read_text())["t"]
    except (OSError, ValueError, KeyError):
        return 0.0


def still_heartbeating(beat: pathlib.Path) -> bool:
    first = heartbeat(beat)
    if not first:
        return False
    time.sleep(1.5)
    second = heartbeat(beat)
    return second > first


def read_pid(beat: pathlib.Path) -> int | None:
    try:
        return json.loads(beat.read_text()).get("pid")
    except (OSError, ValueError):
        return None


def kill_pid(pid: int) -> None:
    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                   capture_output=True, timeout=30)


def main() -> int:
    if os.name != "nt":
        print("SKIP: this asserts Windows taskkill behaviour")
        return 0
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="killtree_"))
    print(f"workspace: {tmp}\n")

    try:
        print("--- the old behaviour: kill the direct child only ---")
        parent, beat = spawn_tree(tmp, "old")
        beat_ok = still_heartbeating(beat)
        grandchild = read_pid(beat)
        check(beat_ok and grandchild is not None,
              f"the grandchild is really running before the kill (pid={grandchild})")
        if not (beat_ok and grandchild):
            print("ABORT: the tree did not come up; nothing to prove")
            return 1
        parent.kill()
        try:
            parent.wait(timeout=30)
        except subprocess.TimeoutExpired:
            pass
        alive = still_heartbeating(beat)
        check(alive, "proc.kill() leaves the grandchild running (this is the bug)")
        if alive:
            print(f"      -> orphan pid={grandchild} outlived the direct child")
        if grandchild:
            kill_pid(grandchild)

        print("\n--- the new behaviour: kill_tree ---")
        parent, beat = spawn_tree(tmp, "new")
        beat_ok = still_heartbeating(beat)
        grandchild = read_pid(beat)
        # Without this guard the next check passes vacuously: a beater that never
        # started never keeps beating, so "kill_tree stopped it" is trivially true.
        # That is exactly what the first run of this test did — the beater used
        # `json` without importing it, died on its first write, and the fix
        # appeared to work.
        check(beat_ok and grandchild is not None,
              f"the grandchild is really running before the kill (pid={grandchild})")
        if not (beat_ok and grandchild):
            print("\nABORT: the tree did not come up; the kill_tree check below "
                  "would be meaningless")
            return 1

        m.kill_tree(parent.pid)
        try:
            parent.wait(timeout=30)
        except subprocess.TimeoutExpired:
            pass
        alive = still_heartbeating(beat)
        check(not alive, f"kill_tree stops the grandchild too (pid={grandchild})")
        if not alive:
            print("      -> no orphan left behind")
        if grandchild and alive:
            kill_pid(grandchild)
    finally:
        pass

    print()
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: kill_tree reaches the whole tree; proc.kill() does not")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())