import base64
import json
from pathlib import Path

from tools.import_workbench_package import import_package
from tools.medium_lock import INTAKE_PLACEHOLDER, validate_medium_lock


PNG_1X1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def test_dramai_backup_becomes_hash_bound_intake(tmp_path: Path):
    source = tmp_path / "dramai.json"
    source.write_text(json.dumps({
        "format": "dramai-backup", "version": 1,
        "projects": [{"id": "p1", "title": "测试项目"}],
        "characters": [{"id": "c1", "name": "阿浪", "locked": True, "referenceAssetId": "a1"}],
        "storyboards": [{"id": "sb1", "sequence": 1, "sceneText": "他按下回车", "narration": "开始。", "imageAssetId": "a1"}],
        "assets": [{"id": "a1", "kind": "image", "mimeType": "image/png", "blobBase64": PNG_1X1}],
        "generations": [],
    }, ensure_ascii=False), encoding="utf-8")
    result = import_package(source, tmp_path / "out")
    assert result["source_kind"] == "dramai"
    assert result["source_sha256"]
    assert result["production_integration"] is False
    assert (tmp_path / "out" / "episode_plan.json").is_file()
    contract = json.loads((tmp_path / "out" / "six_module_contract.json").read_text(encoding="utf-8"))
    assert contract["production_boundary"] == "RESEARCH_ONLY"
    assert contract["shots"][0]["script"]["audio_status"] == "AUDIO_PENDING"
    assert "S01A:locked_dialogue" not in result["missing_requirements"]


def test_chat_ui_workbench_prompt_is_washed_and_unsigned(tmp_path: Path):
    source = tmp_path / "fastmovie.json"
    source.write_text(json.dumps({
        "project": {"id": "fm_chat", "name": "接粉风云"},
        "actors": [{"id": "actor1", "name": "张铁铁"}],
        "shots": [{
            "id": "SHOT_01",
            "scene_id": "scene1",
            "description": "文姬发来第一条消息",
            "dialogue": "铁铁，你最近在干嘛",
            "duration": 5000,
            "video_prompt": "竖屏9:16，手机聊天界面，微信气泡弹出新消息",
            "image_url": "https://example.invalid/anchor.png",
        }],
    }, ensure_ascii=False), encoding="utf-8")
    result = import_package(source, tmp_path / "out", "fastmovieai")
    plan = json.loads((tmp_path / "out" / "episode_plan.json").read_text(encoding="utf-8"))
    shot = plan["shots"][0]
    assert plan["medium_lock"]["signed"] is False
    assert plan["medium_lock"]["output_medium"] == "UNSIGNED"
    assert shot["prompt"] == INTAKE_PLACEHOLDER
    assert "手机聊天界面" in shot["intake_prompt"]
    assert shot["ui_language_in_intake"] is True
    errors = validate_medium_lock(plan)
    assert any("unsigned" in item for item in errors)
    assert result["production_integration"] is False


def test_fastmovieai_import_preserves_pending_gates(tmp_path: Path):
    source = tmp_path / "fastmovie.json"
    source.write_text(json.dumps({
        "project": {"id": "fm1", "name": "Fast"},
        "actors": [{"id": "actor1", "name": "主角"}],
        "shots": [{"id": "shot1", "scene_id": "scene1", "description": "打开门", "dialogue": "我回来了", "duration": 6000, "image_url": "https://example.invalid/anchor.png"}],
    }, ensure_ascii=False), encoding="utf-8")
    result = import_package(source, tmp_path / "out", "fastmovieai")
    assert result["source_kind"] == "fastmovieai"
    assert result["status"] == "INTAKE_READY_FOR_REVIEW"
    plan = json.loads((tmp_path / "out" / "episode_plan.json").read_text(encoding="utf-8"))
    assert plan["production_integration"] is False
    assert plan["shots"][0]["render"]["image"] == "https://example.invalid/anchor.png"
    contract = json.loads((tmp_path / "out" / "six_module_contract.json").read_text(encoding="utf-8"))
    assert contract["shots"][0]["edit"]["duration_source"] == "IMPORTED_ESTIMATE"
    assert contract["shots"][0]["script"]["audio_status"] == "AUDIO_PENDING"
