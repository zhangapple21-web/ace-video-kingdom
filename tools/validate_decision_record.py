"""Validate a hash-bound Video Kingdom Decision Record without calling providers."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _fail(message: str) -> None:
    raise SystemExit(f"Decision Record invalid: {message}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def validate(record: dict, root: Path) -> None:
    required = {"record_id", "episode_id", "scope_ref", "source_realm", "admission", "lifecycle", "evidence", "opinions", "decision", "result"}
    missing = required - set(record)
    if missing:
        _fail("missing root fields: " + ", ".join(sorted(missing)))
    if record["lifecycle"] not in {"DRAFT", "DECIDED", "RESULT_RECORDED"}:
        _fail("unknown lifecycle")
    realm = record["source_realm"]
    admission = record["admission"]
    if realm not in {"CONTROLLED_ORIGIN", "FREE_ZONE_CANDIDATE"} or not isinstance(admission, dict):
        _fail("source_realm or admission is invalid")
    if realm == "CONTROLLED_ORIGIN" and admission.get("status") != "NOT_REQUIRED":
        _fail("controlled origin requires NOT_REQUIRED admission")
    if realm == "FREE_ZONE_CANDIDATE":
        required_admission = {"status", "candidate_path", "candidate_sha256", "accepting_contract_ref"}
        if admission.get("status") != "ACCEPTED" or required_admission - set(admission):
            _fail("Free Zone candidate requires accepted hash-bound admission")
    if not isinstance(record["evidence"], list) or not record["evidence"]:
        _fail("evidence must be a non-empty list")

    evidence_ids: set[str] = set()
    evidence_kinds: set[str] = set()
    for item in record["evidence"]:
        fields = {"evidence_id", "kind", "path", "sha256"}
        if not isinstance(item, dict) or fields - set(item):
            _fail("every evidence item needs evidence_id, kind, path, sha256")
        evidence_id = item["evidence_id"]
        if not isinstance(evidence_id, str) or evidence_id in evidence_ids:
            _fail("evidence_id values must be unique strings")
        path = (root / item["path"]).resolve()
        if not _inside(root, path) or not path.is_file():
            _fail(f"evidence path is absent or outside root: {item['path']}")
        if _sha256(path) != item["sha256"]:
            _fail(f"evidence hash mismatch: {evidence_id}")
        evidence_ids.add(evidence_id)
        evidence_kinds.add(str(item["kind"]))

    opinions = record["opinions"]
    if not isinstance(opinions, list) or not opinions:
        _fail("opinions must be a non-empty list")
    opinion_ids: set[str] = set()
    blocked = False
    for opinion in opinions:
        required_opinion = {"opinion_id", "role", "model", "verdict", "evidence_refs", "findings", "uncertainties"}
        if not isinstance(opinion, dict) or required_opinion - set(opinion):
            _fail("opinion fields are incomplete")
        if opinion["opinion_id"] in opinion_ids:
            _fail("opinion_id values must be unique")
        if opinion["role"] not in {"utility", "director", "challenger", "comparator", "final_decider"}:
            _fail("unknown opinion role")
        if opinion["verdict"] not in {"SUPPORT", "REWORK", "BLOCKED", "UNKNOWN"}:
            _fail("unknown opinion verdict")
        refs = opinion["evidence_refs"]
        if not isinstance(refs, list) or not refs or not set(refs).issubset(evidence_ids):
            _fail("opinion evidence_refs must resolve to evidence")
        opinion_ids.add(opinion["opinion_id"])
        blocked = blocked or opinion["verdict"] == "BLOCKED"

    decision = record["decision"]
    decision_fields = {"verdict", "decider_opinion_id", "basis_evidence_refs", "reason", "repair_scope", "expected_gain", "cost_class"}
    if not isinstance(decision, dict) or decision_fields - set(decision):
        _fail("decision fields are incomplete")
    if decision["verdict"] not in {"PASS", "REWORK", "BLOCKED", "CONDITIONAL"}:
        _fail("unknown decision verdict")
    if decision["decider_opinion_id"] not in opinion_ids:
        _fail("decision decider_opinion_id is unknown")
    decider = next(item for item in opinions if item["opinion_id"] == decision["decider_opinion_id"])
    basis = decision["basis_evidence_refs"]
    if not isinstance(basis, list) or not basis or not set(basis).issubset(evidence_ids):
        _fail("decision basis_evidence_refs must resolve to evidence")
    if decider["role"] != "final_decider" or not set(decider["evidence_refs"]).intersection(basis):
        _fail("decision must cite a final_decider opinion grounded in decision evidence")
    if decision["verdict"] == "PASS":
        if blocked or not evidence_kinds.intersection({"media_integrity", "visual_review", "subtitle_receipt"}):
            _fail("PASS requires media evidence and no BLOCKED opinion")
    if decision["verdict"] == "PASS" and realm == "FREE_ZONE_CANDIDATE" and admission.get("status") != "ACCEPTED":
        _fail("PASS cannot use an unadmitted Free Zone candidate")
    if decision["verdict"] == "REWORK" and (not decision["repair_scope"] or not decision["expected_gain"]):
        _fail("REWORK requires bounded repair_scope and expected_gain")

    result = record["result"]
    if not isinstance(result, dict) or {"status", "observed_evidence_refs", "summary"} - set(result):
        _fail("result fields are incomplete")
    if result["status"] not in {"NOT_EXECUTED", "COMPLETED", "FAILED", "SUPERSEDED"}:
        _fail("unknown result status")
    observed = result["observed_evidence_refs"]
    if not isinstance(observed, list) or not set(observed).issubset(evidence_ids):
        _fail("result observed_evidence_refs must resolve to evidence")
    if record["lifecycle"] == "RESULT_RECORDED" and not observed:
        _fail("RESULT_RECORDED requires observed evidence")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Decision Record invalid: cannot read JSON: {exc}") from exc
    validate(record, args.root.resolve())
    print(f"DECISION_RECORD_VALID record_id={record['record_id']} lifecycle={record['lifecycle']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
