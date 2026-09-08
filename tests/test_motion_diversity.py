from tools.validate_motion_diversity import validate


def test_distinct_action_arcs_pass():
    result = validate({"shots": [
        {"shot_id": "A", "action_beats": ["hands sort a folder", "clips pages", "folder enters bag"]},
        {"shot_id": "B", "action_beats": ["she hears a knock", "stands and opens door", "steps into corridor"]},
    ]})
    assert result["status"] == "VALID"
    assert result["warnings"] == []


def test_missing_action_arc_is_rejected():
    result = validate({"shots": [{"shot_id": "A", "prompt": "she sighs"}]})
    assert result["status"] == "INVALID"
    assert "action_beats" in result["errors"][0]


def test_duplicate_action_arcs_are_flagged():
    result = validate({"shots": [
        {"shot_id": "A", "action_beats": ["looks at phone", "exhales", "lowers phone"]},
        {"shot_id": "B", "action_beats": ["looks at phone", "exhales", "lowers phone"]},
    ]})
    assert result["status"] == "VALID"
    assert result["warnings"]
