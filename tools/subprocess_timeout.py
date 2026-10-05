"""Subprocess helper with default timeout — prevents indefinite hangs (Bug #11).

Bug #11 root cause: 79 subprocess.run calls had no timeout=, causing
indefinite hangs if a subprocess stalls.

Usage:
    from tools.subprocess_timeout import run_with_timeout
    result = run_with_timeout(["ffmpeg", "-i", "input.mp4"], timeout=300)
    if isinstance(result, subprocess.TimeoutExpired):
        handle_timeout(result)
"""
from __future__ import annotations

import subprocess
from typing import Any

DEFAULT_TIMEOUT = int(__import__("os").environ.get("VK_SUBPROCESS_TIMEOUT", "600"))


def run_with_timeout(
    cmd: list[str],
    *,
    timeout: int | float | None = None,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = True,
    text: bool = True,
    **kwargs: Any,
) -> subprocess.CompletedProcess | subprocess.TimeoutExpired:
    """Run subprocess.run with a mandatory timeout.

    If timeout is not specified, uses DEFAULT_TIMEOUT (600s) or the
    VK_SUBPROCESS_TIMEOUT env var. Returns TimeoutExpired on timeout
    instead of raising.
    """
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    try:
        return subprocess.run(
            cmd,
            timeout=timeout,
            cwd=cwd,
            env=env,
            capture_output=capture_output,
            text=text,
            **kwargs,
        )
    except subprocess.TimeoutExpired as e:
        return e
