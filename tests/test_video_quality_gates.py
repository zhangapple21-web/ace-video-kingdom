from tools.validate_continuity_bridge import validate_bridge
from tools.validate_media_readback import compare_readback
from tools.validate_shot_prompt import validate_prompt


def test_prompt_gate_blocks_style_drift_and_ui():
    result = validate_prompt({"compiled_prompt": "主体：一人；动作：走路；环境：房间；光线：暖光；镜头：固定；风格：写实；微信聊天界面", "txt_prompt_elements": {"subject": "一人", "action": "走路", "environment": "房间", "lighting": "暖光", "camera": "固定", "style": "写实"}, "style_lock": "写实"})
    assert result["status"] == "BLOCKED"


def test_continuity_gate_requires_frame_proof_for_ready():
    result = validate_bridge({"status": "READY", "previous_end_frame_state": "人物右手持杯", "next_initial_state": "人物右手持杯", "camera_state": "35mm固定", "lighting_state": "左侧暖光", "tail_frame_state": "杯子停在胸前", "enter_direction": "hold", "exit_direction": "hold"})
    assert result["status"] == "BLOCKED"


def test_media_readback_blocks_unverified_human_listening():
    result = compare_readback({"width": 720, "height": 1280, "frame_count": 240, "audio_tracks": 1, "subtitle_tracks": 0, "duration_seconds": 10.0}, {"width": 720, "height": 1280, "frame_count": 240, "audio_tracks": 1, "subtitle_tracks": 0, "duration_seconds": 10.0, "audio_required": True, "human_listening": "UNVERIFIED"})
    assert result["status"] == "READBACK_MISMATCH"
