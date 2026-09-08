import json
from pathlib import Path

from tools.build_experience_profile import build


def test_profile_is_evidence_only_and_deterministic(tmp_path: Path):
    (tmp_path / "experiments").mkdir()
    (tmp_path / "experiments" / "demo_tasks.json").write_text(json.dumps([
        {"shot_id": "S1", "model_id": "agnes-video-2.5-flash", "status": "COMPLETED"},
        {"shot_id": "S2", "model_id": "agnes-video-2.5-flash", "status": "FAILED", "error": "face drift"},
    ]), encoding="utf-8")
    result = build(tmp_path)
    assert result["production_integration"] is False
    assert result["promotion"] == "NONE_AUTOMATIC"
    assert result["model_summary"]["agnes-video-2.5-flash"]["completed"] == 1
    assert result["failure_attribution"]["generation_or_provider"] == 1
