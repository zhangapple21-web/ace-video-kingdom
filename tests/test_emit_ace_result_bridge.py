import json
from pathlib import Path

from tools.emit_ace_result_bridge import emit


def test_emit_can_relay_hash_bound_bundle_to_explicit_ace_root(tmp_path: Path):
    source_root = tmp_path / "video-kingdom"
    ace_root = tmp_path / "ace-core"
    record = source_root / "research" / "decision_records" / "result.json"
    evidence = source_root / "research" / "evidence.json"
    candidate = source_root / "media" / "shot.mp4"
    contract = source_root / "episodes" / "contract.json"
    for path, payload in ((evidence, b"evidence"), (candidate, b"mp4"), (contract, b"contract")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    import hashlib

    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({
        "record_id": "ep-s01", "episode_id": "ep", "scope_ref": "S01",
        "source_realm": "CONTROLLED_ORIGIN",
        "admission": {"status": "NOT_REQUIRED", "candidate_path": "media/shot.mp4", "accepting_contract_ref": "episodes/contract.json"},
        "lifecycle": "RESULT_RECORDED",
        "evidence": [{"evidence_id": "v", "kind": "visual_review", "path": "research/evidence.json", "sha256": digest(evidence)}],
        "opinions": [{"opinion_id": "final", "role": "final_decider", "model": "test", "verdict": "REWORK", "evidence_refs": ["v"], "findings": ["repair"], "uncertainties": []}],
        "decision": {"verdict": "REWORK", "decider_opinion_id": "final", "basis_evidence_refs": ["v"], "reason": "repair", "repair_scope": "shot", "expected_gain": "continuity", "cost_class": "bounded"},
        "result": {"status": "COMPLETED", "observed_evidence_refs": ["v"], "summary": "done"},
    }), encoding="utf-8")

    result = emit(record, source_root, source_root / "research" / "ace_result_outbox.v1.jsonl", ace_root=ace_root)
    assert result["ace_relay"]["status"] == "RELAYED"
    assert (ace_root / "research" / "decision_records" / "result.json").read_bytes() == record.read_bytes()
    assert (ace_root / "research" / "evidence.json").read_bytes() == evidence.read_bytes()
    assert (ace_root / "media" / "shot.mp4").read_bytes() == candidate.read_bytes()
    assert (ace_root / "episodes" / "contract.json").read_bytes() == contract.read_bytes()
    ace_line = json.loads((ace_root / "research" / "ace_result_outbox.v1.jsonl").read_text(encoding="utf-8").strip())
    assert ace_line["bridge_id"] == result["bridge_id"]
    assert ace_line["delivery_approved"] is False

    again = emit(record, source_root, source_root / "research" / "ace_result_outbox.v1.jsonl", ace_root=ace_root)
    assert again["status"] == "ALREADY_EMITTED"
    assert again["ace_relay"]["status"] == "ALREADY_RELAYED"
