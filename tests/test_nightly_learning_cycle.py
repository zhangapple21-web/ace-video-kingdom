import json

from tools import nightly_learning_cycle as cycle


def test_nightly_cycle_has_one_ordered_entry(monkeypatch, tmp_path):
    calls = []
    run_path = tmp_path / "EL-test.json"

    def fake_collect():
        calls.append("collect")
        return {"run_id": "EL-test"}

    def fake_persist(result):
        calls.append("persist")
        run_path.write_text("{}", encoding="utf-8")
        return run_path

    def fake_publish(path):
        calls.append(("publish", path.name))
        return {"added": 1, "production_integration": False}

    class Completed:
        returncode = 0
        stdout = '{"selected": 0}'
        stderr = ""

    def fake_run(*args, **kwargs):
        calls.append("drain")
        return Completed()

    def fake_promotion(**kwargs):
        calls.append("promotion")
        return {
            "run_id": "PG-test",
            "selected": 0,
            "remaining_ready": 0,
            "decisions": [],
            "receipt": str(tmp_path / "PG-test.json"),
        }

    monkeypatch.setattr(cycle, "collect", fake_collect)
    monkeypatch.setattr(cycle, "persist", fake_persist)
    monkeypatch.setattr(cycle, "publish", fake_publish)
    monkeypatch.setattr(cycle.subprocess, "run", fake_run)
    monkeypatch.setattr(cycle, "run_promotion_gate", fake_promotion)
    result = cycle.run(limit=3)
    assert calls == ["collect", "persist", ("publish", "EL-test.json"), "drain", "promotion"]
    assert result["production_integration"] is False
    assert result["provider_calls"] == 0
    assert result["promotion_gate"]["selected"] == 0
