from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from production_control import ProductionControl, WorkflowError


def _production_run(tmp_path: Path, *, contract: dict) -> ProductionControl:
    run = ProductionControl.create(tmp_path / "run" / "state.json", mode="PRODUCTION")
    asset = tmp_path / "run" / "asset.bin"
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(b"a" * 5000)
    run.register_asset("SCENE", "asset.bin", expected_sha256=hashlib.sha256(asset.read_bytes()).hexdigest())
    assert run.evaluate_asset_gate()["status"] == "READY"
    run.lock_shot("S01", {
        "duration_seconds": {"min": 1, "max": 2},
        "primary_action": "hold",
        **contract,
    })
    return run


def test_production_admission_requires_explicit_generation_permission(tmp_path: Path):
    run = _production_run(tmp_path, contract={})

    with pytest.raises(WorkflowError, match="GENERATION_NOT_ALLOWED:S01"):
        run.admit_generation("S01", {"model": "test", "prompt": "hold"})


def test_production_admission_rejects_nonpassing_five_gate(tmp_path: Path):
    run = _production_run(tmp_path, contract={
        "generation_allowed": True,
        "five_gate_receipt": {"status": "BLOCKED"},
    })

    with pytest.raises(WorkflowError, match="FIVE_GATE_NOT_READY:S01"):
        run.admit_generation("S01", {"model": "test", "prompt": "hold"})
