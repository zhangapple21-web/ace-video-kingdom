import json
from pathlib import Path

from tools.validate_state_contract import validate_state_contract


def _valid_contract() -> dict:
    return {
        "schema": "video_kingdom.state_contract.v1",
        "identity_ref": "CHARACTER_IDENTITY_PACK_ID",
        "episode_state": {"costume": "black shirt"},
        "scene_state": {
            "location": "night studio",
            "time": "night",
            "lighting": "warm desk lamp from camera left",
            "space": "a room with a desk and chair",
            "physical_layout": "floor, desk, chair, wall and background depth",
            "interaction_surface": "wooden desk and chair",
            "scene_mode": "LIVE_DIEGETIC_SPACE",
        },
        "shot_state": {
            "start_pose": "seated with phone in right hand",
            "primary_action": "puts the phone down and leans back",
            "emotion_start_end": "tired to amused",
            "camera": "medium shot with a motivated short push",
            "end_state": "leaned back, eyes on desk",
        },
        "approved_for_next_shot": False,
    }


def test_state_contract_requires_playable_scene_mode():
    contract = _valid_contract()
    contract["scene_state"]["scene_mode"] = "SCENIC_BACKGROUND"
    result = validate_state_contract(contract)
    assert result["status"] == "BLOCKED"
    assert any("scene_mode" in error for error in result["errors"])


def test_state_contract_template_uses_validator_field_names():
    root = Path(__file__).resolve().parents[1]
    template = json.loads((root / "assets" / "templates" / "state_contract.v1.json").read_text(encoding="utf-8"))
    scene = template["scene_state"]
    assert "space" in scene
    assert "spatial_relations" not in scene
