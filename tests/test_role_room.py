from __future__ import annotations

import importlib.util
import json
import urllib.error
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "role_room.py"
SPEC = importlib.util.spec_from_file_location("role_room", MODULE_PATH)
assert SPEC and SPEC.loader
ROLE_ROOM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROLE_ROOM)


def test_role_room_records_fallback_and_degraded_state(tmp_path, monkeypatch):
    calls: list[str] = []

    def fake_call(_base_url, _api_key, model, _prompt):
        calls.append(model)
        if len(calls) == 1:
            raise urllib.error.URLError("primary unavailable")
        return "fallback candidate", model

    monkeypatch.setattr(ROLE_ROOM, "_call", fake_call)
    monkeypatch.setenv("ONEAPI_API_KEY", "test")
    out = tmp_path / "receipt.json"
    assert ROLE_ROOM.main(["--idea", "test", "--out", str(out), "--execute", "--profile", "rapid"]) == 0
    receipt = json.loads(out.read_text(encoding="utf-8"))
    first = receipt["roles"][0]
    assert first["fallback_used"] is True
    assert first["degraded"] is True
    assert [a["status"] for a in first["attempts"][:2]] == ["FAILED", "PASS"]


def test_role_room_dry_run_does_not_call_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(ROLE_ROOM, "_call", lambda *_args: (_ for _ in ()).throw(AssertionError("called")))
    out = tmp_path / "receipt.json"
    assert ROLE_ROOM.main(["--idea", "test", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "DRY_RUN"


def test_role_room_records_gateway_model_rewrite(tmp_path, monkeypatch):
    monkeypatch.setattr(ROLE_ROOM, "_call", lambda *_args: ("candidate", "grok-4.6"))
    monkeypatch.setenv("ONEAPI_API_KEY", "test")
    out = tmp_path / "receipt.json"
    assert ROLE_ROOM.main(["--idea", "test", "--out", str(out), "--execute", "--profile", "rapid"]) == 0
    first = json.loads(out.read_text(encoding="utf-8"))["roles"][0]
    assert first["requested_model"] == "glm-4-flash"
    assert first["model"] == "grok-4.6"
    assert "grok-4.6" not in first["declared_models"]
    assert first["route_rewritten"] is True
    assert first["degraded"] is True
