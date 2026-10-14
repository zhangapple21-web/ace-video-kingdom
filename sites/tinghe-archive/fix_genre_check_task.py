#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write the genre-check wrapper correctly, and prove it before trusting it.

tinghe-genre-check was the only task registered as LOCAL SYSTEM, so `py -3`
could not find Python — it lives under the Administrator profile — and the task
had been exiting 112 since 2026-10-13 15:10. The genre trend monitor was dead
for a day and nothing reads LastTaskResult, so nobody saw it.

Giving it the same wscript wrapper as the other seven fixed the Python problem
and introduced a worse one, in this order:

  1. First run: log said "'genre_check.py' is not recognized" and the rc file
     came out 0 bytes.
  2. Re-running it a few minutes later produced a complete 1417-byte report.
  3. Running it again produced the same 73-byte failure.

An intermittent failure is the worst kind to hand to somebody, because every
hand test passes. The difference from the working wrappers turned out to be one
byte: this file had LF line endings, all six siblings have CRLF. cmd.exe reads
batch files by byte offset and tracks position per line, so LF-only endings
desynchronise it — `cd /d` landed in the archive directory on some runs and not
others, and the script then ran py from the wrong working directory.

Both encodings are now checked before the task is wired to the file, because a
wrapper that is one path byte off returns 1 forever and reads as a broken script
rather than a broken file.

  gbk   cmd.exe parses batch in the console codepage; UTF-8 would make the path
        mojibake. 视 is 0xCAB4 in the sibling wrappers, not 0xE8A786.
  crlf  as above.

Registration itself is left to register_genre_check.ps1. Handing task XML to
schtasks /Create from Python failed twice — the declaration said UTF-16 while the
bytes were UTF-8, and schtasks /Query /XML emits UTF-16LE with no BOM, which does
not survive subprocess — both times reported as "unexpected namespace". The
PowerShell ScheduledTasks module reads and writes that export natively.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

WRAP = pathlib.Path(r"C:\tmp\tinghe-wrappers\tinghe-genre-check.cmd")
ARCHIVE = pathlib.Path(r"D:\视频创作\ace-video-kingdom\sites\tinghe-archive")
REGISTER_PS1 = ARCHIVE / "register_genre_check.ps1"
RUNNER = r"C:\tmp\run-hidden-wait.vbs"

BODY = (
    "@echo off\r\n"
    f'cd /d "{ARCHIVE}"\r\n'
    "if errorlevel 1 exit /b 1\r\n"
    f'py -3 -u genre_check.py > "{ARCHIVE}\\genre_check.log" 2>&1\r\n'
    f'echo %ERRORLEVEL% > "{ARCHIVE}\\genre_check.rc"\r\n'
    "exit /b %ERRORLEVEL%\r\n"
)

SIBLINGS = ("tinghe-stale-watch.cmd", "tinghe-daily-origin.cmd",
            "tinghe-night-repair.cmd", "tinghe-sync-1100.cmd")


def verify(path: pathlib.Path) -> list[str]:
    """Everything that must hold for a wrapper to be trustworthy."""
    problems: list[str] = []
    raw = path.read_bytes()
    crlf = raw.count(b"\r\n")
    lone_lf = raw.count(b"\n") - crlf
    if lone_lf:
        problems.append(f"{lone_lf} LF-only line ending(s) — cmd.exe will mis-seek "
                        f"and the failure will be intermittent")
    if raw[:3] == b"\xef\xbb\xbf":
        problems.append("UTF-8 BOM present")
    try:
        text = raw.decode("gbk")
    except UnicodeDecodeError as exc:
        problems.append(f"not valid gbk: {exc}")
        return problems
    if str(ARCHIVE) not in text:
        problems.append("does not decode back to the archive path under gbk")
    print(f"  {path.name}: {crlf} CRLF, {lone_lf} lone LF, {len(raw)} bytes")
    return problems


def main() -> int:
    WRAP.parent.mkdir(parents=True, exist_ok=True)
    WRAP.write_bytes(BODY.encode("gbk"))
    print(f"wrote {WRAP}")

    print("checking every wrapper in the directory, not just the new one:")
    bad = []
    for name in SIBLINGS:
        sib = WRAP.parent / name
        if not sib.is_file():
            print(f"  {name}: ABSENT")
            continue
        issues = verify(sib)
        bad += [f"{name}: {p}" for p in issues]
    bad += [f"tinghe-genre-check.cmd: {p}" for p in verify(WRAP)]

    if bad:
        print("\nFAILED:")
        for b in bad:
            print("  " + b)
        return 1
    print("\nall wrappers: gbk, CRLF, no BOM")

    if not (ARCHIVE / "genre_check.py").is_file():
        print("FATAL: genre_check.py is not where the wrapper says")
        return 1

    if not REGISTER_PS1.is_file():
        print(f"FATAL: {REGISTER_PS1.name} is missing")
        return 1
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(REGISTER_PS1)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=1500)
    print(proc.stdout)
    if proc.stderr.strip():
        print(proc.stderr)
    if proc.returncode != 0:
        return proc.returncode

    # An intermittent failure passes every single hand test. This one produced a
    # complete report on one run and a 73-byte "not recognized" log on the next,
    # so a single green run proves nothing. Run it repeatedly through the real
    # runner and require every attempt to produce a full report AND a non-empty
    # exit code.
    print("running it three times through wscript, as the scheduler will:")
    log = ARCHIVE / "genre_check.log"
    rc = ARCHIVE / "genre_check.rc"
    runs = []
    for attempt in range(1, 4):
        for p in (log, rc):
            p.unlink(missing_ok=True)
        subprocess.run(
            ["C:\\Windows\\System32\\wscript.exe", "//B", "//nologo", RUNNER, str(WRAP)],
            capture_output=True, timeout=1200)
        size = log.stat().st_size if log.is_file() else 0
        code = rc.read_text(encoding="gbk", errors="replace").strip() if rc.is_file() else ""
        complete = size > 500 and "drift check" in (log.read_bytes().decode("gbk", errors="replace")[:400]
                                                    if log.is_file() else "")
        runs.append(complete and bool(code))
        print(f"  run {attempt}: log={size} bytes  rc={code!r}  complete={complete}")

    if not all(runs):
        print("\nFAILED: the wrapper is still intermittent — do not trust it")
        return 1
    print("\n3/3 runs produced a full report and an exit code")
    return 0


if __name__ == "__main__":
    sys.exit(main())