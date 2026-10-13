#!/usr/bin/env python3
"""Prove _run_writer_model judges completion by output, not by exit.

This is the fix for the hang that ate 2026-10-06 (6h11m) and 2026-10-07
(16+ min): the opencode CLI writes its episode and then never exits, so waiting
for the process to return is waiting forever.

Three real failure shapes are simulated with a fake writer:
  A. writes an episode, then hangs  -> must be treated as SUCCESS and stopped
  B. exits immediately, writes none -> must be treated as FAILURE
  C. hangs forever, writes nothing   -> must be cut off at the timeout
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("run_daily_task", ROOT / "run_daily_task.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def make_sandbox(tmp: pathlib.Path):
    """Point the module at a scratch tree with one work holding one episode."""
    src = tmp / "originals_source" / "w1"
    src.mkdir(parents=True, exist_ok=True)

    def write_work(n: int) -> None:
        (src / "work.json").write_text(json.dumps({
            "id": "w1", "title": "w1", "tone": "t", "format": "f",
            "status": "s", "logline": "l", "chars": ["a"],
            "episodes": [{"id": f"ep{i:02d}", "no": i, "title": "t", "beat": "b",
                          "blocks": [{"k": "para", "t": "x"}]} for i in range(1, n + 1)],
        }, ensure_ascii=False), encoding="utf-8")

    write_work(1)
    original = {k: getattr(mod, k) for k in ("SOURCE",)}
    mod.SOURCE = tmp / "originals_source"
    return original, write_work


def fake_cli(tmp: pathlib.Path, body: str) -> pathlib.Path:
    """A stand-in for opencode.exe.

    _run_writer_model launches the CLI as a real executable with arguments, so
    the stand-in must be one too: a .cmd that forwards to python and ignores the
    opencode-style flags it is handed.
    """
    py = tmp / "fakewriter.py"
    py.write_text(body, encoding="utf-8")
    shim = tmp / "fakewriter.cmd"
    shim.write_text(
        f'@echo off\r\n"{sys.executable}" "{py}" %*\r\n', encoding="utf-8"
    )
    return shim


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="writerprobe_"))
    original_source, write_work = make_sandbox(tmp)
    # Keep the test fast; production values are documented in the module.
    mod.WRITE_TIMEOUT = 12
    mod.WRITER_EXIT_GRACE = 4
    try:
        before = mod.snapshot_counts()

        print("--- case A: writes an episode then hangs (the real 10-07 bug) ---")
        cli = fake_cli(tmp, (
            "import json,pathlib,time,sys\n"
            f"p = pathlib.Path(r'{tmp / 'originals_source' / 'w1' / 'work.json'}')\n"
            "d = json.loads(p.read_text(encoding='utf-8'))\n"
            "d['episodes'].append({'id':'ep02','no':2,'title':'t','beat':'b',"
            "'blocks':[{'k':'para','t':'x'}]})\n"
            "p.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')\n"
            "print('wrote ep02', flush=True)\n"
            "while True: time.sleep(1)\n"  # hangs forever, like the real CLI
        ))
        t0 = time.time()
        code, out, throttled = mod._run_writer_model(cli, "fake", "p", before)
        elapsed = time.time() - t0
        check(elapsed < mod.WRITE_TIMEOUT,
              f"returns on output, not on the timeout ({elapsed:.1f}s < {mod.WRITE_TIMEOUT}s)")
        check(code == 0, f"treats a hang-after-write as success (code={code})")
        check(mod.snapshot_counts()[1] - before[1] == 1, "episode increase detected")
        check("ep02" in out, "captured the writer's output before killing it")
        write_work(1)  # reset for the next case

        print("\n--- case B: exits at once, writes nothing ---")
        cli = fake_cli(tmp, "print('nothing to do', flush=True)\n")
        t0 = time.time()
        code, out, throttled = mod._run_writer_model(cli, "fake", "p", before)
        check(code != 0, f"reports failure (code={code})")
        check(mod.snapshot_counts()[1] == before[1], "no phantom episodes")
        check(not throttled, "not misreported as throttling")

        print("\n--- case C: hangs, writes nothing (throttling / stuck model) ---")
        cli = fake_cli(tmp, "import time\nwhile True: time.sleep(1)\n")
        t0 = time.time()
        code, out, throttled = mod._run_writer_model(cli, "fake", "p", before)
        elapsed = time.time() - t0
        check(elapsed >= mod.WRITE_TIMEOUT - 2,
              f"waited for the timeout ({elapsed:.1f}s >= {mod.WRITE_TIMEOUT - 2}s)")
        check(code == 124, f"returns the timeout code (code={code})")
        check(elapsed < mod.WRITE_TIMEOUT + 8,
              f"does not overrun the budget ({elapsed:.1f}s)")

        print()
        if failures:
            print(f"FAILED {len(failures)} check(s):")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("RESULT: all checks passed")
        return 0
    finally:
        mod.SOURCE = original_source
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
