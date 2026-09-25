from tools.validate_story_action import validate_story_action_packet


def _packet():
    return {
        "new_drama": True,
        "shot_rhythm": {
            "dramatic_function": "让徒弟的捷径第一次产生可见后果",
            "visible_change": "玻璃与普通门的关系从误认变成可验证选择",
            "visible_consequence": "徒弟刹停并改为伸手找门把",
            "script_annotations": {"action": "徒弟冲到玻璃前刹停，随后转身看向普通门"},
            "performance_beats": {
                "speaker_hands_body": "说话前抬手指向玻璃，停住后手掌收回并转身",
                "listener_reaction": "师父抬眉，徒弟的得意表情垮下来",
            },
        },
    }


def test_story_action_gate_requires_visible_change():
    packet = _packet()
    packet["shot_rhythm"].pop("visible_change")
    result = validate_story_action_packet(packet)
    assert result["status"] == "BLOCKED"
    assert any("visible_change" in error for error in result["errors"])


def test_story_action_gate_rejects_camera_contamination():
    packet = _packet()
    packet["shot_rhythm"]["performance_beats"]["speaker_hands_body"] = "摄影机跟拍人物走到门口"
    result = validate_story_action_packet(packet)
    assert result["status"] == "BLOCKED"
    assert any("camera language" in error for error in result["errors"])


def test_story_action_gate_accepts_visible_actor_event():
    assert validate_story_action_packet(_packet())["status"] == "PASS"
