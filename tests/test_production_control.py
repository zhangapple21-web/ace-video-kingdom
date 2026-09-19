from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import production_control.engine as engine
from production_control import ProductionControl, WorkflowError


def _write(path: Path, data: bytes = b"fixture") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def test_media_probe_honors_explicit_ffprobe_binary(monkeypatch, tmp_path: Path):
    calls = []

    class Completed:
        stdout = json.dumps({
            "format": {"duration": "1.5"},
            "streams": [{"width": 720, "height": 1280, "r_frame_rate": "24/1"}],
        })

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Completed()

    monkeypatch.setenv("FFPROBE_BIN", "C:/tools/ffprobe-custom.exe")
    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    result = engine._probe_media(tmp_path / "clip.mp4")
    assert result == {"duration_seconds": 1.5, "width": 720, "height": 1280, "fps": 24.0}
    assert calls[0][0][0] == "C:/tools/ffprobe-custom.exe"


def test_frame_extraction_honors_explicit_ffmpeg_binary(monkeypatch, tmp_path: Path):
    calls = []

    class Completed:
        stdout = "ffmpeg version test"

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[-1] != "-version":
            Path(command[-1]).write_bytes(b"png-fixture")
        return Completed()

    monkeypatch.setenv("FFMPEG_BIN", "C:/tools/ffmpeg-custom.exe")
    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    result = engine._extract_frames(tmp_path / "clip.mp4", tmp_path / "frames")
    assert result["tool_path"] == "C:/tools/ffmpeg-custom.exe"
    assert result["tool_version"] == "ffmpeg version test"
    assert result["first_frame"]["sha256"] == result["last_frame"]["sha256"]
    assert calls[0][0] == "C:/tools/ffmpeg-custom.exe"


def test_fail_closed_asset_gate_and_recovery(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", run_id="demo", mode="SANDBOX")
    asset = tmp_path / "run" / "char.png"
    continuity = tmp_path / "run" / "bridge.json"
    asset_hash = _write(asset)
    bridge_hash = _write(continuity, b"bridge")
    run.register_asset("CHAR_MAIN", "char.png", expected_sha256=asset_hash, role="character")
    run.register_continuity("S01-S02", from_shot="S01", to_shot="S02", evidence_path="bridge.json", expected_sha256=bridge_hash)
    assert run.evaluate_asset_gate()["status"] == "READY"
    run.lock_shot("S01", {"duration_seconds": {"min": 4, "max": 8}, "primary_action": "turn head", "actions": ["turn head"]})
    run.admit_generation("S01", {"model": "test", "prompt_hash": "abc"})
    media = tmp_path / "run" / "s01.mp4"
    _write(media, b"sandbox-media")
    run.record_generation("S01", "S01_T01", video_id="vid-1", artifact_path="s01.mp4", metadata={"duration_seconds": 5})
    run.record_qc("S01_T01", {key: "PASS" for key in ("picture", "motion", "camera", "continuity", "director")})
    run.select_take("S01", "S01_T01")
    assembled = tmp_path / "run" / "final.mp4"
    _write(assembled, b"assembled")
    run.record_assembly("final.mp4", ordered_shots=["S01"])
    assert run.promote_delivery()["status"] == "READY"
    assert run.mark_delivered(destination="sandbox://demo")["status"] == "DELIVERED"
    snapshot = run.snapshot()
    assert snapshot["stage"] == "DELIVERED"
    assert len(snapshot["events"]) >= 10
    assert all(snapshot["events"][i]["prev_event_hash"] == ("GENESIS" if i == 0 else snapshot["events"][i - 1]["event_hash"]) for i in range(len(snapshot["events"])))


def test_scope_metadata_is_persisted_on_production_run(tmp_path: Path):
    scope = {"kind": "SHOT_SUBSET", "shot_ids": ["S01", "S02"], "active_shot_id": "S01", "scope_id": "scope-1"}
    run = ProductionControl.create(
        tmp_path / "run" / "state.json",
        mode="PRODUCTION",
        scope=scope,
        plan_shot_ids=["S01", "S02", "S03"],
    )
    snapshot = run.snapshot()
    assert snapshot["scope"] == scope
    assert snapshot["plan_shot_ids"] == ["S01", "S02", "S03"]
    assert snapshot["total_plan_shots"] == 3


def test_missing_asset_blocks_and_no_generation_admission(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="SANDBOX")
    run.register_asset("MISSING", "missing.png")
    receipt = run.evaluate_asset_gate()
    assert receipt["status"] == "BLOCKED"
    assert run.snapshot()["stage"] == "ASSETS_BLOCKED"
    with pytest.raises(WorkflowError, match="ASSET_GATE_NOT_READY"):
        run.lock_shot("S01", {"duration_seconds": {"min": 4, "max": 8}, "primary_action": "hold"})


def test_generation_admission_is_idempotent_but_conflicts_are_blocked(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="SANDBOX")
    _write(tmp_path / "run" / "a", b"a")
    run.register_asset("A", "a")
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    first = run.admit_generation("S01", {"model": "test"})
    assert run.admit_generation("S01", {"model": "test"}) == first
    with pytest.raises(WorkflowError, match="GENERATION_ALREADY_ADMITTED"):
        run.admit_generation("S01", {"model": "different"})


def test_qc_requires_all_five_layers_and_blocks_unknown(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="SANDBOX")
    _write(tmp_path / "run" / "a", b"a")
    run.register_asset("A", "a")
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    run.admit_generation("S01", {"model": "test"})
    _write(tmp_path / "run" / "a.mp4", b"video")
    run.record_generation("S01", "T1", video_id="v", artifact_path="a.mp4")
    with pytest.raises(WorkflowError, match="QC_REQUIRES_EXACT_FIVE_LAYERS"):
        run.record_qc("T1", {"picture": "PASS"})
    receipt = run.record_qc("T1", {"picture": "PASS", "motion": "UNKNOWN", "camera": "PASS", "continuity": "PASS", "director": "PASS"})
    assert receipt["status"] == "BLOCKED"
    assert run.snapshot()["stage"] == "QC_BLOCKED"


def test_asset_regression_invalidates_downstream_and_allows_recovery(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="SANDBOX")
    asset = tmp_path / "run" / "a"
    _write(asset, b"a")
    run.register_asset("A", "a", expected_sha256=hashlib.sha256(b"a").hexdigest())
    assert run.evaluate_asset_gate()["status"] == "READY"
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    asset.write_bytes(b"drift")
    assert run.evaluate_asset_gate()["status"] == "BLOCKED"
    assert run.snapshot()["stage"] == "ASSETS_BLOCKED"
    with pytest.raises(WorkflowError, match="ASSET_GATE_NOT_READY"):
        run.admit_generation("S01", {"model": "test"})
    asset.write_bytes(b"a")
    assert run.evaluate_asset_gate()["status"] == "READY"
    run.admit_generation("S01", {"model": "test"})


def test_multiple_shots_can_be_locked_without_rewinding_global_stage(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="SANDBOX")
    _write(tmp_path / "run" / "a", b"a")
    run.register_asset("A", "a")
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    run.admit_generation("S01", {"model": "test"})
    run.lock_shot("S02", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "look"})
    run.admit_generation("S02", {"model": "test"})
    assert set(run.snapshot()["shots"]) == {"S01", "S02"}


def test_upstream_non_ready_receipt_keeps_gate_blocked(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="SANDBOX")
    _write(tmp_path / "run" / "a", b"a")
    receipt = tmp_path / "run" / "receipt.json"
    receipt.write_text(json.dumps({"schema": "upstream.v1", "status": "CONDITIONAL"}), encoding="utf-8")
    run.register_asset("A", "a")
    run.bind_asset_gate_receipt("receipt.json")
    result = run.evaluate_asset_gate()
    assert result["status"] == "BLOCKED"
    assert any(item["reason"] == "UPSTREAM_ASSET_GATE_NOT_READY" for item in result["errors"])


def test_state_hash_detects_materialized_state_tampering(tmp_path: Path):
    run_path = tmp_path / "run" / "state.json"
    run = ProductionControl.create(run_path, mode="SANDBOX")
    _write(tmp_path / "run" / "a", b"a")
    run.register_asset("A", "a")
    payload = json.loads(run_path.read_text(encoding="utf-8"))
    payload["stage"] = "DELIVERED"
    run_path.write_text(json.dumps(payload), encoding="utf-8")
    result = run.verify_event_chain()
    assert result["status"] == "FAIL"
    assert any(item["reason"] == "STATE_HASH_MISMATCH" for item in result["errors"])
    with pytest.raises(WorkflowError, match="RUN_INTEGRITY_INVALID"):
        run.register_asset("B", "a")


def test_asset_drift_is_rechecked_before_generation_admission(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="SANDBOX")
    asset = tmp_path / "run" / "a"
    _write(asset, b"a")
    run.register_asset("A", "a", expected_sha256=hashlib.sha256(b"a").hexdigest())
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    asset.write_bytes(b"drift")
    with pytest.raises(WorkflowError, match="ASSET_GATE_NOT_READY"):
        run.admit_generation("S01", {"model": "test"})


def test_assembly_rechecks_selected_take_hash(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="SANDBOX")
    _write(tmp_path / "run" / "a", b"a")
    run.register_asset("A", "a")
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    admission = run.admit_generation("S01", {"model": "test"})
    artifact = tmp_path / "run" / "s01.mp4"
    _write(artifact, b"video")
    run.record_generation("S01", "T1", video_id="v1", artifact_path="s01.mp4", metadata={"request_hash": admission["request_hash"]})
    run.record_qc("T1", {key: "PASS" for key in ("picture", "motion", "camera", "continuity", "director")})
    run.select_take("S01", "T1")
    artifact.write_bytes(b"changed")
    _write(tmp_path / "run" / "final.mp4", b"final")
    with pytest.raises(WorkflowError, match="ARTIFACT_HASH_DRIFT:T1"):
        run.record_assembly("final.mp4", ordered_shots=["S01"])


def test_qc_refuses_drifted_take_before_writing_pass(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="SANDBOX")
    _write(tmp_path / "run" / "a", b"a")
    run.register_asset("A", "a")
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    run.admit_generation("S01", {"model": "test"})
    artifact = tmp_path / "run" / "s01.mp4"
    _write(artifact, b"video")
    run.record_generation("S01", "T1", video_id="v1", artifact_path="s01.mp4")
    artifact.write_bytes(b"changed")
    with pytest.raises(WorkflowError, match="ARTIFACT_HASH_DRIFT:T1"):
        run.record_qc("T1", {key: "PASS" for key in ("picture", "motion", "camera", "continuity", "director")})


def test_production_delivery_requires_final_acceptance_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(engine, "_probe_media", lambda path: {"duration_seconds": 1.0, "width": 720, "height": 1280, "fps": 24.0})
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="PRODUCTION")
    _write(tmp_path / "run" / "asset.bin", b"x" * 5000)
    run.register_asset("A", "asset.bin", expected_sha256=hashlib.sha256(b"x" * 5000).hexdigest())
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    admission = run.admit_generation("S01", {"model": "test"})
    _write(tmp_path / "run" / "s01.mp4", b"video")
    run.record_generation("S01", "T1", video_id="v1", artifact_path="s01.mp4", metadata={"request_hash": admission["request_hash"]})
    run.record_qc("T1", {key: "PASS" for key in ("picture", "motion", "camera", "continuity", "director")})
    run.select_take("S01", "T1")
    _write(tmp_path / "run" / "final.mp4", b"final")
    run.record_assembly("final.mp4", ordered_shots=["S01"])
    with pytest.raises(WorkflowError, match="ACCEPTANCE_RECEIPT_REQUIRED"):
        run.promote_delivery()


def test_production_multi_shot_admission_requires_continuity_edges(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="PRODUCTION")
    _write(tmp_path / "run" / "asset.bin", b"x" * 5000)
    run.register_asset("A", "asset.bin", expected_sha256=hashlib.sha256(b"x" * 5000).hexdigest())
    run.evaluate_asset_gate()
    for shot_id in ("S01", "S02"):
        run.lock_shot(shot_id, {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    with pytest.raises(WorkflowError, match="ASSET_GATE_NOT_READY"):
        run.admit_generation("S01", {"model": "test"})


def test_production_asset_gate_rejects_missing_hash_and_tiny_placeholder(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="PRODUCTION")
    _write(tmp_path / "run" / "tiny.png", b"tiny")
    run.register_asset("TINY", "tiny.png")
    receipt = run.evaluate_asset_gate()
    reasons = {item["reason"] for item in receipt["errors"]}
    assert receipt["status"] == "BLOCKED"
    assert "SHA256_REQUIRED_IN_PRODUCTION" in reasons
    assert "PLACEHOLDER_OR_TOO_SMALL" in reasons


def test_assembly_requires_every_locked_shot_and_delivery_rechecks_hash(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="SANDBOX")
    _write(tmp_path / "run" / "a", b"a")
    run.register_asset("A", "a")
    run.evaluate_asset_gate()
    for shot_id in ("S01", "S02"):
        run.lock_shot(shot_id, {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
        run.admit_generation(shot_id, {"model": "test"})
        _write(tmp_path / "run" / f"{shot_id}.mp4", shot_id.encode())
        run.record_generation(shot_id, f"{shot_id}_T1", video_id=f"v-{shot_id}", artifact_path=f"{shot_id}.mp4")
        run.record_qc(f"{shot_id}_T1", {key: "PASS" for key in ("picture", "motion", "camera", "continuity", "director")})
        run.select_take(shot_id, f"{shot_id}_T1")
    _write(tmp_path / "run" / "final.mp4", b"final")
    with pytest.raises(WorkflowError, match="ASSEMBLY_SHOT_SET_MISMATCH"):
        run.record_assembly("final.mp4", ordered_shots=["S01"])
    run.record_assembly("final.mp4", ordered_shots=["S01", "S02"])
    (tmp_path / "run" / "final.mp4").write_bytes(b"drift")
    with pytest.raises(WorkflowError, match="ASSEMBLY_HASH_DRIFT"):
        run.promote_delivery()


def test_delivery_rejects_selection_drift_after_assembly(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="SANDBOX")
    _write(tmp_path / "run" / "a", b"a")
    run.register_asset("A", "a")
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    admission = run.admit_generation("S01", {"model": "test"})
    for take_id, payload in (("T1", b"one"), ("T2", b"two")):
        _write(tmp_path / "run" / f"{take_id}.mp4", payload)
        run.record_generation("S01", take_id, video_id=take_id, artifact_path=f"{take_id}.mp4", metadata={"request_hash": admission["request_hash"]})
        run.record_qc(take_id, {key: "PASS" for key in ("picture", "motion", "camera", "continuity", "director")})
    run.select_take("S01", "T1")
    _write(tmp_path / "run" / "final.mp4", b"final")
    run.record_assembly("final.mp4", ordered_shots=["S01"])
    run.select_take("S01", "T2")
    with pytest.raises(WorkflowError, match="ASSEMBLY_SELECTION_DRIFT"):
        run.promote_delivery()


def test_production_acceptance_requires_all_lanes_and_output_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(engine, "_probe_media", lambda path: {"duration_seconds": 1.0, "width": 720, "height": 1280, "fps": 24.0})
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="PRODUCTION")
    _write(tmp_path / "run" / "asset.bin", b"x" * 5000)
    run.register_asset("A", "asset.bin", expected_sha256=hashlib.sha256(b"x" * 5000).hexdigest())
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    admission = run.admit_generation("S01", {"model": "test"})
    _write(tmp_path / "run" / "s01.mp4", b"video")
    run.record_generation("S01", "T1", video_id="v1", artifact_path="s01.mp4", metadata={"request_hash": admission["request_hash"]})
    run.record_qc("T1", {key: "PASS" for key in ("picture", "motion", "camera", "continuity", "director")})
    run.select_take("S01", "T1")
    final_hash = _write(tmp_path / "run" / "final.mp4", b"final")
    acceptance = tmp_path / "run" / "acceptance.json"
    acceptance.write_text(json.dumps({"status": "PASS", "delivery_approved": True, "output": "final.mp4"}), encoding="utf-8")
    run.record_assembly("final.mp4", ordered_shots=["S01"], metadata={"acceptance_path": "acceptance.json", "acceptance_sha256": hashlib.sha256(acceptance.read_bytes()).hexdigest()})
    with pytest.raises(WorkflowError, match="ACCEPTANCE_LANES_NOT_READY"):
        run.promote_delivery()
    acceptance.write_text(json.dumps({
        "status": "PASS", "delivery_approved": True, "output": "final.mp4", "artifact_sha256": final_hash,
        "pacing": {"status": "PASS"}, "continuity": {"status": "PASS"}, "subtitle": "PASS", "audio": "PASS", "creative": "PASS",
    }), encoding="utf-8")
    # The receipt itself is hash-bound in the assembly metadata, so update the
    # assembly record through a fresh run for the valid-path assertion.
    valid = ProductionControl.create(tmp_path / "valid" / "state.json", mode="PRODUCTION")
    _write(tmp_path / "valid" / "asset.bin", b"x" * 5000)
    valid.register_asset("A", "asset.bin", expected_sha256=hashlib.sha256(b"x" * 5000).hexdigest())
    valid.evaluate_asset_gate()
    valid.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    admission = valid.admit_generation("S01", {"model": "test"})
    _write(tmp_path / "valid" / "s01.mp4", b"video")
    valid.record_generation("S01", "T1", video_id="v1", artifact_path="s01.mp4", metadata={"request_hash": admission["request_hash"]})
    valid.record_qc("T1", {key: "PASS" for key in ("picture", "motion", "camera", "continuity", "director")})
    valid.select_take("S01", "T1")
    valid_final_hash = _write(tmp_path / "valid" / "final.mp4", b"final")
    valid_acceptance = tmp_path / "valid" / "acceptance.json"
    valid_acceptance.write_text(json.dumps({
        "status": "PASS", "delivery_approved": True, "output": "final.mp4", "artifact_sha256": valid_final_hash,
        "pacing": {"status": "PASS"}, "continuity": {"status": "PASS"}, "subtitle": "PASS", "audio": "PASS", "creative": "PASS",
    }), encoding="utf-8")
    valid.record_assembly("final.mp4", ordered_shots=["S01"], metadata={"acceptance_path": "acceptance.json", "acceptance_sha256": hashlib.sha256(valid_acceptance.read_bytes()).hexdigest()})
    assert valid.promote_delivery()["status"] == "READY"
    with pytest.raises(WorkflowError, match="DELIVERY_AUTHORIZATION_REQUIRED"):
        valid.mark_delivered(destination="https://example.invalid/video.mp4")
    delivered = valid.mark_delivered(destination="https://example.invalid/video.mp4", authorized=True)
    assert delivered["status"] == "DELIVERED"
    assert delivered["authorization_confirmed"] is True


def test_production_continuity_receipt_must_be_semantically_ready(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="PRODUCTION")
    asset_hash = _write(tmp_path / "run" / "asset.bin", b"x" * 5000)
    bridge = tmp_path / "run" / "bridge.json"
    bridge.write_text(json.dumps({"status": "BLOCKED", "from_shot": "S01", "to_shot": "S02"}), encoding="utf-8")
    run.register_asset("A", "asset.bin", expected_sha256=asset_hash)
    run.register_continuity("S01-S02", from_shot="S01", to_shot="S02", evidence_path="bridge.json", expected_sha256=hashlib.sha256(bridge.read_bytes()).hexdigest())
    # The semantic continuity check is evaluated against the declared edge and
    # must block before any production admission.
    result = run.evaluate_asset_gate()
    assert result["status"] == "BLOCKED"
    assert any(item["reason"] == "CONTINUITY_EVIDENCE_NOT_READY" for item in result["errors"])


def test_production_generation_requires_admission_hash_and_contained_artifact(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="PRODUCTION")
    asset = tmp_path / "run" / "asset.bin"
    asset_hash = _write(asset, b"x" * 5000)
    run.register_asset("A", "asset.bin", expected_sha256=asset_hash)
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    admission = run.admit_generation("S01", {"model": "test"})
    _write(tmp_path / "run" / "clip.mp4", b"clip")
    with pytest.raises(WorkflowError, match="GENERATION_REQUEST_HASH_REQUIRED"):
        run.record_generation("S01", "T1", video_id="v1", artifact_path="clip.mp4")
    with pytest.raises(WorkflowError, match="ARTIFACT_PATH_ESCAPE"):
        run.record_generation("S01", "T1", video_id="v1", artifact_path="../clip.mp4", metadata={"request_hash": admission["request_hash"]})


def test_production_delivery_rechecks_per_shot_continuity_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(engine, "_probe_media", lambda path: {"duration_seconds": 1.0, "width": 720, "height": 1280, "fps": 24.0})
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="PRODUCTION")
    asset_hash = _write(tmp_path / "run" / "asset.bin", b"x" * 5000)
    run.register_asset("A", "asset.bin", expected_sha256=asset_hash)
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    admission = run.admit_generation("S01", {"model": "test"})
    _write(tmp_path / "run" / "s01.mp4", b"video")
    run.record_generation("S01", "T1", video_id="v1", artifact_path="s01.mp4", metadata={"request_hash": admission["request_hash"]})
    run.record_qc("T1", {key: "PASS" for key in ("picture", "motion", "camera", "continuity", "director")})
    run.select_take("S01", "T1")
    final_hash = _write(tmp_path / "run" / "final.mp4", b"final")
    acceptance = tmp_path / "run" / "acceptance.json"
    acceptance.write_text(json.dumps({
        "status": "PASS", "delivery_approved": True, "output": "final.mp4", "artifact_sha256": final_hash,
        "pacing": {"status": "PASS"},
        "continuity": {"status": "PASS", "shots": [{"shot_id": "S01", "status": "REVIEW_REQUIRED"}], "review": []},
        "subtitle": "PASS", "audio": "PASS", "creative": "PASS",
    }), encoding="utf-8")
    run.record_assembly("final.mp4", ordered_shots=["S01"], metadata={
        "acceptance_path": "acceptance.json",
        "acceptance_sha256": hashlib.sha256(acceptance.read_bytes()).hexdigest(),
    })
    with pytest.raises(WorkflowError, match="ACCEPTANCE_CONTINUITY_REVIEW_REQUIRED"):
        run.promote_delivery()
