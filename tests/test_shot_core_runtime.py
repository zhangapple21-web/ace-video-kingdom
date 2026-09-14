from pathlib import Path
import hashlib
import pytest

from runtime.shot_core import (
    build_payload,
    canonical_hash,
    generation_fingerprint,
    load_manifest,
    preflight_shot,
    propagate_stale,
    record_decision,
    save_manifest,
)


def shot_fixture() -> dict:
    return {
        "shot_id": "PILOT_S01",
        "episode_id": "PILOT",
        "medium_lock": {
            "schema": "video_kingdom.medium_lock.v1",
            "signed": True,
            "signed_by": "test",
            "output_medium": "CHARACTER_PERFORMANCE",
            "source_kind": "ORIGINAL_STORY",
            "rule": "story_material_is_not_finished_video_medium",
        },
        "scene_id": "ROOM",
        "shot_type": "DIALOGUE",
        "prompt": "A quiet office conversation",
        "provider_mode": "text",
        "intent": {"dramatic_function": "reveal", "primary_visual_event": "speaker finishes one line", "story_delta": "new fact", "emotion_delta": "doubt to focus", "knowledge_delta": "viewer learns fact", "relationship_delta": "trust changes"},
        "state": {"start_state": {"location": "office"}, "action_state": {"character": "LIN_LAN"}, "end_state": {"character": "LIN_LAN", "location": "office"}},
        "contract": {"first_frame_ref": None, "last_frame_ref": None, "allowed_behaviors": ["speak", "hold"], "forbidden_behaviors": ["pan", "cut"], "camera": {"scale": "medium", "position": "desk", "movement": "NONE", "axis": "none", "internal_cuts": 0}, "render_seconds": 6},
        "audio": {"dialogue": [{"speaker": "LIN_LAN", "content": "Hello", "start": 0.0, "end": 3.2, "audio_ref": "audio.wav"}], "narration": [], "sfx": [], "ambience": [], "music": [], "dialogue_duration": 3.2, "action_duration": 0, "hold_duration": 0.8, "render_seconds": 6},
        "asset_refs": [{"asset_id": "LIN_LAN", "asset_type": "character", "version": 1, "sha256": "a" * 64, "scope": "shot", "provider_ref": "https://example.com/anchor.png"}],
        "visible_character_ids": ["LIN_LAN"],
    }


def test_preflight_and_payload_make_contract_executable():
    shot = shot_fixture()
    assert preflight_shot(shot)["status"] == "CONTRACT_VALID"
    payload = build_payload(shot)
    assert "SHOT_CORE_CONTRACT" in payload["prompt"]
    assert '"movement": "NONE"' in payload["prompt"]
    assert generation_fingerprint(shot, payload) == generation_fingerprint(shot, payload)


def test_reference_payload_accepts_public_audio_references():
    shot = shot_fixture()
    shot["provider_mode"] = "reference"
    shot["provider_audio_refs"] = [{"provider_ref": "https://example.com/dialogue.mp3", "purpose": "rhythm"}]
    payload = build_payload(shot)
    assert payload["audios"] == ["https://example.com/dialogue.mp3"]
    assert "<Audio 1>" in payload["prompt"]


def test_reference_payload_rejects_local_audio_references():
    shot = shot_fixture()
    shot["provider_mode"] = "reference"
    shot["provider_audio_refs"] = [{"provider_ref": "D:\\视频创作\\temp\\line.mp3"}]
    with pytest.raises(ValueError, match="local audio references"):
        build_payload(shot)


def test_duration_hard_gate_blocks_before_provider():
    shot = shot_fixture()
    shot["contract"]["render_seconds"] = 3
    result = preflight_shot(shot)
    assert result["status"] == "BLOCKED"
    assert any(item.startswith("duration_contract_short") for item in result["errors"])


def test_run_take_never_calls_provider_when_contract_blocked(tmp_path: Path):
    class NeverCalled:
        def post(self, *args, **kwargs):
            raise AssertionError("provider must not be called")

    shot = shot_fixture()
    shot["contract"]["render_seconds"] = 3
    with pytest.raises(ValueError, match="provider admission blocked"):
        from runtime.shot_core import run_take
        run_take(shot, manifest_path=tmp_path / "manifest.json", output_path=tmp_path / "out.mp4", api_key="test", session=NeverCalled())


def test_take_lineage_and_stale_are_append_only(tmp_path: Path):
    path = tmp_path / "manifest.json"
    artifact = tmp_path / "x"
    artifact.write_bytes(b"clip")
    contract_fingerprint = canonical_hash({"placeholder": True})
    data = {"schema": "video_kingdom.shot_core_pilot.v1", "shots": {"PILOT_S01": {"shot_id": "PILOT_S01", "lifecycle": "REVIEWING", "stale": False, "contract_fingerprint": contract_fingerprint}}, "takes": [{"take_id": "PILOT_S01_T01", "shot_id": "PILOT_S01", "provider_status": "SUCCESS", "technical_status": "PASS", "creative_status": "PASS", "contract_fingerprint": contract_fingerprint, "artifact_path": str(artifact), "artifact_hash": hashlib.sha256(b"clip").hexdigest(), "machine_qc": {key: "PASS" for key in ("file_integrity", "resolution", "fps", "duration", "black_frames", "freeze_tail", "internal_cuts")}, "selected": False}], "events": []}
    save_manifest(path, data)
    record_decision(path, "PILOT_S01", "PILOT_S01_T01", creative="PASS", decision="PASS", reason="director accepted")
    updated = load_manifest(path)
    assert updated["shots"]["PILOT_S01"]["selected_take_id"] == "PILOT_S01_T01"
    assert updated["takes"][0]["selected"] is True
    result = propagate_stale(path, "PILOT_S01", ["first_frame_ref"])
    assert result["independent_shots_affected"] is False
    updated = load_manifest(path)
    assert updated["shots"]["PILOT_S01"]["stale"] is True
    assert updated["takes"][0]["selected"] is False
