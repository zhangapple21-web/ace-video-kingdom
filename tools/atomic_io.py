"""Atomic file write utility — prevents partial writes and parse failures.

Bug #9 root cause: 193 write_text() calls across the codebase perform
non-atomic writes. If the process is killed mid-write, the file is left
truncated or corrupted, causing parse failures downstream.

Usage:
    from tools.atomic_io import atomic_write_text
    atomic_write_text(path, content)  # tempfile + os.fsync + os.replace
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: str | Path, content: str, *, encoding: str = "utf-8") -> None:
    """Write text to a file atomically.

    Writes to a temporary file in the same directory, flushes + fsyncs,
    then renames (replaces) the original. On POSIX this guarantees
    readers never see a partially-written file. On Windows, os.replace
    is atomic within the same filesystem volume.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    """Write bytes to a file atomically (same pattern as atomic_write_text)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_json(path: str | Path, obj, *, indent: int = 2) -> None:
    """Serialize obj to JSON and write atomically with UTF-8 encoding."""
    import json
    content = json.dumps(obj, ensure_ascii=False, indent=indent)
    atomic_write_text(path, content)
