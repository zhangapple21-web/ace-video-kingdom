from tools.validate_continuity_bridge import validate_bridge


def test_continuity_bridge_accepts_typed_clue_ui_and_fx_assets():
    bridge = {
        "previous_end_frame_state": "end",
        "next_initial_state": "start",
        "camera_state": "static",
        "lighting_state": "window",
        "tail_frame_state": "hold",
        "enter_direction": "hold",
        "exit_direction": "hold",
        "asset_register": [
            {"asset_id": "CLUE_A", "kind": "clue", "initial": "sealed", "change": "open", "final": "visible"},
            {"asset_id": "UI_A", "kind": "ui_plate", "initial": "hidden", "change": "show", "final": "hidden"},
            {"asset_id": "FX_A", "kind": "fx", "initial": "off", "change": "flash", "final": "off"},
        ],
    }

    assert validate_bridge(bridge)["status"] == "PASS"
