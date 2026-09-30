"""Deterministic preflight and delivery guidance for scripted TTS lines.

The preflight is conservative: it repairs only unambiguous surface noise and
keeps the source line available for audit. It does not invent filler words or
rewrite plot-critical text without an explicit scene decision.

Standing execution rule: a contract field is not performed until it is written
into the Cosy natural-language instruction and passed to inference_instruct2.
Missing speech_intent or delivery is GENERIC_FALLBACK, never a per-line take.
speed is post-synthesis mel stretch and stays within 0.85-1.15.
Listening QC cannot be stamped by hash, duration, RMS, or frame spacing.
"""
from __future__ import annotations

import re
from typing import Any

VOICE_RULESET = "AI_SHORT_DRAMA_VOICE_V2.0"
DEFAULT_WRAPPER = "You are a helpful assistant. "
END_OF_PROMPT = "<|endofprompt|>"
SPEED_MIN = 0.85
SPEED_MAX = 1.15
SPEED_DEFAULT = 1.0
SPEED_POLICY = "MEL_LINEAR_STRETCH_NOT_PROSODY"
PERFORMANCE_FIELDS = (
    "speech_intent",
    "emotion",
    "delivery",
    "emphasis",
    "ending",
    "performance_notes",
)
REQUIRED_PERFORMANCE_FIELDS = ("speech_intent", "delivery")
FORBIDDEN_MACHINE_LISTENING = {
    "VERIFIED_RMS_ENVELOPE_AND_TIMELINE_ALIGN_OK",
    "VERIFIED",
    "QC_PASS",
    "PASSED_LISTENING",
    "LISTENED_OK",
}


class VoiceExecutionError(ValueError):
    """Standing voice-execution rule was violated."""


class SpeedOutOfRange(VoiceExecutionError):
    """Requested Cosy speed is outside the mel-stretch safe range."""


class ForgedListeningQC(VoiceExecutionError):
    """A script tried to claim a human listened when it did not."""


def _surface_clean(text: str) -> tuple[str, list[str]]:
    original = str(text)
    cleaned = original.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = cleaned.strip()
    repairs: list[str] = []
    if cleaned != original:
        repairs.append("surface_whitespace_normalized")

    def collapse(match: re.Match[str]) -> str:
        repairs.append("repeated_punctuation_collapsed")
        return match.group(1)

    collapsed = re.sub(r"([！？!?])\1{1,}", collapse, cleaned)
    return collapsed, sorted(set(repairs))


def _risk_flags(text: str) -> tuple[list[str], str]:
    flags: list[str] = []
    if re.search(r"[。！？!?]", text) and len(re.findall(r"[！？!?]", text)) >= 2:
        flags.append("B_HIGH_PUNCTUATION")
    if "——" in text or "……" in text or "…" in text:
        flags.append("A_LOCKED_PAUSE_OR_REPETITION")
    if re.search(r"\d|[年月日点分秒%％]", text):
        flags.append("C_LITERAL_FACT_OR_NUMBER")
    if len(text) <= 8:
        flags.append("SHORT_LINE_CONTEXT_REQUIRED")
    if len(text) >= 24:
        flags.append("LONG_LINE_CONTINUITY_REQUIRED")
    if any(flag.startswith("C_") for flag in flags):
        return flags, "C"
    if any(flag.startswith("B_") for flag in flags):
        return flags, "B"
    if any(flag.startswith("A_") for flag in flags):
        return flags, "A"
    return flags, "NONE"


def _semantic_groups(text: str) -> list[str]:
    groups = [part.strip() for part in re.split(r"(?<=[，。！？；：、…——])", text) if part.strip()]
    return groups or [text]


def _clean_performance(performance: dict[str, Any] | None) -> dict[str, str]:
    source = performance or {}
    cleaned: dict[str, str] = {}
    for key in PERFORMANCE_FIELDS:
        value = str(source.get(key) or "").strip()
        if value:
            cleaned[key] = value
    return cleaned


def resolve_speed(speed: float | None = None, *, allow_clamp: bool = False) -> dict[str, Any]:
    """Resolve Cosy speed. None means 1.0. Outside 0.85-1.15 is rejected unless clamped."""
    if speed is None or speed == "":
        return {
            "speed": SPEED_DEFAULT,
            "requested_speed": None,
            "speed_adjusted": False,
            "speed_source": "DEFAULT_1_0",
            "speed_policy": SPEED_POLICY,
        }
    value = float(speed)
    if SPEED_MIN <= value <= SPEED_MAX:
        return {
            "speed": round(value, 4),
            "requested_speed": value,
            "speed_adjusted": False,
            "speed_source": "REQUESTED",
            "speed_policy": SPEED_POLICY,
        }
    if not allow_clamp:
        raise SpeedOutOfRange(
            f"Cosy speed {value} 超出 {SPEED_MIN}-{SPEED_MAX}。"
            "speed 是合成后对 mel 做线性拉伸，不是让模型慢慢说或快点说。"
            "认真、克制、短句不要抢，写进 delivery；不要用低于 "
            f"{SPEED_MIN} 的倍率。"
        )
    clamped = min(SPEED_MAX, max(SPEED_MIN, value))
    return {
        "speed": round(clamped, 4),
        "requested_speed": value,
        "speed_adjusted": True,
        "speed_source": "CLAMPED_MEL_STRETCH",
        "speed_policy": SPEED_POLICY,
    }


def build_voice_contract(
    text: str,
    track_type: str = "DIALOGUE",
    performance: dict[str, Any] | None = None,
    speed: float | None = None,
    allow_speed_clamp: bool = False,
) -> dict[str, Any]:
    source = str(text)
    normalized, repairs = _surface_clean(source)
    flags, risk_class = _risk_flags(normalized)
    short_line = len(normalized) <= 8
    monologue = str(track_type).upper() == "INNER_MONOLOGUE"
    performed = _clean_performance(performance)
    missing = [key for key in REQUIRED_PERFORMANCE_FIELDS if key not in performed]
    per_line = not missing
    speed_info = resolve_speed(speed, allow_clamp=allow_speed_clamp)
    blockers: list[str] = []
    if not per_line:
        blockers.append("MISSING_SPEECH_INTENT_OR_DELIVERY")
    if speed_info["speed_adjusted"]:
        blockers.append("SPEED_CLAMPED_NOT_A_PERFORMANCE")
    return {
        "ruleset": VOICE_RULESET,
        "source_text": source,
        "generation_text": normalized,
        "surface_repairs": repairs,
        "semantic_groups": _semantic_groups(normalized),
        "pause_before_seconds": 0.12 if monologue else (0.08 if short_line else 0.04),
        "pause_after_seconds": 0.16 if short_line else (0.10 if monologue else 0.06),
        "pause_seconds_are_edit_hints_not_cosy_controls": True,
        "breath_hint": "natural_breath_between_semantic_groups",
        "delivery_speed": "performance_directed" if per_line else "natural_unpadded",
        "emotion": performed.get("emotion") or "light_controlled",
        "emotion_intensity": 0.35,
        "delivery": performed.get("delivery") or "生活化、语义清楚、轻重自然、保持音色一致",
        "performance": performed,
        "instruction_mode": "PER_LINE" if per_line else "GENERIC_FALLBACK",
        "formal_voice_performance": per_line,
        "production_blockers": blockers,
        "avoid": ["播音腔", "朗读感", "机械均匀", "夸张表演", "刻意拖长尾音", "用留缓冲填窗口"],
        "filler_policy": "CONTEXTUAL_ONLY_PRESERVE_CORE_TEXT",
        "short_line_policy": "GENERATE_ALONE_DO_NOT_PAD_OR_STRETCH",
        "long_line_policy": "KEEP_SEMANTIC_CONTINUITY_AND_AVOID_HARD_SPLIT",
        "risk_class": risk_class,
        "risk_flags": flags,
        "status": "PREFLIGHT_REVIEW_REQUIRED" if risk_class in {"A", "B", "C"} else "PREFLIGHT_PASS",
        "listening_qc": "PENDING_HUMAN",
        **speed_info,
    }


def _direction(track_type: str, contract: dict[str, Any]) -> str:
    monologue = str(track_type).upper() == "INNER_MONOLOGUE"
    voice = "女主角自然的低声内心独白" if monologue else "女主角生活化自然说话"
    if contract["instruction_mode"] != "PER_LINE":
        return (
            "保持参考音频的音色与质感，" + voice + "。"
            "这是通用兜底，不是逐句表演。"
            "长句保持语义连贯；短句单独说完，不要留缓冲，不要拖长尾音去填窗口。"
            "轻重自然，吐字清楚但不刻意。"
            "不要播音腔，不要朗读感，不要机械均匀，不要夸张表演。"
        )
    performed = contract["performance"]
    parts = [
        "保持参考音频的音色与质感，" + voice + "。",
        "说话目的：" + performed["speech_intent"] + "。",
        "演法：" + performed["delivery"] + "。",
    ]
    if performed.get("emotion"):
        parts.append("情绪：" + performed["emotion"] + "。")
    if performed.get("emphasis"):
        parts.append("重音：" + performed["emphasis"] + "。")
    if performed.get("ending"):
        parts.append("句尾：" + performed["ending"] + "。")
    if performed.get("performance_notes"):
        parts.append("补充：" + performed["performance_notes"] + "。")
    parts.append("把这句一次说完，不要为了填时长拖长，不要留缓冲，不要播音腔，不要机械均匀念稿。")
    return "".join(parts)


def build_instruction(
    text: str,
    track_type: str = "DIALOGUE",
    performance: dict[str, Any] | None = None,
    speed: float | None = None,
    allow_speed_clamp: bool = False,
) -> tuple[str, dict[str, Any]]:
    contract = build_voice_contract(
        text,
        track_type,
        performance=performance,
        speed=speed,
        allow_speed_clamp=allow_speed_clamp,
    )
    prompt = DEFAULT_WRAPPER + _direction(track_type, contract) + END_OF_PROMPT
    contract["instruction_text"] = prompt
    return prompt, contract


def new_take_receipt(
    text: str,
    track_type: str = "DIALOGUE",
    performance: dict[str, Any] | None = None,
    speed: float | None = None,
    allow_speed_clamp: bool = False,
) -> dict[str, Any]:
    """Receipt for a new take. Never marks listening done and never overwrites a locked master."""
    prompt, contract = build_instruction(
        text,
        track_type,
        performance=performance,
        speed=speed,
        allow_speed_clamp=allow_speed_clamp,
    )
    return {
        "status": "GENERATED_PENDING_LISTENING_QC",
        "listening_qc": "PENDING_HUMAN",
        "human_listened": False,
        "instruction_text": prompt,
        "instruction_mode": contract["instruction_mode"],
        "formal_voice_performance": contract["formal_voice_performance"],
        "production_blockers": contract["production_blockers"],
        "speed": contract["speed"],
        "requested_speed": contract["requested_speed"],
        "speed_source": contract["speed_source"],
        "do_not_overwrite_locked": True,
        "contract": contract,
    }


def assert_listening_qc_not_forged(record: dict[str, Any]) -> None:
    """Hash, duration, RMS, or ffprobe frame spacing is not a human listen."""
    qc = str(record.get("listening_qc") or "").strip()
    status = str(record.get("status") or "").strip()
    qc_key = qc.upper()
    machine_stamp = (
        qc in FORBIDDEN_MACHINE_LISTENING
        or qc_key in FORBIDDEN_MACHINE_LISTENING
        or "RMS_ENVELOPE" in qc_key
        or "FFPROBE_FRAME" in qc_key
        or "FRAME_VARIANCE" in qc_key
        or "SHOW_FRAMES" in qc_key
    )
    if machine_stamp:
        raise ForgedListeningQC(
            "听感不能由 RMS、时长、哈希或 ffprobe 帧间隔写成已验证。"
            "WAV 帧间隔本来就恒定，不能用来判断机械念稿。"
        )
    human = record.get("human_listened") is True and bool(str(record.get("human_listener") or "").strip())
    claims_verified = status == "LOCKED" or any(
        token in qc_key for token in ("VERIFIED", "QC_PASS", "PASSED_LISTENING", "LISTENED_OK")
    )
    if claims_verified and not human:
        raise ForgedListeningQC(
            "没有 human_listened 和 human_listener，不能写 LOCKED 或听感已验证。"
            "脚本只能写 PENDING_HUMAN。"
        )
    if human and not str(record.get("listened_at") or "").strip():
        raise ForgedListeningQC("真人听过必须留下 listened_at，不能只打一个通过标记。")
    if human and qc_key in {"", "PENDING_HUMAN"} and status == "LOCKED":
        raise ForgedListeningQC("锁定前必须写下真人听感结论，不能只写 LOCKED。")



def formal_instruct2_call(
    text: str,
    track_type: str = "DIALOGUE",
    performance: dict[str, Any] | None = None,
    speed: float | None = None,
    allow_speed_clamp: bool = False,
) -> dict[str, Any]:
    """Arguments that must be passed to CosyVoice3.inference_instruct2."""
    prompt, contract = build_instruction(
        text,
        track_type,
        performance=performance,
        speed=speed,
        allow_speed_clamp=allow_speed_clamp,
    )
    if contract["instruction_mode"] != "PER_LINE":
        raise VoiceExecutionError(
            "正式合成不能只用通用 instruction。缺 speech_intent 或 delivery 时是 GENERIC_FALLBACK，不能当逐句表演。"
        )
    return {
        "tts_text": contract["generation_text"],
        "instruct_text": prompt,
        "speed": contract["speed"],
        "stream": False,
        "text_frontend": True,
        "listening_qc": "PENDING_HUMAN",
        "instruction_mode": "PER_LINE",
        "do_not_overwrite_locked": True,
    }

__all__ = [
    "VOICE_RULESET",
    "SPEED_MIN",
    "SPEED_MAX",
    "SPEED_DEFAULT",
    "VoiceExecutionError",
    "SpeedOutOfRange",
    "ForgedListeningQC",
    "resolve_speed",
    "build_instruction",
    "build_voice_contract",
    "new_take_receipt",
    "assert_listening_qc_not_forged",
    "formal_instruct2_call",
]
