from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from production_control import engine
from production_control.demand import infer_goal, route
from production_control import ProductionControl, WorkflowError
from production_control.workflow import ingest_execution
from tools.medium_lock import character_performance_lock


def _write(path: Path, payload: bytes = b"x" * 5000) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _plan(root: Path, *, bridge: bool) -> Path:
    asset = root / "assets" / "scene.bin"
    asset_hash = _write(asset)
    bridge_path = root / "bridges" / "S01-S02.json"
    if bridge:
        _write(bridge_path, json.dumps({"status": "READY", "from_shot": "S01", "to_shot": "S02"}).encode("utf-8"))
    data = {
        "project_id": "demand-demo",
        "production_integration": False,
        "medium_lock": character_performance_lock(),
        "assets": {"scene": [{"asset_id": "SCENE", "reference_path": "assets/scene.bin", "sha256": asset_hash}]},
        "shots": [
            {
                "shot_id": "S01",
                "action": "hold",
                "render": {"seconds": 4},
                "shot_contract": {"single_action": True},
                "continuity_evidence_path": "bridges/S01-S02.json" if bridge else None,
                "generation_request": {"model": "test", "prompt": "hold"},
            },
            {
                "shot_id": "S02",
                "action": "look",
                "render": {"seconds": 4},
                "shot_contract": {"single_action": True},
                "generation_request": {"model": "test", "prompt": "look"},
            },
        ],
    }
    path = root / "episode_plan.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_goal_inference_is_small_and_deterministic():
    assert infer_goal(text="继续上次的视频") == "RESUME"
    assert infer_goal(text="看一下当前状态") == "AUDIT"
    assert infer_goal(text="把成片交付") == "DELIVER"
    assert infer_goal(text="做一个短片") == "PRODUCE"


def test_route_stops_at_blocked_asset_gate_without_admission(tmp_path: Path):
    plan = _plan(tmp_path, bridge=False)
    result = route({"goal": "PRODUCE", "plan": str(plan)}, root=tmp_path)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "ASSET_GATE_BLOCKED"
    assert result["run"] is None
    assert not (tmp_path / ".control" / "production_run.json").exists()
    receipt = Path(result["preflight_receipt"])
    assert receipt.is_file()
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert any(row["reason"] == "CONTINUITY_EVIDENCE_MISSING" for row in payload["errors"])


def test_route_advances_ready_plan_and_returns_external_execution_boundary(tmp_path: Path):
    plan = _plan(tmp_path, bridge=True)
    result = route({"goal": "PRODUCE", "plan": str(plan)}, root=tmp_path)
    assert result["status"] == "READY_FOR_EXECUTION"
    assert result["external_action_required"]
    payload = json.loads((tmp_path / ".control" / "production_run.json").read_text(encoding="utf-8"))
    assert payload["stage"] == "GENERATION_ADMITTED"
    assert {row["shot_id"] for row in payload["generation_admissions"]} == {"S01", "S02"}


def test_resume_uses_persisted_admission_without_original_plan(tmp_path: Path):
    plan = _plan(tmp_path, bridge=True)
    first = route({"goal": "PRODUCE", "plan": str(plan)}, root=tmp_path)
    assert first["status"] == "READY_FOR_EXECUTION"
    run_path = tmp_path / ".control" / "production_run.json"
    resumed = route({"text": "继续上次的视频", "run": str(run_path)}, root=tmp_path)
    assert resumed["status"] == "READY_FOR_EXECUTION"
    assert "PLAN_REQUIRED_FOR_ADMISSION" not in str(resumed)


def test_resume_discovers_latest_run_without_explicit_path(tmp_path: Path):
    plan = _plan(tmp_path, bridge=True)
    first = route({"goal": "PRODUCE", "plan": str(plan)}, root=tmp_path)
    assert first["status"] == "READY_FOR_EXECUTION"
    resumed = route({"text": "继续上次的视频"}, root=tmp_path)
    assert resumed["status"] == "READY_FOR_EXECUTION"
    assert "discover_latest_run" in resumed["actions_taken"]


def test_route_repairs_partial_per_shot_admission(tmp_path: Path):
    plan = _plan(tmp_path, bridge=True)
    run_path = tmp_path / ".control" / "production_run.json"
    run = ProductionControl(run_path)
    run = ProductionControl.create(run_path, mode="SANDBOX", root=tmp_path)
    asset_hash = hashlib.sha256((tmp_path / "assets" / "scene.bin").read_bytes()).hexdigest()
    run.register_asset("SCENE", "assets/scene.bin", expected_sha256=asset_hash)
    run.register_continuity("S01->S02", from_shot="S01", to_shot="S02", evidence_path="bridges/S01-S02.json")
    run.evaluate_asset_gate()
    for shot_id, action in (("S01", "hold"), ("S02", "look")):
        run.lock_shot(shot_id, {"duration_seconds": {"min": 4, "max": 4}, "primary_action": action, "actions": [action]})
    run.admit_generation("S01", {"model": "test", "prompt": "hold"})
    resumed = route({"goal": "RESUME", "plan": str(plan), "run": str(run_path)}, root=tmp_path)
    assert resumed["status"] == "READY_FOR_EXECUTION"
    repaired = ProductionControl(run_path).snapshot()
    assert {row["shot_id"] for row in repaired["generation_admissions"] if not row.get("invalidated")} == {"S01", "S02"}


def test_status_on_terminal_run_is_read_only(tmp_path: Path):
    run_path = tmp_path / ".control" / "production_run.json"
    run = ProductionControl.create(run_path, mode="SANDBOX", root=tmp_path)
    _write(tmp_path / "asset.bin")
    _write(tmp_path / "bridge.bin", b"bridge")
    run.register_asset("A", "asset.bin")
    run.register_continuity("S01-S02", from_shot="S01", to_shot="S02", evidence_path="bridge.bin")
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    run.admit_generation("S01", {"model": "test"})
    _write(tmp_path / "s01.mp4", b"video")
    run.record_generation("S01", "T1", video_id="v1", artifact_path="s01.mp4")
    run.record_qc("T1", {key: "PASS" for key in ("picture", "motion", "camera", "continuity", "director")})
    run.select_take("S01", "T1")
    _write(tmp_path / "final.mp4", b"final")
    run.record_assembly("final.mp4", ordered_shots=["S01"])
    run.promote_delivery()
    result = route({"goal": "STATUS", "run": str(run_path)}, root=tmp_path)
    assert result["status"] == "READY"
    assert result["stage"] == "DELIVERY_READY"


def test_status_does_not_promote_qc_blocked_to_ready(tmp_path: Path):
    run_path = tmp_path / ".control" / "production_run.json"
    run = ProductionControl.create(run_path, mode="SANDBOX", root=tmp_path)
    _write(tmp_path / "asset.bin")
    _write(tmp_path / "s01.mp4", b"video")
    run.register_asset("A", "asset.bin")
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    run.admit_generation("S01", {"model": "test"})
    run.record_generation("S01", "T1", video_id="v1", artifact_path="s01.mp4")
    run.record_qc("T1", {"picture": "PASS", "motion": "UNKNOWN", "camera": "PASS", "continuity": "PASS", "director": "PASS"})
    result = route({"goal": "STATUS", "run": str(run_path)}, root=tmp_path)
    assert result["status"] == "QC_BLOCKED"
    assert result["stage"] == "QC_BLOCKED"


def test_unknown_execution_outcome_is_recorded_and_blocks_resume(tmp_path: Path):
    plan = _plan(tmp_path, bridge=True)
    first = route({"goal": "PRODUCE", "plan": str(plan)}, root=tmp_path)
    assert first["status"] == "READY_FOR_EXECUTION"
    run_path = tmp_path / ".control" / "production_run.json"
    project = tmp_path / "project"
    project.mkdir()
    (project / "manifest.json").write_text(json.dumps({"status": "UNKNOWN", "shot_id": "S01", "action_id": "a1"}), encoding="utf-8")
    result = route({"goal": "RESUME", "run": str(run_path), "project_dir": str(project)}, root=tmp_path)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "EXECUTION_OUTCOME_UNRESOLVED"
    assert ProductionControl(run_path).snapshot()["execution_outcomes"][0]["status"] == "UNKNOWN"
    blocked_again = route({"goal": "RESUME", "run": str(run_path)}, root=tmp_path)
    assert blocked_again["status"] == "BLOCKED"
    assert blocked_again["reason"] == "EXECUTION_OUTCOME_UNRESOLVED"


def test_conflicting_reingest_with_same_take_id_is_blocked(tmp_path: Path):
    run_path = tmp_path / ".control" / "production_run.json"
    run = ProductionControl.create(run_path, mode="SANDBOX", root=tmp_path)
    _write(tmp_path / "asset.bin")
    run.register_asset("A", "asset.bin")
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    admission = run.admit_generation("S01", {"model": "test"})
    project = tmp_path / "project"
    project.mkdir()
    (project / "clip1.mp4").write_bytes(b"one")
    (project / "clip2.mp4").write_bytes(b"two")
    manifest = {"status": "COMPLETED", "shot_id": "S01", "video_id": "v1", "take_id": "T1", "artifact_path": "clip1.mp4", "request_hash": admission["request_hash"]}
    (project / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    ingest_execution(run_path, project)
    manifest.update({"video_id": "v2", "artifact_path": "clip2.mp4"})
    (project / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(WorkflowError, match="EXECUTION_RECEIPT_CONFLICT"):
        ingest_execution(run_path, project)


def test_production_ingest_requires_same_run_identity(tmp_path: Path):
    plan = _plan(tmp_path, bridge=True)
    first = route({"goal": "PRODUCE", "plan": str(plan)}, root=tmp_path)
    assert first["status"] == "READY_FOR_EXECUTION"
    run_path = tmp_path / ".control" / "production_run.json"
    run_id = ProductionControl(run_path).snapshot()["run_id"]
    project = tmp_path / "project"
    project.mkdir()
    (project / "manifest.json").write_text(json.dumps({
        "run_id": "a-different-run",
        "status": "UNKNOWN",
        "shot_id": "S01",
        "action_id": "a1",
    }), encoding="utf-8")
    with pytest.raises(WorkflowError, match="EXECUTION_RUN_ID_MISMATCH"):
        ingest_execution(run_path, project)
    (project / "manifest.json").write_text(json.dumps({
        "run_id": run_id,
        "status": "UNKNOWN",
        "shot_id": "S01",
        "action_id": "a1",
    }), encoding="utf-8")
    result = ingest_execution(run_path, project)
    assert result["status"] == "BLOCKED"


def test_production_success_ingest_requires_owner_and_action_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    plan = _plan(tmp_path, bridge=True)
    first = route({"goal": "PRODUCE", "plan": str(plan)}, root=tmp_path)
    assert first["status"] == "READY_FOR_EXECUTION"
    run_path = tmp_path / ".control" / "production_run.json"
    run = ProductionControl(run_path)
    run_id = run.snapshot()["run_id"]
    request_hash = run.snapshot()["generation_admissions"][0]["request_hash"]
    project = tmp_path / "project"
    project.mkdir()
    (project / "clip.mp4").write_bytes(b"clip")
    (project / "manifest.json").write_text(json.dumps({
        "run_id": run_id,
        "status": "COMPLETED",
        "shot_id": "S01",
        "video_id": "v1",
        "take_id": "T1",
        "artifact_path": "clip.mp4",
        "request_hash": request_hash,
        "action_id": "action-1",
        "executor_owner": "window-A",
    }), encoding="utf-8")
    monkeypatch.setattr(engine, "_probe_media", lambda path: {"duration_seconds": 1.0, "width": 720, "height": 1280, "fps": 24.0})
    with pytest.raises(WorkflowError, match="EXECUTION_BINDING_REQUIRED"):
        ingest_execution(run_path, project)
    run.assign_execution_owner(owner="window-A", action_id="action-1")
    result = ingest_execution(run_path, project)
    assert result["ingested_shots"] == ["S01"]


def test_production_acceptance_requires_same_action_id(tmp_path: Path):
    run_path = tmp_path / ".control" / "production_run.json"
    run = ProductionControl.create(run_path, run_id="run-123", mode="PRODUCTION", root=tmp_path)
    run.assign_execution_owner(owner="window-A", action_id="action-1")
    project = tmp_path / "project"
    project.mkdir()
    (project / "manifest.json").write_text(json.dumps({
        "run_id": "run-123",
        "status": "UNKNOWN",
        "shot_id": "S01",
        "action_id": "action-1",
    }), encoding="utf-8")
    (project / "acceptance_receipt.json").write_text(json.dumps({
        "run_id": "run-123",
        "action_id": "different-action",
        "status": "PASS",
        "delivery_approved": True,
        "output": "final.mp4",
    }), encoding="utf-8")
    with pytest.raises(WorkflowError, match="ACCEPTANCE_ACTION_ID_MISMATCH"):
        ingest_execution(run_path, project)


def test_production_acceptance_requires_same_execution_owner(tmp_path: Path):
    run_path = tmp_path / ".control" / "production_run.json"
    run = ProductionControl.create(run_path, run_id="run-123", mode="PRODUCTION", root=tmp_path)
    run.assign_execution_owner(owner="window-A", action_id="action-1")
    project = tmp_path / "project"
    project.mkdir()
    (project / "manifest.json").write_text(json.dumps({
        "run_id": "run-123",
        "status": "UNKNOWN",
        "shot_id": "S01",
        "action_id": "action-1",
    }), encoding="utf-8")
    (project / "acceptance_receipt.json").write_text(json.dumps({
        "run_id": "run-123",
        "action_id": "action-1",
        "executor_owner": "window-B",
        "status": "PASS",
        "delivery_approved": True,
        "output": "final.mp4",
    }), encoding="utf-8")
    with pytest.raises(WorkflowError, match="ACCEPTANCE_OWNER_MISMATCH"):
        ingest_execution(run_path, project)


def test_execution_owner_handoff_preserves_run_identity(tmp_path: Path):
    run_path = tmp_path / ".control" / "production_run.json"
    run = ProductionControl.create(run_path, run_id="run-123", mode="PRODUCTION", root=tmp_path)
    assigned = run.assign_execution_owner(owner="window-A", action_id="action-1")
    assert assigned["owner"] == "window-A"
    handed = run.handoff_execution(from_owner="window-A", to_owner="window-B", action_id="action-1", reason="context handoff")
    assert handed["owner"] == "window-B"
    assert handed["handoff_seq"] == 1
    assert ProductionControl(run_path).snapshot()["run_id"] == "run-123"
    with pytest.raises(WorkflowError, match="EXECUTION_HANDOFF_SOURCE_MISMATCH"):
        run.handoff_execution(from_owner="window-A", to_owner="window-C", action_id="action-1")
