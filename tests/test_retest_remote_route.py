from __future__ import annotations

import json
from pathlib import Path

from tools.retest_remote_route import run


def test_remote_retest_fails_closed_without_text_key(tmp_path: Path, monkeypatch):
    state = tmp_path / "watchdog.json"
    state.write_text(json.dumps({"providers": {}, "last_updated": 0}), encoding="utf-8")
    monkeypatch.delenv("SHENWEN_API_KEY", raising=False)
    result = run(state_path=state)
    assert result["status"] == "BLOCKED_MISSING_SHENWEN_API_KEY"
    assert result["attempted"] is False
    assert result["secret_recorded"] is False

