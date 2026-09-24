from __future__ import annotations

from pathlib import Path

from tools.workflow_decision_matrix import (
    build_workflow_policy_receipt,
    evaluate_project_selection,
    evaluate_source_quality,
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
    assert [item["tier"] for item in matrix["budget_tiers"]] == ["T0", "T1", "T2", "T3"]
    assert matrix["source_quality_gate"]["pass_threshold"] == 6
    assert matrix["project_selection_gate"]["pass_threshold"] == 10
    assert matrix["stop_policy"]["block_not_abandon"]
    assert matrix["production_integration"] is False


def test_decision_matrix_receipt_is_rebuildable():
    receipt = build_workflow_policy_receipt(PROJECT_ROOT)
    assert receipt["validation"]["status"] == "PASS"
    assert len(receipt["sha256"]) == 64
    assert receipt["recovery_ladder"][0] == "STOP_AND_PRESERVE_EVIDENCE"
    assert receipt["budget_tiers"][1]["tier"] == "T1"
    assert receipt["source_quality_gate"]["authority"] == "CREATIVE_GO_NO_GO"
    assert receipt["source_quality_assessment"]["status"] == "PENDING"
    assert receipt["project_selection_assessment"]["status"] == "PENDING"


def test_decision_matrix_rejects_missing_stage_contract():
    matrix, _, _ = load_workflow_decision_matrix(PROJECT_ROOT)
    matrix["stages"][0].pop("failure_recovery")
    check = validate_workflow_decision_matrix(matrix)
    assert check["status"] == "FAIL"
    assert "stage_1_missing_failure_recovery" in check["errors"]


def test_source_quality_and_project_selection_are_explicit_for_ready_profile():
    profile = {
        "status": "READY",
        "episode_structure": {
            "opening_hook": "雨夜录音回答问题",
            "conflict": "答案会暴露主角秘密",
            "escalation": "录音开始提前回答",
            "information_change": "主角发现录音来自未来",
            "reversal_or_payoff": "最后一个答案指向她自己",
            "ending_question": "她还要不要继续播放",
            "visual_action": "她反复按下录音键并后退",
        },
        "character_roster": [{"character_id": "C1", "name": "小雨", "goal": "找出录音来源"}],
        "character_signature_system": {"records": [{"signature_action": "握紧录音笔"}]},
        "quality_review": {
            "status": "PASS",
            "source_quality_criteria": {
                key: {"score": 2, "evidence": f"review:{key}"}
                for key in ("hook", "conflict", "character_goal", "escalation", "payoff", "visual_action", "production_fit")
            },
            "project_selection_criteria": {
                key: {"score": 2, "evidence": f"selection:{key}"}
                for key in ("hook", "conflict", "visual_action", "character_memorability", "episode_payload", "continuation", "production_fit")
            },
            "reviewer": "test",
            "evidence_refs": ["test-review.json"],
        },
    }
    matrix, _, _ = load_workflow_decision_matrix(PROJECT_ROOT)
    source = evaluate_source_quality(profile, matrix)
    selection = evaluate_project_selection(source, profile, matrix)
    assert source["status"] == "PASS"
    assert selection["status"] == "PASS"
