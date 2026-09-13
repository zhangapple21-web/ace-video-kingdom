from pathlib import Path

from production_control.media_routing import classify_media_intent, route_media_demand
from production_control.project import discover_project
from production_control.task_state import append_event, create, progress
from production_control.media_executor import execute_media_task


def test_media_intent_does_not_misclassify_vision_as_generation():
    assert classify_media_intent("请看这张图片，判断人物身份和画面连续性") is None
    assert classify_media_intent("生成两张角色包图") == "IMAGE"
    assert classify_media_intent("制作第1镜视频") == "VIDEO"
    assert classify_media_intent("生成角色包图并制作第1镜视频") == "MIXED"


def test_media_route_locks_model_and_fails_closed_without_secret():
    route = route_media_demand("生成两张角色包图", env={})
    assert route["task_class"] == "IMAGE"
    assert route["status"] == "BLOCKED"
    selected = route["selected_routes"][0]
    assert selected["model"] == "gpt-image-2"
    assert selected["model_locked"] is True
    assert "CREDENTIAL_MISSING" in selected["reasons"]


def test_project_discovery_is_canonical_and_hashed():
    result = discover_project("C:/tmp")
    assert result["project_id"] == "ace-video-kingdom"
    assert result["source_of_truth"] == "canonical_root"
    assert len(result["manifest_sha256"]) == 64


def test_image_wrapper_locks_production_model():
    wrapper = Path("D:/tmp/ace-video-kingdom/tools/imagegen_shenwen.ps1").read_text(encoding="utf-8")
    assert "MODEL_OVERRIDE_REJECTED" in wrapper
    assert "gpt-image-2" in wrapper


def test_media_executor_closes_route_artifact_receipt(tmp_path: Path):
    result = execute_media_task(
        tmp_path / "task_state.json",
        "task-e2e",
        "生成两张角色包图",
        output_dir=tmp_path / "receipts",
        env={"SHENWEN_API_KEY": "test"},
        dry_run=True,
    )
    assert result["status"] == "COMPLETED"
    assert result["state"]["state"] == "COMPLETED"
    assert Path(result["receipt_path"]).is_file()
    assert result["receipt"]["verification"] == "PASS"
    replay = execute_media_task(
        tmp_path / "task_state.json",
        "task-e2e",
        "生成两张角色包图",
        output_dir=tmp_path / "receipts",
        env={"SHENWEN_API_KEY": "test"},
        dry_run=True,
    )
    assert replay["idempotent"] is True


def test_media_executor_persists_blocked_receipt(tmp_path: Path):
    result = execute_media_task(
        tmp_path / "task_state.json",
        "task-blocked",
        "生成两张角色包图",
        output_dir=tmp_path / "receipts",
        env={},
    )
    assert result["status"] == "BLOCKED"
    assert result["state"]["state"] == "WAITING_CAPABILITY"
    assert Path(result["receipt_path"]).is_file()


def test_task_state_stalls_after_repeated_no_progress(tmp_path: Path):
    state_path = tmp_path / "task_state.json"
    create(state_path, "task-1", "生成角色包图")
    action = {"capability": "image.generate", "step": "execute"}
    progress(state_path, state="RUNNING", current_step="execute", next_action="poll receipt", action=action)
    stalled = progress(state_path, state="RUNNING", current_step="execute", next_action="poll receipt", action=action)
    stalled = progress(state_path, state="RUNNING", current_step="execute", next_action="poll receipt", action=action)
    assert stalled["state"] == "STALLED"
    assert "action fingerprint" in stalled["next_action"]


def test_external_event_does_not_reset_task_progress(tmp_path: Path):
    state_path = tmp_path / "task_state.json"
    create(state_path, "task-event", "生成角色包图")
    progress(state_path, state="RUNNING", current_step="execute", next_action="verify receipt", action={"step": "execute"})
    before = progress(state_path, state="RUNNING", current_step="execute", next_action="verify receipt", action={"step": "execute"}, progress_token="started")
    updated = append_event(state_path, {"type": "user_followup", "text": "保留当前角色包，不重做"})
    assert updated["state"] == "RUNNING"
    assert updated["current_step"] == before["current_step"]
    assert updated["events"][-1]["type"] == "user_followup"
