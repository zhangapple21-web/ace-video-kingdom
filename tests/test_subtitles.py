from pathlib import Path

from tools.validate_subtitles import Cue, parse_srt, validate


def test_episode_006_track_is_valid():
    path = Path(__file__).parent / "fixtures/episode_006_full_inner_monologue.srt"
    result = validate(parse_srt(path))
    assert result["status"] == "VALID"
    assert result["errors"] == []


def test_overlapping_cues_are_rejected():
    result = validate([Cue(1, 0.0, 1.0, "第一句"), Cue(2, 0.9, 2.0, "第二句")])
    assert result["status"] == "INVALID"
    assert any("overlaps cue 1" in error for error in result["errors"])


def test_scene_direction_is_rejected_from_dialogue_track():
    result = validate([Cue(1, 0.0, 1.0, "[SCENE] she enters the room")])
    assert result["status"] == "INVALID"
    assert any("scene-direction" in error for error in result["errors"])
