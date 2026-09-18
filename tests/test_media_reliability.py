import json

from production_control.media_executor import execute_media_task
from production_control.media_routing import build_image_model_plan, choose_image_strategy, classify_media_intent, route_media_demand
from production_control.task_state import complete, create, load, progress


MEDIA_ENV = {"SHENWEN_API_KEY": "test-key", "AGNES_API_KEY": "test-key"}


def test_media_intents_are_not_general():
    assert classify_media_intent("\u751f\u6210\u89d2\u8272\u5305\u56fe") == "IMAGE"
    assert classify_media_intent("\u751f\u6210\u7b2c1\u955c\u89c6\u9891") == "VIDEO"
    assert classify_media_intent("\u751f\u6210\u89d2\u8272\u5305\u56fe + \u7b2c1\u955c\u89c6\u9891") == "MIXED"


def test_image_strategy_escalates_only_for_composition_risk():
    assert choose_image_strategy("\u751f\u6210\u7b2c1\u955c\u89c6\u9891")["mode"] == "REFERENCE_ONLY"
    assert choose_image_strategy("\u751f\u6210\u7b2c1\u955c\u89c6\u9891，\u5148\u9501\u5b9a\u9996\u5e27\u6784\u56fe")["mode"] == "COMPOSITION_STILL_CANDIDATE"


def test_image_model_plan_has_verified_fallbacks_only():
    route = route_media_demand("\u751f\u6210\u89d2\u8272\u5305\u56fe", env=MEDIA_ENV)
    plan = build_image_model_plan(route)
    assert plan["status"] == "READY"
    assert [item["model"] for item in plan["candidates"]] == [
        "gpt-image-2", "gpt-image-2.5-flare", "gpt-image-2.5-sunburst",
        "grok-imagine-image", "grok-imagine-image-quality",
    ]
    assert plan["blocked_variants"] == []
    assert [item["model"] for item in plan["candidates"]] == [
        "gpt-image-2", "gpt-image-2.5-flare", "gpt-image-2.5-sunburst",
        "grok-imagine-image", "grok-imagine-image-quality",
    ]


def test_media_route_binds_capability_and_project():
    route = route_media_demand("\u751f\u6210\u89d2\u8272\u5305\u56fe", env=MEDIA_ENV)
    assert route["status"] == "ROUTED"
    assert route["task_class"] == "IMAGE"
    assert route["required_capabilities"] == ["image.generate"]
    assert route["selected_routes"][0]["model"] == "gpt-image-2"
    assert {item["model"] for item in route["selected_routes"][0]["available_variants"]} == {
        "gpt-image-2.5-flare", "gpt-image-2.5-sunburst",
        "grok-imagine-image", "grok-imagine-image-quality",
    }
    assert all(
        item["status"] == "PROBE_PASS"
        for item in route["selected_routes"][0]["available_variants"]
        if item["model"].startswith("gpt-image")
    )
    assert route["project"]["project_id"] == "ace-video-kingdom"
    assert route["production_integration"] is True


def test_missing_media_credential_is_blocked_once():
    route = route_media_demand("\u751f\u6210\u7b2c1\u955c\u89c6\u9891", env={})
    assert route["status"] == "BLOCKED"
    assert "CREDENTIAL_MISSING" in route["selected_routes"][0]["reasons"]


def test_task_state_stalls_after_two_identical_actions(tmp_path):
    state_path = tmp_path / "task.json"
    create(state_path, "t-1", "\u751f\u6210\u89d2\u8272\u5305\u56fe")
    action = {"step": "route", "capability": "image.generate"}
    progress(state_path, state="READY", current_step="route", next_action="execute", action=action)
    state = progress(state_path, state="READY", current_step="route", next_action="execute", action=action)
    assert state["state"] == "STALLED"
    assert state["lifecycle_state"] == "STALLED"
    assert state["no_progress_count"] == 1


def test_media_executor_writes_bound_receipt_and_completion(tmp_path):
    result = execute_media_task(
        tmp_path / "state.json",
        "t-image",
        "\u751f\u6210\u89d2\u8272\u5305\u56fe",
        output_dir=tmp_path / "artifacts",
        env=MEDIA_ENV,
        dry_run=True,
        context_messages=[{"role": "assistant", "text": "结论：角色包已锁定"}],
    )
    assert result["status"] == "COMPLETED"
    assert result["receipt"]["project_id"] == "ace-video-kingdom"
    assert result["receipt"]["capability"] == ["image.generate"]
    assert result["receipt"]["verification"] == "PASS"
    assert load(tmp_path / "state.json")["lifecycle_state"] == "COMPLETED"
    assert result["receipt"]["projection"]["protected_conclusions"] == 1


def test_executor_failure_is_persisted_as_failed(tmp_path):
    def failing_runner(route, request, output_dir):
        raise RuntimeError("provider unavailable")

    result = execute_media_task(
        tmp_path / "state.json",
        "t-fail",
        "\u751f\u6210\u7b2c1\u955c\u89c6\u9891",
        output_dir=tmp_path / "artifacts",
        env=MEDIA_ENV,
        runner=failing_runner,
    )
    assert result["status"] == "FAILED"
    assert result["receipt"]["verification"] == "FAIL"
    assert load(tmp_path / "state.json")["state"] == "FAILED"
