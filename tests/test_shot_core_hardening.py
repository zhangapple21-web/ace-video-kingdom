from __future__ import annotations

import json
from pathlib import Path

import pytest

import runtime.shot_core as core
from tests.test_shot_core_runtime import shot_fixture
from tools.run_comedy_episode import _review_continuity


class Response:
    def __init__(self, status_code: int, body: dict, *, content: bytes = b"", content_type: str = "video/mp4"):
        self.status_code = status_code
        self._body = body
        self.content = content
        self.text = json.dumps(body)
        self.headers = {"content-type": content_type}

    def json(self):
        return self._body


class Session:
    def __init__(self, poll_body: dict):
        self.poll_body = poll_body
        self.posts = 0
        self.gets = 0

    def post(self, *args, **kwargs):
        self.posts += 1
        return Response(200, {"video_id": "vid-1", "status": "queued"})

    def get(self, url, *args, **kwargs):
        self.gets += 1
        if "agnesapi" in url:
            return Response(200, self.poll_body)
        return Response(200, {}, content=b"not-a-real-video")


def test_payload_contains_audio_contract_and_negative_prompt():
    shot = shot_fixture()
    shot["negative_prompt"] = "no extra people"
    payload = core.build_payload(shot)
    assert "negative_prompt" not in payload
    assert "no extra people" in payload["prompt"]
    assert '"dialogue_duration": 3.2' in payload["prompt"]
    assert '"render_seconds": 6' in payload["prompt"]


def test_keyframe_mode_requires_first_frame():
    shot = shot_fixture()
    shot["provider_mode"] = "keyframe"
    shot["contract"]["first_frame_ref"] = None
    result = core.preflight_shot(shot)
    assert result["status"] == "BLOCKED"
    assert "keyframe_mode_requires_first_frame_ref" in result["errors"]


def test_static_same_frame_keyframe_is_blocked_as_unverified_hold():
    shot = shot_fixture()
    shot["provider_mode"] = "keyframe"
    shot["contract"]["first_frame_ref"] = "asset://scene"
    shot["contract"]["last_frame_ref"] = "asset://scene"
    result = core.preflight_shot(shot)
    assert result["status"] == "BLOCKED"
    assert "static_keyframe_hold_requires_verified_control_surface" in result["errors"]


def test_required_negative_prompt_is_a_hard_gate():
    shot = shot_fixture()
    shot["require_negative_prompt"] = True
    result = core.preflight_shot(shot)
    assert result["status"] == "BLOCKED"
    assert "required_negative_prompt_missing" in result["errors"]


def test_reference_mode_can_bind_only_the_approved_scene_anchor():
    shot = shot_fixture()
    shot["provider_mode"] = "reference"
    shot["asset_refs"].append({"asset_id": "SCENE", "asset_type": "scene", "version": 1, "sha256": "b" * 64, "scope": "shot", "provider_ref": "https://example.com/scene.png"})
    shot["provider_asset_ids"] = ["SCENE"]
    payload = core.build_payload(shot)
    assert payload["images"] == ["https://example.com/scene.png"]
    assert "provider_asset_ids" not in payload


def test_data_uri_asset_reference_is_blocked():
    shot = shot_fixture()
    shot["asset_refs"][0]["provider_ref"] = "data:image/webp;base64,ZmFrZQ=="
    result = core.preflight_shot(shot)
    assert result["status"] == "BLOCKED"
    assert "asset_ref_data_uri_forbidden:LIN_LAN" in result["errors"]


def test_local_asset_reference_requires_verified_bounded_webp(tmp_path: Path):
    from PIL import Image

    image_path = tmp_path / "anchor.webp"
    Image.new("RGB", (32, 32), (20, 40, 60)).save(image_path, format="WEBP")
    shot = shot_fixture()
    shot["asset_refs"][0].update({
        "provider_ref": str(image_path),
        "path": str(image_path),
        "sha256": core.file_hash(image_path),
        "size_bytes": image_path.stat().st_size,
    })
    assert core.preflight_shot(shot)["status"] == "CONTRACT_VALID"
    shot["asset_refs"][0]["sha256"] = "b" * 64
    result = core.preflight_shot(shot)
    assert result["status"] == "BLOCKED"
    assert "asset_ref_sha256_mismatch:LIN_LAN" in result["errors"]


def test_reference_payload_rejects_local_metadata_for_url_provider(tmp_path: Path):
    from PIL import Image

    image_path = tmp_path / "anchor.webp"
    Image.new("RGB", (32, 32), (20, 40, 60)).save(image_path, format="WEBP")
    shot = shot_fixture()
    shot["provider_mode"] = "reference"
    shot["asset_refs"][0].update({
        "provider_ref": str(image_path),
        "path": str(image_path),
        "sha256": core.file_hash(image_path),
        "size_bytes": image_path.stat().st_size,
    })
    with pytest.raises(ValueError, match="Provider-compatible"):
        core.build_payload(shot)


def test_terminal_provider_failure_is_not_reported_as_timeout(tmp_path: Path):
    shot = shot_fixture()
    session = Session({"status": "failed", "error": "provider rejected request"})
    result = core.run_take(shot, manifest_path=tmp_path / "manifest.json", output_path=tmp_path / "out.mp4", api_key="test", session=session, poll_delay=0, timeout=1)
    assert result["provider_status"] == "FAILED"
    assert result["failure_reason"] == "provider rejected request"
    assert result["failure_reason"] != "POLL_TIMEOUT"


def test_completed_without_url_is_durable_failure(tmp_path: Path):
    shot = shot_fixture()
    session = Session({"status": "completed"})
    result = core.run_take(shot, manifest_path=tmp_path / "manifest.json", output_path=tmp_path / "out.mp4", api_key="test", session=session, poll_delay=0, timeout=1)
    assert result["provider_status"] == "SUCCESS"
    assert result["status"] == "FAILED"
    assert result["failure_reason"] == "COMPLETED_WITHOUT_ARTIFACT_URL"
    assert core.load_manifest(tmp_path / "manifest.json")["shots"][shot["shot_id"]]["lifecycle"] == "REWORK"


def test_duplicate_fingerprint_is_blocked_before_provider(tmp_path: Path):
    shot = shot_fixture()
    path = tmp_path / "manifest.json"
    payload = core.build_payload(shot)
    data = {"shots": {}, "takes": [{"take_id": "PILOT_S01_T01", "shot_id": shot["shot_id"], "generation_fingerprint": core.generation_fingerprint(shot, payload), "stale": False}], "events": []}
    core.save_manifest(path, data)
    with pytest.raises(ValueError, match="duplicate_generation_fingerprint"):
        core.run_take(shot, manifest_path=path, output_path=tmp_path / "out.mp4", api_key="test", session=Session({"status": "failed"}))


def test_stale_propagates_only_to_explicit_dependents(tmp_path: Path):
    path = tmp_path / "manifest.json"
    core.save_manifest(path, {"shots": {"A": {"shot_id": "A", "lifecycle": "SELECTED", "selected_take_id": "A_T01"}, "B": {"shot_id": "B", "depends_on_shots": ["A"], "lifecycle": "SELECTED", "selected_take_id": "B_T01"}, "C": {"shot_id": "C", "lifecycle": "SELECTED", "selected_take_id": "C_T01"}}, "takes": [{"take_id": "A_T01", "shot_id": "A", "status": "SELECTED", "selected": True}, {"take_id": "B_T01", "shot_id": "B", "status": "SELECTED", "selected": True}, {"take_id": "C_T01", "shot_id": "C", "status": "SELECTED", "selected": True}], "events": []})
    result = core.propagate_stale(path, "A", ["first_frame_ref"])
    assert result["affected_shots"] == ["A", "B"]
    updated = core.load_manifest(path)
    assert updated["shots"]["C"].get("stale") is not True
    assert updated["takes"][1]["status"] == "GENERATED"


def test_stale_take_cannot_be_selected_again(tmp_path: Path):
    path = tmp_path / "manifest.json"
    core.save_manifest(path, {"shots": {"A": {"shot_id": "A", "lifecycle": "REVIEWING"}}, "takes": [{"take_id": "A_T01", "shot_id": "A", "provider_status": "SUCCESS", "technical_status": "PASS", "creative_status": "PASS", "selected": False}], "events": []})
    core.propagate_stale(path, "A", ["prompt"])
    with pytest.raises(ValueError, match="stale take"):
        core.record_decision(path, "A", "A_T01", creative="PASS", decision="PASS", reason="should not select stale take")


def test_continuity_spike_never_synthesizes_pass():
    result = _review_continuity("A", {"status": "PASS", "internal_scene_cut_count": 0}, {"status": "REVIEW_REQUIRED", "spike_count": 2})
    assert result["status"] == "REVIEW_REQUIRED"
    assert "reviewer" not in result


def test_manifest_audit_catches_cross_shot_selection_and_stale_selection(tmp_path: Path):
    path = tmp_path / "manifest.json"
    core.save_manifest(path, {"shots": {"A": {"shot_id": "A", "selected_take_id": "B_T01"}, "B": {"shot_id": "B", "selected_take_id": "B_T01", "stale": True}}, "takes": [{"take_id": "B_T01", "shot_id": "B", "selected": True, "stale": True}], "events": []})
    report = core.audit_manifest(path)
    assert report["status"] == "FAIL"
    assert any("cross_shot" in item or "not_eligible" in item for item in report["errors"])


def test_malformed_contract_and_audio_are_blocked_not_crashed():
    assert core.preflight_shot(None)["status"] == "BLOCKED"
    assert core.preflight_shot([])["status"] == "BLOCKED"
    shot = shot_fixture()
    shot["audio"] = []
    assert core.preflight_shot(shot)["status"] == "BLOCKED"
    shot = shot_fixture()
    shot["contract"] = []
    assert core.preflight_shot(shot)["status"] == "BLOCKED"


def test_manifest_audit_catches_selected_artifact_hash_and_status(tmp_path: Path):
    path = tmp_path / "manifest.json"
    artifact = tmp_path / "clip.mp4"
    artifact.write_bytes(b"clip")
    core.save_manifest(path, {"shots": {"A": {"shot_id": "A", "selected_take_id": "A_T01"}}, "takes": [{
        "take_id": "A_T01", "shot_id": "A", "selected": True, "status": "SELECTED",
        "provider_status": "FAILED", "technical_status": "UNKNOWN", "creative_status": "PASS",
        "artifact_path": str(artifact), "artifact_hash": "0" * 64, "bytes": 99,
    }], "events": []})
    report = core.audit_manifest(path)
    assert report["status"] == "FAIL"
    assert any("artifact_hash_mismatch" in item for item in report["errors"])
    assert any("provider_not_success" in item for item in report["errors"])


def test_dialogue_ranges_cannot_overlap_or_exceed_render():
    shot = shot_fixture()
    shot["audio"]["dialogue"] = [
        {"speaker": "LIN_LAN", "content": "one", "start": 0, "end": 2, "audio_ref": "a.wav"},
        {"speaker": "LIN_LAN", "content": "two", "start": 1.5, "end": 7, "audio_ref": "b.wav"},
    ]
    shot["audio"]["dialogue_duration"] = 2
    result = core.preflight_shot(shot)
    assert result["status"] == "BLOCKED"
    assert "dialogue_lines_overlap" in result["errors"]
    assert "dialogue_line_exceeds_render_seconds" in result["errors"]


def test_stale_parent_cannot_start_new_take(tmp_path: Path):
    shot = shot_fixture()
    path = tmp_path / "manifest.json"
    core.save_manifest(path, {"shots": {}, "takes": [{"take_id": "PILOT_S01_T01", "shot_id": shot["shot_id"], "stale": True}], "events": []})
    with pytest.raises(ValueError, match="parent_take_is_stale"):
        core.run_take(shot, manifest_path=path, output_path=tmp_path / "out.mp4", api_key="test", parent_take_id="PILOT_S01_T01", branch_reason="REWORK", session=Session({"status": "failed"}))


def test_stale_shot_cannot_be_silently_cleared(tmp_path: Path):
    shot = shot_fixture()
    path = tmp_path / "manifest.json"
    fingerprint = core.canonical_hash(shot)
    core.save_manifest(path, {"shots": {shot["shot_id"]: {"shot_id": shot["shot_id"], "stale": True, "contract_fingerprint": fingerprint}}, "takes": [], "events": []})
    with pytest.raises(ValueError, match="shot_is_stale_requires_reconciliation"):
        core.run_take(shot, manifest_path=path, output_path=tmp_path / "out.mp4", api_key="test", session=Session({"status": "failed"}))


def test_machine_qc_records_detector_failure_as_unknown(monkeypatch, tmp_path: Path):
    artifact = tmp_path / "clip.mp4"
    artifact.write_bytes(b"placeholder")
    monkeypatch.setattr(core, "_run_media_filter", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("ffmpeg unavailable")))
    result = core.machine_qc({"duration_seconds": 5, "width": 720, "height": 1280, "fps": "24/1", "has_audio": False}, expected_seconds=5, required_seconds=5, artifact_path=artifact, expected_internal_cuts=0)
    assert result["detector_errors"]
    assert result["black_frames"] == "UNKNOWN"
    assert result["freeze_tail"] == "UNKNOWN"
    assert result["internal_cuts"] == "UNKNOWN"


def test_unknown_submission_is_not_auto_retried_and_terminal_failure_is(tmp_path: Path):
    shot = shot_fixture()
    path = tmp_path / "manifest.json"
    payload = core.build_payload(shot)
    fp = core.generation_fingerprint(shot, payload)
    core.save_manifest(path, {"shots": {}, "takes": [{"take_id": "PILOT_S01_T01", "shot_id": shot["shot_id"], "generation_fingerprint": fp, "provider_status": "UNKNOWN", "status": "UNKNOWN_SUBMISSION", "video_id": "vid-1"}], "events": []})
    with pytest.raises(ValueError, match="duplicate_generation_fingerprint"):
        core.run_take(shot, manifest_path=path, output_path=tmp_path / "new.mp4", api_key="test", session=Session({"status": "failed"}))

    core.save_manifest(path, {"shots": {}, "takes": [{"take_id": "PILOT_S01_T01", "shot_id": shot["shot_id"], "generation_fingerprint": fp, "provider_status": "FAILED", "status": "FAILED"}], "events": []})
    result = core.run_take(shot, manifest_path=path, output_path=tmp_path / "new.mp4", api_key="test", session=Session({"status": "failed"}), timeout=1)
    assert result["take_id"] == "PILOT_S01_T02"


def test_resume_take_is_poll_only(tmp_path: Path):
    shot = shot_fixture()
    path = tmp_path / "manifest.json"
    core.save_manifest(path, {"shots": {shot["shot_id"]: {"shot_id": shot["shot_id"], "lifecycle": "REWORK"}}, "takes": [{"take_id": "PILOT_S01_T01", "shot_id": shot["shot_id"], "video_id": "vid-1", "provider_status": "UNKNOWN", "status": "UNKNOWN_SUBMISSION"}], "events": []})
    class PollOnly(Session):
        def post(self, *args, **kwargs):
            raise AssertionError("resume must not POST")
    result = core.resume_take(manifest_path=path, take_id="PILOT_S01_T01", api_key="test", session=PollOnly({"status": "failed", "error": "gone"}), timeout=1)
    assert result["provider_status"] == "FAILED"
    assert result["reconcile_required"] is False


def test_manifest_revision_conflict_is_rejected(tmp_path: Path):
    path = tmp_path / "manifest.json"
    core.save_manifest(path, {"shots": {}, "takes": [], "events": []})
    first = core.load_manifest(path)
    second = core.load_manifest(path)
    first["events"].append({"event": "one"})
    core.save_manifest(path, first)
    second["events"].append({"event": "two"})
    with pytest.raises(core.ManifestConflictError, match="manifest_revision_conflict"):
        core.save_manifest(path, second)


def test_manifest_audit_catches_contract_mismatch_and_dependency_cycle(tmp_path: Path):
    path = tmp_path / "manifest.json"
    core.save_manifest(path, {"shots": {"A": {"shot_id": "A", "contract_fingerprint": "new", "selected_take_id": "A_T01", "depends_on_shots": ["B"]}, "B": {"shot_id": "B", "contract_fingerprint": "b", "depends_on_shots": ["A"]}}, "takes": [{"take_id": "A_T01", "shot_id": "A", "selected": True, "status": "SELECTED", "provider_status": "SUCCESS", "technical_status": "PASS", "creative_status": "PASS", "contract_fingerprint": "old", "artifact_path": str(tmp_path / "missing"), "artifact_hash": "x", "machine_qc": {k: "PASS" for k in ("file_integrity", "resolution", "fps", "duration", "black_frames", "freeze_tail", "internal_cuts")}}], "events": []})
    report = core.audit_manifest(path)
    assert any("contract_mismatch" in e for e in report["errors"])
    assert any("dependency_cycle" in e for e in report["errors"])


def test_machine_qc_can_enforce_expected_media_profile():
    result = core.machine_qc({"duration_seconds": 5, "width": 704, "height": 1280, "fps": "24/1", "has_audio": False}, expected_seconds=5, required_seconds=5, expected_width=720, expected_height=1280)
    assert result["resolution"] == "FAIL"


def test_dialogue_lines_cannot_bypass_zero_duration():
    shot = shot_fixture()
    shot["audio"]["dialogue_duration"] = 0
    result = core.preflight_shot(shot)
    assert result["status"] == "BLOCKED"
    assert "dialogue_lines_require_positive_dialogue_duration" in result["errors"]


def test_resume_can_finalize_remote_artifact_without_selecting(tmp_path: Path, monkeypatch):
    shot = shot_fixture()
    path = tmp_path / "manifest.json"
    core.save_manifest(path, {"shots": {shot["shot_id"]: {"shot_id": shot["shot_id"], "lifecycle": "RECONCILE"}}, "takes": [{
        "take_id": "PILOT_S01_T01", "shot_id": shot["shot_id"], "video_id": "vid-1",
        "provider_status": "UNKNOWN", "status": "UNKNOWN_SUBMISSION", "shot_snapshot": {
            "contract": shot["contract"], "audio": shot["audio"], "media_profile": {}
        }
    }], "events": []})
    class Completed(Session):
        def get(self, url, *args, **kwargs):
            self.gets += 1
            if "agnesapi" in url:
                return Response(200, {"status": "completed", "url": "https://example.test/clip.mp4"})
            return Response(200, {}, content=b"video-bytes")
    monkeypatch.setattr(core, "_probe", lambda path: {"duration_seconds": 6.0, "width": 720, "height": 1280, "fps": "24/1", "has_audio": False})
    monkeypatch.setattr(core, "_run_media_filter", lambda *args, **kwargs: "")
    out = tmp_path / "recovered.mp4"
    result = core.resume_take(manifest_path=path, take_id="PILOT_S01_T01", output_path=out, api_key="test", session=Completed({}), timeout=1)
    assert result["status"] == "GENERATED"
    assert result["artifact_finalize_status"] == "PASS"
    assert result["selected"] is False
    assert out.read_bytes() == b"video-bytes"
