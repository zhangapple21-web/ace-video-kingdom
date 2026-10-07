"""Regression test for the vklogging VK_LOG_PATH file sink (P1).

tools/vklogging.py referenced Path without importing it, so the
optional file sink raised NameError on every vklog() call and the
bare ``except Exception: pass`` silently dropped all file log
writes whenever VK_LOG_PATH was set.
"""
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_vklog_appends_jsonl_to_vk_log_path(tmp_path, monkeypatch):
    log_file = tmp_path / "logs" / "vk.jsonl"
    monkeypatch.setenv("VK_LOG_PATH", str(log_file))
    import tools.vklogging as vk
    importlib.reload(vk)
    try:
        vk.vklog("INFO", "test message", shot_id="S01A")
        assert log_file.is_file(), "vklog did not write to VK_LOG_PATH"
        record = json.loads(log_file.read_text(encoding="utf-8").splitlines()[0])
        assert record["level"] == "INFO"
        assert record["msg"] == "test message"
        assert record["shot_id"] == "S01A"
        # the sink must append, not overwrite
        vk.vklog("ERROR", "second message")
        lines = log_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[1])["level"] == "ERROR"
    finally:
        monkeypatch.undo()
        importlib.reload(vk)
