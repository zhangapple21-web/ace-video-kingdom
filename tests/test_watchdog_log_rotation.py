"""M-01/E2: the watchdog watch log must not grow without bound.

tools/world_live_watchdog.ps1 appends one line per event to
<lib>/world_live_watchdog.log. It reached 2.6 GB because nothing rotated it and
the only remedy was manual deletion, which is precisely why it kept growing.

These tests exercise the real rotation logic by extracting Invoke-LogRotation
from the script and running it against a temp directory, so the shipped code is
what is under test rather than a copy of it.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
WATCHDOG = ROOT / "tools" / "world_live_watchdog.ps1"

pytestmark = pytest.mark.skipif(
    not WATCHDOG.is_file(), reason="tools/world_live_watchdog.ps1 not present"
)


def _extract_rotation() -> str:
    """Pull the rotation function out of the script as a standalone PowerShell unit."""
    text = WATCHDOG.read_text(encoding="utf-8")
    match = re.search(
        r"function Invoke-LogRotation \{.*?\n\}", text, flags=re.DOTALL
    )
    assert match, "Invoke-LogRotation not found in world_live_watchdog.ps1"
    return match.group(0)


def _run_rotation(tmp: Path, max_log_mb: int, keep: int) -> None:
    ps = tmp / "rotate.ps1"
    ps.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        f"$watchLog = '{tmp / 'world_live_watchdog.log'}'\n"
        f"$MaxLogMB = {max_log_mb}\n"
        f"$KeepRotations = {keep}\n"
        + _extract_rotation()
        + "\nInvoke-LogRotation\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def _write_log(tmp: Path, megabytes: int) -> Path:
    log = tmp / "world_live_watchdog.log"
    log.write_bytes(b"x" * (megabytes * 1024 * 1024))
    return log


def test_small_log_is_left_alone(tmp_path):
    """No rotation below the threshold: the live file must survive untouched."""
    log = _write_log(tmp_path, 1)
    before = log.read_bytes()
    _run_rotation(tmp_path, max_log_mb=100, keep=3)
    assert log.is_file()
    assert log.read_bytes() == before
    assert not (tmp_path / "world_live_watchdog.log.1").exists()


def test_oversize_log_is_rotated_and_content_preserved(tmp_path):
    log = _write_log(tmp_path, 2)
    before = log.read_bytes()
    _run_rotation(tmp_path, max_log_mb=1, keep=3)

    rotated = tmp_path / "world_live_watchdog.log.1"
    assert rotated.is_file(), "oversize log was not rotated"
    assert rotated.read_bytes() == before, "rotation lost log content"

    live = tmp_path / "world_live_watchdog.log"
    assert live.is_file(), "a fresh live log must exist after rotation"
    assert live.stat().st_size < before.__len__(), "live log should be small again"
    assert "ROTATED" in live.read_text(encoding="utf-8", errors="replace")


def test_rotation_keeps_only_the_requested_number(tmp_path):
    """Repeated rotations must not accumulate an unbounded pile of .N files."""
    _run_rotation(tmp_path, max_log_mb=0, keep=3)  # no-op first
    for _ in range(6):
        _write_log(tmp_path, 2)
        _run_rotation(tmp_path, max_log_mb=1, keep=3)

    rotations = sorted(p.name for p in tmp_path.glob("world_live_watchdog.log.*"))
    assert len(rotations) <= 3, f"kept too many rotations: {rotations}"


def test_rotation_can_be_disabled(tmp_path):
    """MaxLogMB=0 means no rotation at all, for anyone who wants the raw log."""
    log = _write_log(tmp_path, 5)
    before = log.read_bytes()
    _run_rotation(tmp_path, max_log_mb=0, keep=3)
    assert log.read_bytes() == before
    assert not (tmp_path / "world_live_watchdog.log.1").exists()


def test_rotation_settings_are_wired_into_the_script():
    """Guard against the params existing but never being passed to the function."""
    text = WATCHDOG.read_text(encoding="utf-8")
    assert "[int64]$MaxLogMB = 100" in text
    assert "[int]$KeepRotations = 3" in text
    # Write-WatchLog must invoke rotation, otherwise growth is still unbounded
    assert re.search(r"function Write-WatchLog.*?Invoke-LogRotation", text, re.DOTALL), (
        "Write-WatchLog does not call Invoke-LogRotation; the log can still grow"
    )