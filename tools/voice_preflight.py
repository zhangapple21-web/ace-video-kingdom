"""Deterministic preflight and delivery guidance for scripted TTS lines.

The preflight is conservative: it repairs only unambiguous surface noise and
keeps the source line available for audit. It does not invent filler words or
rewrite plot-critical text without an explicit scene decision.
"""
from __future__ import annotations

import re
from typing import Any


VOICE_RULESET = "AI_SHORT_DRAMA_VOICE_V2.0"
DEFAULT_WRAPPER = "You are a helpful assistant. "
END_OF_PROMPT = "<|endofprompt|>"


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


def build_voice_contract(text: str, track_type: str = "DIALOGUE") -> dict[str, Any]:
    source = str(text)
    normalized, repairs = _surface_clean(source)
    flags, risk_class = _risk_flags(normalized)
    short_line = len(normalized) <= 8
    long_line = len(normalized) >= 24
    monologue = str(track_type).upper() == "INNER_MONOLOGUE"
    return {
        "ruleset": VOICE_RULESET,
        "source_text": source,
        "generation_text": normalized,
        "surface_repairs": repairs,
        "semantic_groups": _semantic_groups(normalized),
        "pause_before_seconds": 0.12 if monologue else (0.08 if short_line else 0.04),
        "pause_after_seconds": 0.16 if short_line else (0.10 if monologue else 0.06),
        "breath_hint": "natural_breath_between_semantic_groups",
        "delivery_speed": "natural_buffered" if short_line else ("natural_continuous" if long_line else "natural"),
        "emotion": "light_controlled",
        "emotion_intensity": 0.35,
        "delivery": "生活化、语义清楚、轻重自然、保持音色一致",
        "avoid": ["播音腔", "朗读感", "机械均匀", "夸张表演", "刻意拖长尾音"],
        "filler_policy": "CONTEXTUAL_ONLY_PRESERVE_CORE_TEXT",
        "short_line_policy": "BUFFER_OR_CONTEXTUAL_FILLER_ONLY_AFTER_SCENE_DECISION",
        "long_line_policy": "KEEP_SEMANTIC_CONTINUITY_AND_AVOID_HARD_SPLIT",
        "risk_class": risk_class,
        "risk_flags": flags,
        "status": "PREFLIGHT_REVIEW_REQUIRED" if risk_class in {"A", "B", "C"} else "PREFLIGHT_PASS",
    }


def build_instruction(text: str, track_type: str = "DIALOGUE") -> tuple[str, dict[str, Any]]:
    contract = build_voice_contract(text, track_type)
    if str(track_type).upper() == "INNER_MONOLOGUE":
        direction = (
            "保持参考音频的音色与质感，女主角自然的低声内心独白；"
            "长句保持语义连贯，短句保留自然缓冲；像真实人在心里说话，"
            "轻声、生活化、带自然停顿和细微情绪；情绪淡而清楚，"
            "不要播音腔，不要朗读感，不要机械均匀，不要夸张表演，"
            "不要刻意拖长尾音。"
        )
    else:
        direction = (
            "保持参考音频的音色与质感，女主角生活化自然说话；"
            "长句保持连贯和语义分组，短句保留自然缓冲；"
            "必要时只在句首或句尾使用轻微自然衬字感，不改变核心台词；"
            "轻重缓急自然，情绪淡而清楚，吐字清楚但不刻意；"
            "不要播音腔，不要朗读感，不要机械均匀，"
            "不要夸张表演，不要刻意拖长尾音。"
        )
    prompt = DEFAULT_WRAPPER + direction + END_OF_PROMPT
    return prompt, contract


__all__ = ["VOICE_RULESET", "build_instruction", "build_voice_contract"]
