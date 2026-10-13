#!/usr/bin/env python3
"""Pin the probe's verdict to the exit code, not to what a model replied.

Three times in two days this probe declared healthy models dead, every time
because it asked the model to answer 可用 and then required that string in the
output:

  - all six models reported DEAD five minutes after one had written five episodes
  - all six reported DEAD again on a later spot check
  - mimo-v2.6-flash-free reported DEAD while three direct calls answered plainly

The replies show why text matching cannot work as a liveness test. Asked to say
可用, muse-spark answered "收到，正在确认当前工作区状态。 可用。" and longcat
answered with a project status summary. Both are successful endpoint calls. A
model that replies with something else, or that gets interrupted mid-step, would
be condemned by the old check while being perfectly available.

So the assertions here are about the probe's logic, run against synthetic
subprocess results, and they fail if anyone reintroduces text matching.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("p", HERE / "probe_pool_health.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


class Result:
    def __init__(self, code: int, out: str = "", err: str = ""):
        self.returncode = code
        self.stdout = out
        self.stderr = err


def fake_runner(results: list):
    """Patch subprocess.run inside the probe to return scripted results."""
    seq = list(results)

    def run(cmd, **kwargs):
        item = seq.pop(0) if seq else Result(0, "可用")
        if isinstance(item, BaseException):
            raise item
        return item

    return run


def with_runner(results: list, fn):
    original = probe.subprocess.run
    probe.subprocess.run = fake_runner(results)
    try:
        return fn()
    finally:
        probe.subprocess.run = original


def main() -> int:
    print("--- a live model that replies with something else is still live ---")
    ok, _, note = with_runner([Result(0, "收到，正在确认当前工作区状态。")],
                              lambda: probe.probe("m"))
    check(ok, "exit 0 counts as available even when 可用 is absent")
    check("收到" in note, f"the reply is reported for reading: {note!r}")

    print("\n--- the exact replies that caused the false alarms ---")
    for reply in ("收到。 当前状态：**停在剧本审核前**。",
                  "工作区 D:\\视频创作 ... 关键入口已就位。"):
        ok, _, _ = with_runner([Result(0, reply)], lambda: probe.probe("m"))
        check(ok, f"a chatty reply does not condemn the model: {reply[:24]}…")

    print("\n--- a genuinely dead model is still caught ---")
    # Two scripted attempts: probe() retries, so a single Result leaves the second
    # attempt falling through to the default success stub.
    dead_call = [Result(1, "", "Model unavailable")] * probe.ATTEMPTS
    ok, _, note = with_runner(dead_call, lambda: probe.probe("m"))
    check(not ok, "exit 1 is unavailable")
    check("unavailable" in note.lower() or "exit 1" in note,
          f"the note carries the reason: {note!r}")

    print("\n--- one interrupted call is noise, two are a verdict ---")
    ok, _, _ = with_runner([Result(1, "", "Step interrupted"), Result(0, "可用")],
                           lambda: probe.probe("m"))
    check(ok, "a retry recovers a single interrupted call")
    ok, _, _ = with_runner([Result(1, "", "Step interrupted")] * probe.ATTEMPTS,
                           lambda: probe.probe("m"))
    check(not ok, "two failures in a row are reported as unavailable")

    print("\n--- a timeout is not availability ---")
    ok, _, note = with_runner([probe.subprocess.TimeoutExpired("t", "")] * probe.ATTEMPTS,
                              lambda: probe.probe("m"))
    check(not ok, "a timeout is unavailable")
    check("timeout" in note, "the note says timeout")

    print()
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: availability is read from the exit code, never from the reply")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
