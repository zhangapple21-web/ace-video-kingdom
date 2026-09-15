from __future__ import annotations

import json
from pathlib import Path

import tools.role_room as role_room


def test_role_room_resume_skips_completed_roles(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ONEAPI_API_KEY", "test")
    prior = tmp_path / "prior.json"
    prior.write_text(
        json.dumps(
            {
                "schema": "video_kingdom.oneapi_role_room.v2",
                "idea": "test",
                "memory_context": {"sha256": role_room.build_memory_context(None)["sha256"]},
                "roles": [
                    {
                        "role_id": "outline_structurer",
                        "status": "COMPLETED",
                        "model": "glm-4-flash",
                        "output": "已有结构化简报",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    calls: list[str] = []

    def fake_call(_base_url, _api_key, model, _prompt):
        calls.append(model)
        return "新的候选稿", model

    monkeypatch.setattr(role_room, "_call", fake_call)
    out = tmp_path / "resumed.json"
    assert role_room.main(["--idea", "test", "--out", str(out), "--execute", "--profile", "rapid", "--resume-from", str(prior)]) == 0
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["resume_compatible"] is True
    assert receipt["roles"][0]["output"] == "已有结构化简报"
    assert len(calls) == 2

