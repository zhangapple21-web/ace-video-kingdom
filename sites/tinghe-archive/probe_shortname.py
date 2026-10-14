#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Is there an 8.3 short name for the CJK directory?

If there is, the wrapper can be written in pure ASCII and the intermittent
`cd /d` failure under a console-less cmd.exe disappears as a class rather than
as a bug to keep chasing. Written as a file because inline quoting through
PowerShell mangles the CJK before Python ever sees it.
"""
from __future__ import annotations

import pathlib
import subprocess

ARCHIVE = pathlib.Path(r"D:\视频创作\ace-video-kingdom\sites\tinghe-archive")

# A .cmd written in GBK, so cmd.exe itself parses the CJK the way it always has.
probe = pathlib.Path(r"C:\tmp\tinghe-wrappers\_short2.cmd")
probe.write_bytes(
    ("@echo off\r\n"
     "for %%I in (\"D:\\视频创作\") do @echo SHORT=%%~sI\r\n"
     "for %%I in (\"D:\\视频创作\\ace-video-kingdom\\sites\\tinghe-archive\") do @echo ARCHIVE_SHORT=%%~sI\r\n"
     "exit /b 0\r\n").encode("gbk"))

r = subprocess.run(["cmd.exe", "/c", str(probe)], capture_output=True, timeout=120)
print(r.stdout.decode("gbk", errors="replace").strip())
print("exit", r.returncode)

r2 = subprocess.run(["cmd.exe", "/c", "dir", "/x", "D:\\"], capture_output=True,
                    timeout=120)
for line in r2.stdout.decode("gbk", errors="replace").splitlines():
    if "  " in line and ("<" in line or "视频" in line):
        print("dir:", line.rstrip())