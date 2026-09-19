from tools.validate_shot_rhythm import validate_shot_rhythm


def _rhythm():
    return {
        "schema": "video_kingdom.shot_rhythm_contract.v1",
        "shot_purpose": "信息落地",
        "scale": "medium",
        "transition_intent": "反应后切回说话者",
        "script_annotations": {
            "action": "说前看向对方，句尾放下手",
            "dialogue": "明天准备接粉。",
            "emotion": "疲惫但故作轻松",
            "subtext": "其实想让对方留下",
            "motivation": "掩饰心虚",
            "atmosphere": "深夜安静",
        },
        "performance_beats": {
            "speaker_hands_body": "说前揉眼，开口时手指敲桌一次，说完靠回椅背",
            "listener_reaction": "听到关键句眉头收紧，停半拍后抿嘴",
            "pause_point": "说完停半秒，等对方反应",
            "inner_voice_mouth_state": "不适用",
            "cut_motivation": "在听者反应落地后切回说话者",
        },
        "timing_basis": "AUDIO_DRIVEN",
        "audio_anchor": "audio/shot.wav",
    }


def test_strict_performance_rejects_placeholders():
    packet = _rhythm()
    packet["performance_beats"]["speaker_hands_body"] = "PENDING_ROLE_ROOM"
    result = validate_shot_rhythm(packet, strict_performance=True)
    assert result["status"] == "BLOCKED"
    assert any("placeholder" in error for error in result["errors"])


def test_strict_performance_accepts_concrete_dialogue_beats():
    assert validate_shot_rhythm(_rhythm(), strict_performance=True)["status"] == "PASS"
