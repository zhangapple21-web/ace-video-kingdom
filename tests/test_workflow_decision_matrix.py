from __future__ import annotations

from pathlib import Path

from tools.workflow_decision_matrix import (
    build_workflow_policy_receipt,
    load_workflow_decision_matrix,
    validate_workflow_decision_matrix,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_decision_matrix_covers_all_seven_stages_and_budget_policy():
    matrix, check, _ = load_workflow_decision_matrix(PROJECT_ROOT)
    assert check["status"] == "PASS"
    assert matrix["stage_order"] == [1, 2, 3, 4, 5, 6, 7]
    assert len(matrix["stages"]) == 7
    assert [item["rank"] for item in matrix["budget_priority_order"]] == [1, 2, 3, 4, 5, 6]
    assert matrix["production_integration"] is False


def test_decision_matrix_receipt_is_rebuildable():
    receipt = build_workflow_policy_receipt(PROJECT_ROOT)
    assert receipt["validation"]["status"] == "PASS"
    assert len(receipt["sha256"]) == 64
    assert receipt["recovery_ladder"][0] == "STOP_AND_PRESERVE_EVIDENCE"


def test_decision_matrix_rejects_missing_stage_contract():
    matrix, _, _ = load_workflow_decision_matrix(PROJECT_ROOT)
    matrix["stages"][0].pop("failure_recovery")
    check = validate_workflow_decision_matrix(matrix)
    assert check["status"] == "FAIL"
    assert "stage_1_missing_failure_recovery" in check["errors"]
