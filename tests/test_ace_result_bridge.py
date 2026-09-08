from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "emit_ace_result_bridge.py"
SPEC = importlib.util.spec_from_file_location("emit_ace_result_bridge", MODULE_PATH)
assert SPEC and SPEC.loader
BRIDGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BRIDGE)


def _record(root: Path) -> Path:
    proof = root / "proof.json"
    proof.write_text('{"ok":true}\n', encoding="utf-8")
    digest = hashlib.sha256(proof.read_bytes()).hexdigest()
    record = root / "decision.json"
    record.write_text(json.dumps({
        "record_id": "ep1-s01", "episode_id": "ep1", "scope_ref": "S01", "source_realm": "CONTROLLED_ORIGIN", "admission": {"status": "NOT_REQUIRED"}, "lifecycle": "RESULT_RECORDED",
        "evidence": [{"evidence_id": "proof", "kind": "media_integrity", "path": "proof.json", "sha256": digest}],
        "opinions": [{"opinion_id": "final", "role": "final_decider", "model": "gpt-5.6-terra", "verdict": "SUPPORT", "evidence_refs": ["proof"], "findings": ["checked"], "uncertainties": []}],
        "decision": {"verdict": "REWORK", "decider_opinion_id": "final", "basis_evidence_refs": ["proof"], "reason": "repair", "repair_scope": "S01", "expected_gain": "continuity", "cost_class": "low"},
        "result": {"status": "COMPLETED", "observed_evidence_refs": ["proof"], "summary": "observed"}
    }), encoding="utf-8")
    return record


def test_bridge_emits_once_and_never_marks_delivery_approved(tmp_path: Path) -> None:
    record = _record(tmp_path)
    outbox = tmp_path / "outbox.jsonl"
    first = BRIDGE.emit(record, tmp_path, outbox, "VK-AUTO-1")
    second = BRIDGE.emit(record, tmp_path, outbox, "VK-AUTO-1")
    assert first["status"] == "EMITTED"
    assert second["status"] == "ALREADY_EMITTED"
    assert first["delivery_approved"] is False
    assert len(outbox.read_text(encoding="utf-8").splitlines()) == 1
