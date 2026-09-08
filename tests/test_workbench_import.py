import base64
import json
from pathlib import Path

from tools.import_workbench_package import import_package


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
