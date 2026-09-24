import json
from pathlib import Path

from tools.promotion_gate import run


def _record(**overrides):
    value = {
        "status": "READY_FOR_GATE",
        "evolution_id": "EV-test-001",
        "capability": "镜头动作遵循",
        "source_evidence_complete": True,
        "execution_authorized": False,
        "production_integration": False,
        "baseline_metrics": {"success_rate": 0.5},
        "after_metrics": {"success_rate": 0.75},
        "change": "把镜头动作合同接入生成前门禁",
        "tests": ["pytest tests/test_production_generation_gate.py"],
        "tests_passed": True,
        "evaluation": {"status": "IMPROVED"},
        "painful_review": {
            "observed_problem": "旧合同只锁画面，动作没有进入生成输入",
            "cost": "返工三镜并浪费一次生成额度",
            "blast_radius": "同一模板的七个镜头",
            "counterfactual": "不拦截会继续生成活照片式成片",
            "recurrence_risk": "旧模板仍可能被复制",
            "reusable_lesson": "镜头动作必须成为可验证合同字段",
            "retain": True,
        },
        "created_at": "2026-09-25T00:00:00Z",
    }
    value.update(overrides)
    return value


def test_gate_promotes_only_complete_evidence(tmp_path: Path):
    queue = tmp_path / "candidates.jsonl"
    queue.write_text(json.dumps(_record(), ensure_ascii=False) + "\n", encoding="utf-8")
    result = run(
        execute=True,
        limit=5,
        queue_path=queue,
        receipts_dir=tmp_path / "receipts",
        ledger_path=tmp_path / "ledger.jsonl",
        capabilities_path=tmp_path / "capabilities.json",
    )
    assert result["decisions"][0]["decision"] == "PROMOTE"
    assert result["production_integration"] is False
    assert (tmp_path / "ledger.jsonl").exists()
    assert json.loads((tmp_path / "capabilities.json").read_text(encoding="utf-8"))["capabilities"]


def test_gate_keeps_incomplete_candidate_in_review(tmp_path: Path):
    queue = tmp_path / "candidates.jsonl"
    queue.write_text(json.dumps(_record(source_evidence_complete=False), ensure_ascii=False) + "\n", encoding="utf-8")
    result = run(
        execute=True,
        queue_path=queue,
        receipts_dir=tmp_path / "receipts",
        ledger_path=tmp_path / "ledger.jsonl",
        capabilities_path=tmp_path / "capabilities.json",
    )
    assert result["decisions"][0]["decision"] == "REVIEW_REQUIRED"
    assert not (tmp_path / "ledger.jsonl").exists()


def test_gate_caps_batch_and_keeps_production_closed(tmp_path: Path):
    queue = tmp_path / "candidates.jsonl"
    rows = [_record(evolution_id=f"EV-test-{index:03d}") for index in range(7)]
    queue.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    result = run(execute=True, limit=5, queue_path=queue, receipts_dir=tmp_path / "receipts")
    assert result["selected"] == 5
    assert result["remaining_ready"] == 2
    assert result["execution_authorized"] is False
    assert result["production_integration"] is False
