from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from production_control import ProductionControl, WorkflowError
from production_control.workflow import bootstrap, lock_plan_shots, recover


def _asset(path: Path, payload: bytes = b"x" * 5000) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _plan(root: Path, *, with_bridge: bool = False) -> Path:
    char = root / "assets" / "char.png"
    scene = root / "assets" / "scene.png"
    char_hash = _asset(char)
    scene_hash = _asset(scene, b"y" * 5000)
    bridge = root / "bridges" / "S01-S02.json"
    if with_bridge:
        _asset(bridge, b"bridge")
    data = {
        "project_id": "demo-workflow",
        "production_integration": False,
        "assets": {"characters": [{"asset_id": "CHAR", "reference_path": "assets/char.png", "sha256": char_hash, "status": "APPROVED_REFERENCE_SHEET"}], "scenes": [{"asset_id": "SCENE", "reference_path": "assets/scene.png", "sha256": scene_hash, "status": "APPROVED_REFERENCE_SHEET"}]},
        "shots": [
            {"shot_id": "S01", "action": "look left", "render": {"seconds": 4}, "shot_contract": {"single_action": True, "max_primary_actions": 1}, "continuity_evidence_path": "bridges/S01-S02.json" if with_bridge else None},
            {"shot_id": "S02", "action": "hold", "render": {"seconds": 4}, "shot_contract": {"single_action": True, "max_primary_actions": 1}},
        ],
    }
    path = root / "episode_plan.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_bootstrap_blocks_without_continuity_proof(tmp_path: Path):
    plan = _plan(tmp_path)
    result = bootstrap(plan, tmp_path / "control" / "run.json", mode="SANDBOX")
    assert result["status"] == "BLOCKED"
    assert result["stage"] == "ASSETS_BLOCKED"
    assert result["next_action"].startswith("repair assets")


def test_bootstrap_ready_then_lock_shots(tmp_path: Path):
    plan = _plan(tmp_path, with_bridge=True)
    run_path = tmp_path / "control" / "run.json"
    result = bootstrap(plan, run_path, mode="SANDBOX")
    assert result["status"] == "READY"
    locked = lock_plan_shots(run_path, plan)
    assert locked["locked_shots"] == ["S01", "S02"]
    assert recover(run_path)["status"] == "SHOT_LOCKED"


def test_recovery_fails_closed_on_tampered_event_chain(tmp_path: Path):
    plan = _plan(tmp_path, with_bridge=True)
    run_path = tmp_path / "control" / "run.json"
    bootstrap(plan, run_path, mode="SANDBOX")
    payload = json.loads(run_path.read_text(encoding="utf-8"))
    payload["events"][0]["data"]["tampered"] = True
    run_path.write_text(json.dumps(payload), encoding="utf-8")
    result = recover(run_path)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "EVENT_CHAIN_INVALID"


def test_lock_never_bypasses_blocked_gate(tmp_path: Path):
    plan = _plan(tmp_path)
    run_path = tmp_path / "control" / "run.json"
    bootstrap(plan, run_path, mode="SANDBOX")
    with pytest.raises(WorkflowError, match="ASSET_GATE_NOT_READY"):
        lock_plan_shots(run_path, plan)


def test_production_bootstrap_preflights_before_creating_run(tmp_path: Path):
    plan = _plan(tmp_path)
    run_path = tmp_path / "control" / "run.json"
    result = bootstrap(plan, run_path, mode="PRODUCTION")
    assert result["status"] == "BLOCKED"
    assert result["run"] is None
    assert not run_path.exists()
    receipt = Path(result["preflight_receipt"])
    assert receipt.is_file()
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert any(row["reason"] == "CONTINUITY_EVIDENCE_MISSING" for row in payload["errors"])


def test_changed_admission_requires_explicit_request_revision(tmp_path: Path):
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="SANDBOX")
    _asset(tmp_path / "run" / "asset.bin")
    run.register_asset("A", "asset.bin")
    run.evaluate_asset_gate()
    run.lock_shot("S01", {"duration_seconds": {"min": 1, "max": 2}, "primary_action": "hold"})
    first = run.admit_generation("S01", {"model": "test", "prompt": "A"})
    with pytest.raises(WorkflowError, match="GENERATION_ALREADY_ADMITTED"):
        run.admit_generation("S01", {"model": "test", "prompt": "B"})
    revised = run.admit_generation(
        "S01",
        {"model": "test", "prompt": "B"},
        revision_of=first["request_hash"],
    )
    assert revised["request_hash"] != first["request_hash"]
    assert revised["supersedes_request_hash"] == first["request_hash"]
    snapshot = run.snapshot()
    assert snapshot["generation_admissions"][0]["superseded_by_request_hash"] == revised["request_hash"]
