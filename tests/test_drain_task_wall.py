import json
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
    assert statuses == {"learn-1": "COMPLETED", "repair-1": "AUTO_TRIAGED", "media-1": "HANDOFF_READY"}
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
