import json
import time
from pathlib import Path

from production_control import (
    infer_task_requirements,
    load_provider_health_snapshot,
    route_model_demand,
    select_fallback_labor,
)


ROOT = Path(__file__).parents[1]
REGISTRY = ROOT / "research" / "model_capability_registry.v1.json"


def test_natural_language_is_compiled_to_capabilities_without_a_model_name():
    requirements = infer_task_requirements("请分析 Episode 008 整个制作链，找出最大结构性风险")

    assert requirements["task_class"] == "DIRECTOR"
    assert requirements["required_capabilities"] == ["reasoning", "planning", "long_context"]
    assert "gpt-6-astra" not in json.dumps(requirements, ensure_ascii=False)


def test_utility_poc_selects_verified_low_cost_labor_automatically():
    receipt = route_model_demand("把这些文件批量整理、归档并生成哈希清单")

    assert receipt["status"] == "ROUTED"
    assert receipt["task_class"] == "UTILITY"
    assert receipt["selected_labor"]["id"] == "zhipu:glm-4-flash"
    assert receipt["production_integration"] is False


def test_provider_health_snapshot_can_remove_a_candidate_before_execution():
    receipt = route_model_demand(
        "把这些文件批量整理、归档并生成哈希清单",
        health_snapshot={"zhipu": {"status": "OFFLINE", "health_score": 0}},
    )

    assert receipt["status"] == "BLOCKED"
    glm = next(row for row in receipt["blocked_candidates"] if row["id"] == "zhipu:glm-4-flash")
    assert "PROVIDER_UNHEALTHY" in glm["reasons"]


def test_complex_local_route_does_not_promote_remote_astra_or_unproven_terra():
    receipt = route_model_demand(
        "新项目策划、复杂制作流程和 3D 预演，请做导演级长链规划",
        scope="current_control_plane",
    )

    assert receipt["status"] == "BLOCKED"
    assert receipt["selected_labor"] is None
    blocked = {row["id"]: row["reasons"] for row in receipt["blocked_candidates"]}
    assert "shenwen:gpt-6-astra" in blocked
    assert any(reason.startswith("SCOPE_NOT_ELIGIBLE") for reason in blocked["shenwen:gpt-6-astra"])
    assert not any(reason.startswith("CAPABILITY_NOT_PROVEN") for reason in blocked["shenwen:gpt-6-astra"])


def test_vision_task_fails_closed_instead_of_becoming_text_only():
    receipt = route_model_demand("请看这张图片，判断人物身份和画面连续性", scope="current_control_plane")

    assert receipt["task_class"] == "VISION"
    assert "vision" in receipt["required_capabilities"]
    assert receipt["status"] == "BLOCKED"
    assert receipt["reason"] == "NO_ELIGIBLE_LABOR_FOR_VERIFIED_CAPABILITIES"


def test_explicit_override_is_only_an_override_and_never_a_silent_fallback():
    receipt = route_model_demand(
        "分析这个项目的整体结构",
        model_override="gpt-6-astra",
        scope="current_control_plane",
    )

    assert receipt["status"] == "BLOCKED"
    assert receipt["reason"] == "MODEL_OVERRIDE_UNAVAILABLE_OR_UNPROVEN"
    assert receipt["model_override"] == "gpt-6-astra"


def test_explicit_natural_language_astra_override_is_preserved_and_fail_closed():
    receipt = route_model_demand("这次用 Astra 分析整个项目结构")

    assert receipt["status"] == "BLOCKED"
    assert receipt["reason"] == "MODEL_OVERRIDE_UNAVAILABLE_OR_UNPROVEN"
    assert receipt["model_override"] == "astra"


def test_scoring_can_select_astra_only_when_a_separate_fixture_proves_it():
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    astra = next(row for row in payload["models"] if row["id"] == "shenwen:gpt-6-astra")
    astra["eligible_scopes"] = ["remote_shenwen"]
    astra["capability_states"].update({
        "reasoning": "VERIFIED",
        "planning": "VERIFIED",
        "long_context": "VERIFIED",
    })
    fixture = REGISTRY.parent / ".tmp_model_capability_registry_test.json"
    fixture.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        receipt = route_model_demand(
            "新项目策划和复杂制作流程，请做长链导演规划",
            scope="remote_shenwen",
            registry_path=fixture,
        )
    finally:
        fixture.unlink(missing_ok=True)

    assert receipt["status"] == "ROUTED"
    assert receipt["selected_labor"]["id"] == "shenwen:gpt-6-astra"


def test_auto_scope_selects_remote_astra_for_complex_work_without_changing_local_default():
    receipt = route_model_demand(
        "新项目策划和复杂制作流程，请做长链导演规划",
        scope="auto",
    )

    assert receipt["status"] == "ROUTED"
    assert receipt["selected_labor"]["id"] == "shenwen:gpt-6-astra"
    assert receipt["production_integration"] is False
    assert receipt["health_snapshot"]["_meta"]["loaded"] is True


def test_astra_profile_is_secret_free_and_explicitly_non_production():
    profile = ROOT / "research" / "provider_profiles" / "shenwen_astra.v1.toml"
    text = profile.read_text(encoding="utf-8")

    assert 'model_id = "gpt-6-astra"' in text
    assert 'wire_api = "responses"' in text
    assert 'api_key_env = "SHENWEN_API_KEY"' in text
    assert "production_eligible = false" in text
    assert "sk-" not in text


def test_watchdog_adapter_is_read_only_and_normalizes_status_score(tmp_path):
    path = tmp_path / "watchdog_state.json"
    path.write_text(
        json.dumps({"providers": {"shenwen": {"status": "HEALTHY", "total_calls": 4}}, "last_updated": time.time()}),
        encoding="utf-8",
    )

    snapshot = load_provider_health_snapshot(path)

    assert snapshot["shenwen"]["status"] == "HEALTHY"
    assert snapshot["shenwen"]["health_score"] == 100.0
    assert snapshot["_meta"]["stale"] is False
    assert snapshot["_meta"]["source_path"] == str(path.resolve())
    assert json.loads(path.read_text(encoding="utf-8"))["last_updated"] > 0


def test_stale_watchdog_snapshot_blocks_remote_labor(tmp_path):
    path = tmp_path / "watchdog_state.json"
    path.write_text(
        json.dumps({
            "providers": {"shenwen": {"status": "HEALTHY", "total_calls": 4}},
            "last_updated": time.time() - (24 * 60 * 60 + 1),
        }),
        encoding="utf-8",
    )

    receipt = route_model_demand(
        "新项目策划和复杂制作流程，请做长链导演规划",
        scope="auto",
        health_snapshot=load_provider_health_snapshot(path),
    )

    assert receipt["status"] == "BLOCKED"
    astra = next(row for row in receipt["blocked_candidates"] if row["id"] == "shenwen:gpt-6-astra")
    assert "PROVIDER_UNHEALTHY" in astra["reasons"]


def test_fallback_selector_skips_attempted_labor_and_never_invents_one():
    receipt = {"candidate_set": [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.7}]}

    assert select_fallback_labor(receipt, ["a"])["id"] == "b"
    assert select_fallback_labor(receipt, ["a", "b"]) is None
    assert select_fallback_labor({"candidate_set": []}, []) is None


def test_auto_scope_fails_closed_when_input_exceeds_scoped_probe_limit():
    receipt = route_model_demand("新项目策划和复杂制作流程 " + ("长上下文 " * 3000), scope="auto")

    assert receipt["status"] == "BLOCKED"
    astra = next(row for row in receipt["blocked_candidates"] if row["id"] == "shenwen:gpt-6-astra")
    assert any(reason.startswith("CONTEXT_EXCEEDS_VERIFIED_LIMIT") for reason in astra["reasons"])
