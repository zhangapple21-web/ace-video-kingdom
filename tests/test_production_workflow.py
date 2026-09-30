from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import production_control.engine as engine
from production_control import ProductionControl, WorkflowError
from production_control.workflow import bootstrap, lock_plan_shots, normalize_scope, preflight_plan, recover
from tools.medium_lock import character_performance_lock


def _asset(path: Path, payload: bytes = b"x" * 5000) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _fake_production_frames(artifact: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    first = output_dir / "first.png"
    last = output_dir / "last.png"
    first.write_bytes(b"first-frame")
    last.write_bytes(b"last-frame")
    return {
        "tool": "test-ffmpeg",
        "tool_path": "test-ffmpeg",
        "tool_version": "test",
        "first_frame": {"path": str(first), "sha256": hashlib.sha256(first.read_bytes()).hexdigest()},
        "last_frame": {"path": str(last), "sha256": hashlib.sha256(last.read_bytes()).hexdigest()},
    }


def _plan(root: Path, *, with_bridge: bool = False) -> Path:
    char = root / "assets" / "char.png"
    scene = root / "assets" / "scene.png"
    char_hash = _asset(char)
    scene_hash = _asset(scene, b"y" * 5000)
    bridge = root / "bridges" / "S01-S02.json"
    if with_bridge:
        bridge.parent.mkdir(parents=True, exist_ok=True)
        bridge.write_text(
            json.dumps({"status": "PASS", "from_shot": "S01", "to_shot": "S02"}),
            encoding="utf-8",
        )
    data = {
        "project_id": "demo-workflow",
        "production_integration": False,
        "medium_lock": character_performance_lock(),
        "assets": {"characters": [{"asset_id": "CHAR", "reference_path": "assets/char.png", "sha256": char_hash, "status": "APPROVED_REFERENCE_SHEET"}], "scenes": [{"asset_id": "SCENE", "reference_path": "assets/scene.png", "sha256": scene_hash, "status": "APPROVED_REFERENCE_SHEET"}]},
        "shots": [
            {"shot_id": "S01", "action": "look left", "generation_allowed": True, "five_gate_receipt": {"status": "PASS"}, "render": {"seconds": 4}, "shot_contract": {"single_action": True, "max_primary_actions": 1}, "continuity_evidence_path": "bridges/S01-S02.json" if with_bridge else None},
            {"shot_id": "S02", "action": "hold", "generation_allowed": True, "five_gate_receipt": {"status": "PASS"}, "render": {"seconds": 4}, "shot_contract": {"single_action": True, "max_primary_actions": 1}},
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


def test_preflight_scope_is_normalized_and_limits_continuity_edges(tmp_path: Path):
    plan_path = _plan(tmp_path, with_bridge=True)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["shots"].append({"shot_id": "S03", "action": "hold"})
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    scope = normalize_scope(plan, ["S01", "S02"])
    result = preflight_plan(plan_path, mode="SANDBOX", scope=scope)
    assert result["scope"] == scope
    assert result["continuity"] == [{"from_shot": "S01", "to_shot": "S02", "evidence_path": "bridges/S01-S02.json"}]


def test_production_staged_bootstrap_allows_first_shot_without_later_bridge(tmp_path: Path):
    plan_path = _plan(tmp_path)
    run_path = tmp_path / "control" / "run.json"
    result = bootstrap(plan_path, run_path, mode="PRODUCTION", scope=["S01"])
    assert result["status"] == "READY"
    snapshot = ProductionControl(run_path).snapshot()
    assert snapshot["scope"]["shot_ids"] == ["S01"]
    assert snapshot["scope"]["active_shot_id"] == "S01"
    assert snapshot["plan_shot_ids"] == ["S01", "S02"]
    assert snapshot["continuity"] == {}
    assert snapshot["events"][0]["event"] == "SCOPE_BOUND"
    assert ProductionControl(run_path).verify_event_chain()["status"] == "PASS"
    locked = lock_plan_shots(run_path, plan_path)
    assert locked["locked_shots"] == ["S01"]
    assert locked["scope"] == snapshot["scope"]
    assert locked["active_shot_id"] == "S01"
    assert locked["plan_shot_ids"] == ["S01", "S02"]


def test_scope_expansion_registers_next_edge_only_when_explicitly_locked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        engine,
        "_probe_media",
        lambda path: {"duration_seconds": 4.0, "width": 720, "height": 1280, "fps": 24.0},
    )
    monkeypatch.setattr(engine, "_extract_frames", _fake_production_frames)
    plan_path = _plan(tmp_path, with_bridge=True)
    run_path = tmp_path / "control" / "run.json"
    assert bootstrap(plan_path, run_path, mode="PRODUCTION", scope=["S01"])["status"] == "READY"
    run = ProductionControl(run_path)
    lock_plan_shots(run_path, plan_path)
    admission = run.admit_generation("S01", {"model": "test"})
    _asset(tmp_path / "s01.mp4", b"s01-media")
    run.record_generation(
        "S01",
        "S01_T1",
        video_id="v-s01",
        artifact_path="s01.mp4",
        metadata={"request_hash": admission["request_hash"]},
    )
    run.record_qc("S01_T1", {key: "PASS" for key in ("picture", "motion", "camera", "continuity", "director")})
    run.select_take("S01", "S01_T1")
    expanded = run.expand_scope("S02")
    assert expanded["shot_ids"] == ["S01", "S02"]
    assert "S01->S02" not in run.snapshot()["continuity"]
    locked = lock_plan_shots(run_path, plan_path)
    assert locked["locked_shots"] == ["S01", "S02"]
    assert "S01->S02" in run.snapshot()["continuity"]
    run.advance_active_shot("S02")
    assert run.snapshot()["scope"]["active_shot_id"] == "S02"
    assert admission["shot_id"] == "S01"


def test_lock_plan_shots_respects_run_scope(tmp_path: Path):
    plan = _plan(tmp_path, with_bridge=True)
    run_path = tmp_path / "control" / "run.json"
    bootstrap(plan, run_path, mode="SANDBOX", scope=["S01"])
    result = lock_plan_shots(run_path, plan)
    assert result["locked_shots"] == ["S01"]


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
