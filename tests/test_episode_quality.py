from tools.validate_episode_quality import validate


def test_experimental_plan_reports_gaps_without_blocking_exploration():
    result = validate({"quality_mode": "EXPERIMENTAL", "shots": [{"shot_id": "A", "action_beats": ["start", "move", "end"]}]})
    assert result["status"] == "EXPERIMENTAL_WITH_GAPS"
    assert result["warnings"]


def test_formal_plan_fails_closed_on_missing_layers():
    result = validate({"quality_mode": "FORMAL", "shots": [{"shot_id": "A"}]})
    assert result["status"] == "INVALID"
    assert any("A.dramatic_function" in error for error in result["errors"])


def test_formal_minimal_plan_passes():
    shot = {
        "shot_id": "A", "dramatic_function": "reveal", "information_gain": "the record exists",
        "emotion_change": "uncertain to resolved", "action_beats": ["hands empty", "opens folder", "record visible"],
        "camera": {"scale": "close", "movement": "locked", "axis": "A"}, "continuity_bridge": "record stays in hand",
        "audio_beats": ["room tone", "paper sound"],
    }
    root = {"quality_mode": "FORMAL", "premise": "A worker preserves evidence", "causal_chain": ["debt", "record", "claim"],
            "plants": [{"id": "record", "shot_id": "A"}], "payoffs": [{"id": "record", "shot_id": "A"}],
            "viewer_knowledge_checkpoints": [{"time": "00:05", "knows": "record exists"}], "shots": [shot]}
    assert validate(root)["status"] == "VALID"
