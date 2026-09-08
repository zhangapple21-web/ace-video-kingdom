import json
from pathlib import Path

from tools.preflight_episode import _scene_switch_audit, _validate_six_module_contract
from tools.run_idea_pipeline import _compile


def test_compiled_plan_keeps_tts_pending_until_measured(tmp_path: Path):
    _compile("程序员发现代码里的求救信息", tmp_path, "pending", target_seconds=30)
    contract = json.loads((tmp_path / "six_module_contract.json").read_text(encoding="utf-8"))
    assert contract["contract_version"].endswith(".v2")
    assert all(shot["script"]["audio_status"] == "AUDIO_PENDING" for shot in contract["shots"])
    assert all(shot["script"]["tts_duration_seconds"] is None for shot in contract["shots"])
    assert all(shot["edit"]["duration_seconds"] is None for shot in contract["shots"])
    assert all(shot["shot_contract"]["single_action"] is True for shot in contract["shots"])


def test_measured_tts_drives_render_seconds_and_contract(tmp_path: Path):
    measurements = {f"S{i:02d}A": {"duration_seconds": 4.2 + i / 10} for i in range(1, 7)}
    plan = _compile("程序员发现代码里的求救信息", tmp_path, "measured", target_seconds=30, tts_measurements=measurements)
    contract = json.loads((tmp_path / "six_module_contract.json").read_text(encoding="utf-8"))
    for shot in contract["shots"]:
        assert shot["script"]["audio_status"] == "MEASURED"
        assert shot["edit"]["duration_seconds"] >= shot["script"]["tts_duration_seconds"]
        assert shot["edit"]["render_seconds"] >= shot["edit"]["duration_seconds"]
        assert shot["shot_contract"]["max_primary_actions"] == 1
    assert plan["shots"][0]["render"]["seconds"] >= 4


def test_single_action_contract_rejects_compound_action(tmp_path: Path):
    _compile("程序员发现代码里的求救信息", tmp_path, "compound", target_seconds=30)
    path = tmp_path / "six_module_contract.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["shots"][0]["shot_contract"]["action_unit"] = "主角拔掉网线并后退半步"
    path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
    report = _validate_six_module_contract(path, contract)
    assert report["status"] == "INVALID"
    assert any("multiple primary actions" in item for item in report["errors"])


def test_dialogue_line_over_35_characters_is_rejected(tmp_path: Path):
    _compile("程序员发现代码里的求救信息", tmp_path, "dialogue-length", target_seconds=30)
    path = tmp_path / "six_module_contract.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["shots"][0]["script"]["dialogue_text"] = "x" * 36
    path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
    report = _validate_six_module_contract(path, contract)
    assert report["status"] == "INVALID"
    assert any("exceeds 35 characters" in item for item in report["errors"])


def test_dense_scene_switches_require_review():
    shots = [
        {"scene_id": f"SC{i}", "edit": {"duration_seconds": 5}}
        for i in range(6)
    ]
    report = _scene_switch_audit(shots)
    assert report["status"] == "REVIEW_REQUIRED"
    assert report["max_transitions_per_60s"] == 5
