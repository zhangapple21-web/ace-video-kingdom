#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the working sibling wrapper and the new one through the identical path.

The new wrapper is the same shape as tinghe-stale-watch.cmd, which runs fine, and
it still could not find genre_check.py. Two variables are in play — the runner
and the file — so the only way to separate them is to run both and compare.

The first version of this probe redirected nothing and printed "NO OUTPUT FILE",
which said nothing about either hypothesis.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

HERE = pathlib.Path(r"C:\tmp\tinghe-wrappers")
ARCHIVE = pathlib.Path(r"D:\视频创作\ace-video-kingdom\sites\tinghe-archive")
RUNNER = r"C:\tmp\run-hidden-wait.vbs"

# The control is the real, working wrapper, run through the real runner. Nothing
# about it is rebuilt here — if this fails too, the runner is the problem and the
# new wrapper is innocent.
CASES = [
    ("control_stale_watch", HERE / "tinghe-stale-watch.cmd"),
    ("new_genre_check", HERE / "tinghe-genre-check.cmd"),
]

# A probe that reports what cmd.exe actually sees, in ASCII only so it cannot be
# accused of the encoding fault it is meant to diagnose.
PROBE_BODY = f"""@echo off
echo --- case start ---
cd /d "{ARCHIVE}"
echo CWD=[%CD%]
echo ERRORLEVEL_AFTER_CD=%ERRORLEVEL%
if exist genre_check.py (echo SEES_genre_check) else (echo NOT_SEEING_genre_check)
py -3 -u genre_check.py > "{HERE}\\"_probe_genre.out" 2>&1
echo PY_EXIT=%ERRORLEVEL%
echo --- case end ---
exit /b 0
"""


def run_through_runner(label: str, target: pathlib.Path, out: pathlib.Path) -> None:
    print(f"===== {label}: {target.name} =====")
    proc = subprocess.run(
        ["C:\\Windows\\System32\\wscript.exe", "//B", "//nologo", RUNNER, str(target)],
        capture_output=True, timeout=900)
    print(f"  wscript exit={proc.returncode}")
    if out.is_file():
        data = out.read_bytes().decode("gbk", errors="replace")
        out.unlink()
        print("  --- wrapper said ---")
        for line in data.splitlines():
            print("  " + line)
    else:
        print(f"  NO OUTPUT at {out}")
    print()


probe = HERE / "_probe_cwd.cmd"
probe.write_bytes(PROBE_BODY.encode("gbk"))
print(f"probe: {probe.stat().st_size} bytes gbk")
print(f"archive really contains genre_check.py: {(ARCHIVE / 'genre_check.py').is_file()}")
print()

for label, target in CASES:
    out = HERE / f"_{label}.out"
    if out.is_file():
        out.unlink()
    run_through_runner(label, target, out)

# The ASCII probe isolates the question the two wrappers could not answer: does
# cmd.exe under this runner land in the archive directory at all.
run_through_runner("ascii_probe", probe, HERE / "_probe_out.out")