import json
import hashlib
from pathlib import Path

from tools.drain_task_wall import drain


def test_drain_closes_research_and_triages_repairs(tmp_path: Path):
    queue = tmp_path / "queue.json"
    receipts = tmp_path / "receipts.jsonl"
    runs = tmp_path / "runs"
    runs.mkdir()
    run = runs / "EL-test.json"
    run.write_text(json.dumps({"schema": "video_kingdom.external_learning_run.v1", "records": []}), encoding="utf-8")
    queue.write_text(json.dumps({"cards": [
        {"task_id": "learn-1", "task_type": "EXTERNAL_LEARNING", "status": "HANDOFF_READY", "created_at": "2026-01-01", "evidence": {"learning_run": str(run)}},
        {"task_id": "repair-1", "task_type": "CONTINUITY_REPAIR", "status": "HANDOFF_READY", "created_at": "2026-01-02", "evidence": {"warning_count": 2}},
        {"task_id": "media-1", "task_type": "RESUME_MEDIA_WORK", "status": "HANDOFF_READY", "created_at": "2026-01-03"},
    ]}), encoding="utf-8")
    result = drain(execute=True, limit=5, queue_path=queue, receipt_path=receipts, learning_runs_dir=runs)
    assert result["selected"] == 2
    saved = json.loads(queue.read_text(encoding="utf-8"))
    statuses = {c["task_id"]: c["status"] for c in saved["cards"]}
    assert statuses == {"learn-1": "COMPLETED", "repair-1": "REVIEW_REQUIRED", "media-1": "HANDOFF_READY"}
    assert len(receipts.read_text(encoding="utf-8").splitlines()) == 2


def test_drain_is_idempotent_after_status_change(tmp_path: Path):
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({"cards": [{"task_id": "learn-1", "task_type": "EXTERNAL_LEARNING", "status": "COMPLETED"}]}), encoding="utf-8")
    result = drain(execute=True, limit=5, queue_path=queue, receipt_path=tmp_path / "receipts.jsonl")
    assert result["selected"] == 0


def test_unlinked_learning_card_cannot_consume_latest_run(tmp_path: Path):
    queue = tmp_path / "queue.json"
    receipts = tmp_path / "receipts.jsonl"
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "EL-latest.json").write_text(json.dumps({"schema": "video_kingdom.external_learning_run.v1", "records": []}), encoding="utf-8")
    queue.write_text(json.dumps({"cards": [{"task_id": "learn-1", "task_type": "EXTERNAL_LEARNING", "status": "HANDOFF_READY", "created_at": "2026-01-01"}]}), encoding="utf-8")
    result = drain(execute=True, limit=5, queue_path=queue, receipt_path=receipts, learning_runs_dir=runs)
    assert result["actions"][0]["new_status"] == "REVIEW_REQUIRED"


def test_continuity_repair_writes_replay_and_ab_plan_only_with_complete_evidence(tmp_path: Path):
    source = tmp_path / "failure-source.json"
    source.write_text('{"warning":"hand drift"}\n', encoding="utf-8")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    queue = tmp_path / "queue.json"
    receipts = tmp_path / "receipts.jsonl"
    failure_replay = tmp_path / "failure.jsonl"
    experiments = tmp_path / "experiments.jsonl"
    card = {
        "task_id": "repair-complete",
        "task_type": "CONTINUITY_REPAIR",
        "status": "HANDOFF_READY",
        "created_at": "2026-01-02",
        "evidence": {
            "warning_count": 1,
            "warning_digest": "a" * 64,
            "linkage": {"contract_status": "LINKED", "linked_artifacts": 1, "hash_verified_artifacts": 1, "previous_cut_audit_status": "AVAILABLE"},
            "source_refs": [{"path": source.name, "sha256": source_hash}],
            "failure_replay": {
                "problem": "hand continuity warning repeats",
                "judgment": "the shot state was not inherited",
                "action": "bind the approved shot state",
                "result": "baseline captured for repair",
                "why": "the old contract omitted the state edge",
                "reuse_when": "the same state inheritance warning recurs",
                "cost": "one isolated review cycle",
                "blast_radius": "one continuity repair card",
                "counterfactual": "without the repair the next shot would drift",
                "recurrence_risk": "medium until the gate remains enforced",
            },
            "ab_experiment": {
                "hypothesis": "approved state binding lowers continuity warnings",
                "baseline_metrics": {"failure_rate": 0.5},
                "change_plan": "add approved state edge to the shot contract",
                "test_plan": ["run the isolated fixture twice"],
                "success_criteria": "failure_rate decreases without regression",
                "rollback_ref": "git:known-good-contract",
            },
        },
    }
    queue.write_text(json.dumps({"cards": [card]}, ensure_ascii=False), encoding="utf-8")
    result = drain(
        execute=True,
        limit=5,
        queue_path=queue,
        receipt_path=receipts,
        source_root=tmp_path,
        failure_replay_path=failure_replay,
        experiment_path=experiments,
    )
    assert result["actions"][0]["new_status"] == "AUTO_TRIAGED"
    assert failure_replay.exists()
    assert experiments.exists()
