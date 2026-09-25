from pathlib import Path

from tools.validate_creative_slice import validate_creative_slice


def test_creative_slice_requires_goal_obstacle_reversal_and_evidence(tmp_path: Path):
    clip = tmp_path / "slice.mp4"
    clip.write_bytes(b"clip")
    packet = {
        "schema": "video_kingdom.creative_slice.v1",
        "status": "PASS",
        "beats": {"goal": "赶在打卡前穿过门", "obstacle": "玻璃挡住去路", "reversal": "普通门就在旁边"},
        "viewer_change": "徒弟从要穿墙改为找门",
        "evidence": {"video_path": str(clip)},
    }
    assert validate_creative_slice(packet, base_dir=tmp_path)["status"] == "PASS"


def test_creative_slice_blocks_pending_or_missing_video(tmp_path: Path):
    packet = {
        "schema": "video_kingdom.creative_slice.v1",
        "status": "PENDING",
        "beats": {"goal": "要什么", "obstacle": "阻碍", "reversal": "反转"},
        "viewer_change": "变化",
        "evidence": {"video_path": "missing.mp4"},
    }
    result = validate_creative_slice(packet, base_dir=tmp_path)
    assert result["status"] == "BLOCKED"
    assert result["batch_expansion_allowed"] is False
