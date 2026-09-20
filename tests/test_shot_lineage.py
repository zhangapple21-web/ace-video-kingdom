import hashlib
import json
from pathlib import Path

from tools.build_shot_lineage import build_lineage
from tools.validate_shot_lineage import validate_lineage


def _ref(path: Path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"path": str(path), "sha256": digest, "status": "PRESENT"}


def _document(tmp_path: Path):
    refs = {}
    for name in ("script", "script_structure", "storyboard", "prompt_contract", "asset_manifest", "audio_timeline", "review_record", "generation_receipt"):
        path = tmp_path / f"{name}.json"
        path.write_text(name, encoding="utf-8")
        refs[name] = _ref(path)
    video = tmp_path / "shot.mp4"
    video.write_bytes(b"video")
    audio = tmp_path / "line.wav"
    audio.write_bytes(b"audio")
    assembly = tmp_path / "episode.mp4"
    assembly.write_bytes(b"assembly")
    line = {
        "line_id": "S01_LINE_01", "text": "明天准备接粉。", "track_type": "DIALOGUE",
        "shot_id": "SHOT_01", "character_id": "CHAR_ZHANG", "speaker": "老张",
        "voice_id": "VOICE_MALE_V1", "audio_track_id": "S01_LINE_01",
        "audio": {"path": str(audio), "sha256": hashlib.sha256(audio.read_bytes()).hexdigest(), "duration_seconds": 1.2, "reference_audio_urls": ["https://cdn.example.test/a.wav"]},
        "generation_receipt_id": "VID_01", "video_artifact_path": str(video), "video_artifact_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        "review_receipt_ids": ["review_record.json"], "review_status": "PASS", "take_id": "SHOT_01_T01", "selected": True, "delivery_version_id": "EP01_V1",
    }
    return {"schema": "ace.video_kingdom.shot_lineage.v1", **refs, "lines": [line], "delivery": {"status": "APPROVED_MASTER", "version_id": "EP01_V1", "assembly_path": str(assembly), "assembly_sha256": hashlib.sha256(assembly.read_bytes()).hexdigest(), "selected_take_ids": ["SHOT_01_T01"]}}


def test_lineage_passes_when_every_line_is_traceable(tmp_path):
    result = validate_lineage(_document(tmp_path), base_dir=tmp_path, production=True)
    assert result["status"] == "PASS", result


def test_lineage_blocks_unselected_or_unreviewed_line(tmp_path):
    document = _document(tmp_path)
    document["lines"][0]["selected"] = False
    document["lines"][0]["review_status"] = "UNVERIFIED"
    result = validate_lineage(document, base_dir=tmp_path, production=True)
    assert result["status"] == "BLOCKED"
    assert any("not selected" in item or "review_status" in item for item in result["errors"])


def test_builder_keeps_missing_refs_explicitly_blocked(tmp_path):
    episode = {
        "project_id": "EP01", "title": "测试", "screenplay_source": {"path": "剧本.md"},
        "shots": [{"shot_id": "SHOT_01", "audio_contract": {"dialogue_tracks": [{"track_id": "L1", "text": "你好", "speaker": "甲", "voice_id": "V1", "duration_seconds": 1.0, "local_path": "missing.wav"}]}}],
    }
    episode_path = tmp_path / "episode.json"
    manifest_path = tmp_path / "manifest.json"
    episode_path.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    manifest_path.write_text(json.dumps([{ "shot_id": "SHOT_01", "status": "FAILED" }]), encoding="utf-8")
    document = build_lineage(episode_path, manifest_path)
    result = validate_lineage(document, base_dir=tmp_path, production=True)
    assert result["status"] == "BLOCKED"
    assert document["generation_receipt"]["status"] == "PRESENT"
