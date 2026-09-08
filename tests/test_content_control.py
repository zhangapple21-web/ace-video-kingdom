from __future__ import annotations

import pytest

from tools.content_control import (
    apply_content_transition,
    build_post_diagnostics,
    evaluate_content_feasibility,
    initial_content_control,
    transition_content_state,
)
from tools.run_idea_pipeline import _compile


def test_compiler_emits_dynamic_plan_and_ordered_beat_mapping(tmp_path):
    plan = _compile("程序员深夜发现代码里的求救信息", tmp_path, "dynamic", target_seconds=30)
    dynamic = plan["dynamic_content_plan"]
    assert dynamic["episode_plan_version"] == "v1"
    assert dynamic["target_seconds"] == 30
    assert dynamic["pacing_profile"]["dialogue"]["role"] == "diagnostic"
    assert len(dynamic["beats"]) == len(plan["shots"]) == 6
    assert all(beat["mapped_shots"] for beat in dynamic["beats"])
    assert plan["content_control"]["content_state"] == "R0"
    assert plan["content_control"]["tech_route"] == "NORMAL"


def test_ratio_or_duration_alone_never_triggers_degradation():
    dynamic = {"acceptable_duration_range": [92, 108]}
    result = evaluate_content_feasibility(dynamic, actual_duration=130)
    assert result["verdict"] == "CONTENT_VALID"
    result = evaluate_content_feasibility(dynamic, actual_duration=130, repeated_information=True)
    assert result["verdict"] == "CONTENT_DEGRADED"


def test_technical_and_provider_failures_do_not_change_content_state():
    control = initial_content_control()
    diagnostic = build_post_diagnostics({"acceptable_duration_range": [0, 100]}, failure_class="PROVIDER_FAILURE")
    assert diagnostic["classification"] == "PROVIDER_FAILURE"
    assert control["content_state"] == "R0"
    # The provider receipt is diagnostic only; no automatic content
    # transition is performed.
    assert control["lineage"] == []


def test_content_degradation_is_monotonic_and_records_lineage():
    control = initial_content_control()
    transition_content_state(
        control,
        "R1",
        reason="duplicate line exceeds measured budget",
        reason_code="REDUNDANT_DIALOGUE",
        changed_items=["dialogue:S02A"],
        preserved_beats=["BEAT-01", "BEAT-02"],
        removed_items=["line:2b"],
        impact="no_core_narrative_loss",
    )
    assert control["content_state"] == "R1"
    assert control["lineage"][0]["from"] == "R0"
    with pytest.raises(ValueError):
        transition_content_state(control, "R0", reason="rollback", reason_code="REDUNDANT_DIALOGUE")
    with pytest.raises(ValueError):
        transition_content_state(control, "R2", reason="provider error", reason_code="REDUNDANT_SHOT", failure_class="PROVIDER_FAILURE")


def test_r5_is_terminal_and_requires_core_unsatisfiable_reason():
    control = initial_content_control()
    transition_content_state(
        control,
        "R5",
        reason="core causal chain cannot fit or survive the plan",
        reason_code="NARRATIVE_CORE_UNSATISFIABLE",
    )
    assert control["terminal"] is True
    assert control["terminal_reason"] == "REWRITE_REQUIRED"


def test_transition_state_is_propagated_to_shots(tmp_path):
    plan = _compile("测试一个记录冲突的故事", tmp_path, "propagate", target_seconds=30)
    apply_content_transition(
        plan,
        "R1",
        reason="repeated information is removable",
        reason_code="REDUNDANT_DIALOGUE",
        preserved_beats=["BEAT-01"],
    )
    assert all(shot["content_state"] == "R1" for shot in plan["shots"])
    assert all(shot["content_lineage_ref"] == "content_control.v1.json" for shot in plan["shots"])
