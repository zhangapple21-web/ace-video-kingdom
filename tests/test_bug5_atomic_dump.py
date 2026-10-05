"""Tests for Bug #5 fix: atomic _dump prevents receipt corruption.

Verifies that _dump writes atomically (tempfile + os.replace) and that
the watchdog encoding fix (line 112: -Encoding UTF8) is present.
"""
from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parents[1]


def test_world_live_evolve_dump_is_atomic():
    """_dump uses tempfile + os.replace, not direct write_text."""
    import importlib
    mod = importlib.import_module("tools.world_live_evolve")
    import inspect
    source = inspect.getsource(mod._dump)
    assert "mkstemp" in source or "tempfile" in source
    assert "os.replace" in source or "_os.replace" in source


def test_world_live_evolve_dump_round_trip(tmp_path):
    """_dump writes valid JSON that can be read back."""
    import importlib
    mod = importlib.import_module("tools.world_live_evolve")

    obj = {"schema": "test", "data": "活着的世界 🌊", "count": 3}
    path = tmp_path / "test.json"
    mod._dump(path, obj)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == obj


def test_world_live_evolve_dump_no_leftover_temp(tmp_path):
    """_dump must not leave temp files after successful write."""
    import importlib
    mod = importlib.import_module("tools.world_live_evolve")

    path = tmp_path / "test.json"
    mod._dump(path, {"ok": True})
    temps = list(tmp_path.glob("*.tmp"))
    temps += list(tmp_path.glob(".test.json.*"))
    assert len(temps) == 0


def test_watchdog_receipt_parse_uses_utf8_encoding():
    """watchdog.ps1 line 112 must use -Encoding UTF8 for receipt parse."""
    ps1 = (ROOT / "tools/world_live_watchdog.ps1").read_text(encoding="utf-8")
    lines = ps1.split('\n')
    # Find the Get-Content line that reads the receipt
    for i, line in enumerate(lines, 1):
        if 'receiptPath' in line and 'ConvertFrom-Json' in lines[i-1] if i > 0 else False:
            pass
    # More robust: find the line with Get-Content and ConvertFrom-Json
    found = False
    for line in lines:
        if 'Get-Content' in line and 'ConvertFrom-Json' in line:
            assert '-Encoding UTF8' in line or '-Encoding utf8' in line, \
                "Receipt parse line must specify -Encoding UTF8: %s" % line
            found = True
            break
    assert found, "No Get-Content + ConvertFrom-Json line found in watchdog"


def test_world_live_evolve_dump_handles_chinese(tmp_path):
    """Receipt with Chinese content must be readable with UTF-8 decoding."""
    import importlib
    mod = importlib.import_module("tools.world_live_evolve")

    receipt = {
        "schema": "video_kingdom.world_live_receipt.v1",
        "status": "COMPLETED",
        "layer": "CREATOR_LIVE",
        "note": "活体演化候选。不是锁稿。未进生产。resume-safe。",
        "script_locked": False,
    }
    path = tmp_path / "world_live_receipt.v1.json"
    mod._dump(path, receipt)

    # Verify it parses with UTF-8 (what the fixed watchdog uses)
    raw = path.read_bytes()
    assert not raw.startswith(b'\xef\xbb\xbf')  # no BOM
    text = raw.decode('utf-8')
    obj = json.loads(text)
    assert obj["note"] == "活体演化候选。不是锁稿。未进生产。resume-safe。"
