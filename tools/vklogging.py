"""Minimal structured logging — replaces print()-based observability (Bug #12).

Bug #12 root cause: 0 logging imports, 0 logging.* calls across all tools.
This module provides a lightweight logger that writes structured JSON
to both stderr and an optional .jsonl log file.

Usage:
    from tools.vklogging import vklog
    vklog("PROCESSING", "shot_id=S01A", count=42)
    vklog("ERROR", "failed to render", exc_info=True)
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any

sys.stderr.reconfigure(encoding="utf-8")  # Bug #1 fix: prevent UnicodeEncodeError on GBK console
sys.stdout.reconfigure(encoding="utf-8")


_DEFAULT_LOG_PATH = os.environ.get("VK_LOG_PATH")


def vklog(level: str, msg: str, *, exc_info: bool = False, **fields: Any) -> None:
    """Log a structured JSON record to stderr and optionally a file.

    Args:
        level: Log level string (INFO, WARNING, ERROR, etc.)
        msg: Human-readable message.
        exc_info: If True, capture and include traceback.
        **fields: Additional key-value pairs to include in the record.
    """
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "level": level,
        "msg": msg,
    }
    record.update(fields)
    if exc_info:
        record["traceback"] = traceback.format_exc()

    line = json.dumps(record, ensure_ascii=False)
    print(line, file=sys.stderr, flush=True)

    if _DEFAULT_LOG_PATH:
        try:
            from tools.atomic_io import atomic_write_text
            log_path = Path(_DEFAULT_LOG_PATH)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


def vklog_event(event: str, **fields: Any) -> None:
    """Log an event (INFO level) — shorthand for vklog('INFO', event, ...)."""
    vklog("INFO", event, **fields)


def vklog_error(msg: str, **fields: Any) -> None:
    """Log an error (ERROR level) with optional traceback."""
    vklog("ERROR", msg, exc_info=True, **fields)


# Convenience for module-level access
logger = vklog
