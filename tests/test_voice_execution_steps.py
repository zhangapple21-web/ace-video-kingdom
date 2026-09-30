"""Standing voice execution rules, not a one-off episode patch."""
from __future__ import annotations

import pytest

from tools.voice_preflight import (
    ForgedListeningQC,
    SpeedOutOfRange,
    VoiceExecutionError,
    assert_listening_qc_not_forged,
    build_instruction,
    formal_instruct2_call,
    new_take_receipt,
)


PERFORMANCE = {
    "speech_intent": "逼对方正面回应",
    "emotion": "炸毛",
    "delivery": "高能量但不哭喊",
    "emphasis": "欠我/两天工资",
    "ending": "质问收住",
    "performance_notes": "不要慢放",
}


def test_per_line_fields_are_in_the_cosy_prompt():
    prompt, contract = build_instruction("你还欠我两天工资！", "DIALOGUE", performance=PERFORMANCE, speed=1.05)
    assert contract["instruction_mode"] == "PER_LINE"
    assert contract["formal_voice_performance"] is True
    for value in PERFORMANCE.values():
        assert value in prompt
    assert prompt.startswith("You are a helpful assistant. ")
    assert prompt.endswith("<|endofprompt|>")
    assert "保留自然缓冲" not in prompt
    assert "不要留缓冲" in prompt
    call = formal_instruct2_call("你还欠我两天工资！", "DIALOGUE", performance=PERFORMANCE, speed=1.05)
    assert call["instruct_text"] == prompt
    assert call["speed"] == 1.05
    assert call["tts_text"] == "你还欠我两天工资！"
    assert call["listening_qc"] == "PENDING_HUMAN"


def test_missing_performance_is_generic_fallback_not_per_line():
    prompt, contract = build_instruction("好哒～", "DIALOGUE")
    assert contract["instruction_mode"] == "GENERIC_FALLBACK"
    assert contract["formal_voice_performance"] is False
    assert "MISSING_SPEECH_INTENT_OR_DELIVERY" in contract["production_blockers"]
    assert "通用兜底" in prompt
    assert "说话目的" not in prompt
    with pytest.raises(VoiceExecutionError, match="GENERIC_FALLBACK"):
        formal_instruct2_call("好哒～", "DIALOGUE")


def test_speed_below_floor_is_rejected_or_clamped():
    with pytest.raises(SpeedOutOfRange):
        build_instruction("好哒～", "DIALOGUE", performance=PERFORMANCE, speed=0.62)
    prompt, contract = build_instruction(
        "好哒～",
        "DIALOGUE",
        performance=PERFORMANCE,
        speed=0.62,
        allow_speed_clamp=True,
    )
    assert contract["speed"] == 0.85
    assert contract["requested_speed"] == 0.62
    assert contract["speed_source"] == "CLAMPED_MEL_STRETCH"
    assert "SPEED_CLAMPED_NOT_A_PERFORMANCE" in contract["production_blockers"]
    assert "保留自然缓冲" not in prompt
    assert "不要留缓冲" in prompt


def test_machine_listening_stamp_is_rejected():
    with pytest.raises(ForgedListeningQC):
        assert_listening_qc_not_forged({
            "listening_qc": "VERIFIED_RMS_ENVELOPE_AND_TIMELINE_ALIGN_OK",
            "status": "LOCKED",
        })
    with pytest.raises(ForgedListeningQC):
        assert_listening_qc_not_forged({"status": "LOCKED", "listening_qc": "PENDING_HUMAN"})
    assert_listening_qc_not_forged({
        "status": "GENERATED_PENDING_LISTENING_QC",
        "listening_qc": "PENDING_HUMAN",
        "human_listened": False,
    })
    receipt = new_take_receipt("好哒～", "DIALOGUE", performance=PERFORMANCE)
    assert receipt["status"] == "GENERATED_PENDING_LISTENING_QC"
    assert receipt["do_not_overwrite_locked"] is True
    assert_listening_qc_not_forged(receipt)
