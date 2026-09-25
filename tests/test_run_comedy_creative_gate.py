import json
from pathlib import Path

from tools.run_comedy_episode import _validate_episode_creative_slice


def _episode(tmp_path: Path, receipt: str | None = None) -> dict:
    value = {
        "project_id": "demo",
        "production_semantics": "new_drama",
        "shots": [],
        "__episode_path": str(tmp_path / "episode.json"),
    }
    if receipt is not None:
        value["acceptance"] = {"creative_slice_receipt": receipt}
    return value


def _write_receipt(tmp_path: Path, *, video_name: str = "slice.mp4") -> None:
    (tmp_path / video_name).write_bytes(b"not-a-video-but-present-evidence")
    (tmp_path / "slice.json").write_text(json.dumps({
        "schema": "video_kingdom.creative_slice.v1",
        "status": "PASS",
        "beats": {"goal": "要什么", "obstacle": "阻碍", "reversal": "改变"},
        "viewer_change": "观众知道关系发生变化",
        "evidence": {"video_path": video_name},
    }, ensure_ascii=False), encoding="utf-8")


def test_non_new_drama_episode_does_not_require_slice(tmp_path):
    episode = _episode(tmp_path)
    episode["production_semantics"] = "reference_research"
    assert _validate_episode_creative_slice(episode)["status"] == "SKIPPED"


def test_new_drama_without_slice_is_blocked(tmp_path):
    result = _validate_episode_creative_slice(_episode(tmp_path))
    assert result["status"] == "BLOCKED"
    assert "creative_slice_receipt" in result["errors"][0]


def test_new_drama_requires_a_passed_local_slice(tmp_path):
    _write_receipt(tmp_path)
    result = _validate_episode_creative_slice(_episode(tmp_path, "slice.json"))
    assert result["status"] == "PASS"


def test_slice_receipt_cannot_escape_episode_directory(tmp_path):
    outside = tmp_path.parent / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    result = _validate_episode_creative_slice(_episode(tmp_path, "../outside.json"))
    assert result["status"] == "BLOCKED"
    assert "escapes" in result["errors"][0]
