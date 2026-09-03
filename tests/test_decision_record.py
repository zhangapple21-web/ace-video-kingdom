from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / "tools" / "validate_decision_record.py"
SPEC = importlib.util.spec_from_file_location("validate_decision_record", MODULE_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def _record(path: Path) -> dict:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "record_id": "ep001-s01-r1", "episode_id": "ep001", "scope_ref": "S01", "source_realm": "CONTROLLED_ORIGIN", "admission": {"status": "NOT_REQUIRED"}, "lifecycle": "RESULT_RECORDED",
        "evidence": [{"evidence_id": "integrity", "kind": "media_integrity", "path": path.name, "sha256": digest}],
        "opinions": [
            {"opinion_id": "director", "role": "director", "model": "gpt-5.5", "verdict": "SUPPORT", "evidence_refs": ["integrity"], "findings": ["bounded"], "uncertainties": []},
            {"opinion_id": "final", "role": "final_decider", "model": "gpt-5.6-terra", "verdict": "SUPPORT", "evidence_refs": ["integrity"], "findings": ["evidence reviewed"], "uncertainties": []}
        ],
        "decision": {"verdict": "PASS", "decider_opinion_id": "final", "basis_evidence_refs": ["integrity"], "reason": "checks pass", "repair_scope": "none", "expected_gain": "none", "cost_class": "none"},
        "result": {"status": "COMPLETED", "observed_evidence_refs": ["integrity"], "summary": "observed"}
    }


def test_hash_bound_decision_record_passes(tmp_path: Path) -> None:
    proof = tmp_path / "proof.json"
    proof.write_text('{"ok":true}\n', encoding="utf-8")
    VALIDATOR.validate(_record(proof), tmp_path)


def test_pass_cannot_ignore_a_blocking_challenge(tmp_path: Path) -> None:
    proof = tmp_path / "proof.json"
    proof.write_text('{"ok":true}\n', encoding="utf-8")
    record = _record(proof)
    record["opinions"].append({"opinion_id": "challenge", "role": "challenger", "model": "grok-4.5", "verdict": "BLOCKED", "evidence_refs": ["integrity"], "findings": ["identity mismatch"], "uncertainties": []})
    with pytest.raises(SystemExit, match="no BLOCKED opinion"):
        VALIDATOR.validate(record, tmp_path)


def test_free_zone_candidate_cannot_enter_a_pass_without_admission(tmp_path: Path) -> None:
    proof = tmp_path / "proof.json"
    proof.write_text('{"ok":true}\n', encoding="utf-8")
    record = _record(proof)
    record["source_realm"] = "FREE_ZONE_CANDIDATE"
    record["admission"] = {"status": "REJECTED"}
    with pytest.raises(SystemExit, match="Free Zone candidate requires accepted hash-bound admission"):
        VALIDATOR.validate(record, tmp_path)
