from __future__ import annotations

from tools.memory_context import build_memory_context, render_memory_context


def test_memory_context_always_loads_invariants_and_active_lessons():
    result = build_memory_context()
    assert result["payload"]["l0"]["invariants"]
    assert result["payload"]["l1"] == {}
    assert result["payload"]["scope"]["l1_l2_loaded"] is False
    assert "memory/L0_invariants.json" in result["sources"]
    assert "视频王国自动记忆" in render_memory_context(result)


def test_memory_context_loads_project_state_only_on_explicit_match():
    result = build_memory_context("episode_007_virtual_data")
    assert result["payload"]["l1"]["project_id"] == "episode_007_virtual_data"
    assert result["payload"]["scope"]["l1_l2_loaded"] is True
    assert result["payload"]["l2"]
    assert "memory/L1_story_state.json" in result["sources"]
