"""Feature tests for Bug #12: logging infrastructure.

Tests verify that:
1. vklog produces valid JSON output to stderr
2. vklog includes timestamp, level, and message fields
3. vklog accepts additional fields
4. vklog_error includes traceback when exc_info=True
5. vklog_event is a shorthand for INFO-level events
"""
import json
import sys
from pathlib import Path
from io import StringIO

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_vklog_output_is_valid_json():
    """vklog should produce valid JSON on stderr."""
    from tools.vklogging import vklog

    old_stderr = sys.stderr
    sys.stderr = captured = StringIO()
    try:
        vklog("INFO", "test message")
    finally:
        sys.stderr = old_stderr

    output = captured.getvalue().strip()
    record = json.loads(output)
    assert record["msg"] == "test message"
    assert record["level"] == "INFO"
    assert "ts" in record


def test_vklog_accepts_additional_fields():
    """vklog should include extra fields in the output record."""
    from tools.vklogging import vklog

    old_stderr = sys.stderr
    sys.stderr = captured = StringIO()
    try:
        vklog("INFO", "processing", shot_id="S01A", count=42)
    finally:
        sys.stderr = old_stderr

    output = captured.getvalue().strip()
    record = json.loads(output)
    assert record["shot_id"] == "S01A"
    assert record["count"] == 42


def test_vklog_error_includes_traceback():
    """vklog_error should include traceback when exc_info=True."""
    from tools.vklogging import vklog_error

    old_stderr = sys.stderr
    sys.stderr = captured = StringIO()
    try:
        try:
            raise ValueError("test error")
        except ValueError:
            vklog_error("something failed", code=500)
    finally:
        sys.stderr = old_stderr

    output = captured.getvalue().strip()
    record = json.loads(output)
    assert record["level"] == "ERROR"
    assert "traceback" in record
    assert "ValueError: test error" in record["traceback"]


def test_vklog_event_is_info_level():
    """vklog_event should log at INFO level."""
    from tools.vklogging import vklog_event

    old_stderr = sys.stderr
    sys.stderr = captured = StringIO()
    try:
        vklog_event("SHOT_COMPLETE", shot_id="S01A")
    finally:
        sys.stderr = old_stderr

    output = captured.getvalue().strip()
    record = json.loads(output)
    assert record["level"] == "INFO"
    assert record["msg"] == "SHOT_COMPLETE"
    assert record["shot_id"] == "S01A"


def test_vklog_unicode_preserved():
    """vklog should preserve Unicode characters in output."""
    from tools.vklogging import vklog

    old_stderr = sys.stderr
    sys.stderr = captured = StringIO()
    try:
        vklog("INFO", "处理完成", name="张铁铁")
    finally:
        sys.stderr = old_stderr

    output = captured.getvalue().strip()
    record = json.loads(output)
    assert record["msg"] == "处理完成"
    assert record["name"] == "张铁铁"


def test_vklog_module_importable():
    """vklogging module should be importable."""
    import importlib
    mod = importlib.import_module("tools.vklogging")
    assert hasattr(mod, "vklog")
    assert hasattr(mod, "vklog_event")
    assert hasattr(mod, "vklog_error")
    assert hasattr(mod, "logger")
