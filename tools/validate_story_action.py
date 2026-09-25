"""Validate the story-bearing action layer of a new drama shot.

Technical completeness is not enough for a watchable short drama.  This gate
keeps actor performance, camera movement, and narrative change separate so a
contract cannot pass with only walking/standing/camera language.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


PLACEHOLDERS = {"", "unknown", "未知", "pending", "待补", "tbd", "none", "无"}
CAMERA_MARKERS = (
    "摄影机",
    "摄像机",
    "镜头",
    "跟拍",
    "推镜",
    "拉镜",
    "摇镜",
    "移镜",
    "运镜",
    "机位",
    "camera",
    "dolly",
    "pan",
    "zoom",
)
narrative_change_fields = ("dramatic_function", "visible_change", "visible_consequence")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _missing(value: Any) -> bool:
    text = _text(value).lower()
    return not text or text in PLACEHOLDERS or (text.startswith("【") and text.endswith("】"))


def validate_story_action_packet(packet: Any, *, enforce: bool = True) -> dict[str, Any]:
    """Return PASS/BLOCKED without authorizing a provider call."""
    if not enforce:
        return {"status": "SKIPPED", "errors": [], "warnings": []}
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(packet, Mapping):
        return {"status": "BLOCKED", "errors": ["story action packet must be an object"], "warnings": warnings}

    rhythm = packet.get("shot_rhythm") if isinstance(packet.get("shot_rhythm"), Mapping) else {}
    annotations = rhythm.get("script_annotations") if isinstance(rhythm.get("script_annotations"), Mapping) else {}
    beats = rhythm.get("performance_beats") if isinstance(rhythm.get("performance_beats"), Mapping) else {}

    for field in narrative_change_fields:
        if _missing(rhythm.get(field)):
            errors.append(f"shot_rhythm.{field} is required: describe what changes on screen")

    action = _text(annotations.get("action") or packet.get("action"))
    actor_action = _text(beats.get("speaker_hands_body"))
    listener = _text(beats.get("listener_reaction"))
    if _missing(action):
        errors.append("named actor action is required")
    if _missing(actor_action):
        errors.append("performance_beats.speaker_hands_body is required")
    if _missing(listener):
        errors.append("performance_beats.listener_reaction is required")

    for label, value in (("script_annotations.action", action), ("performance_beats.speaker_hands_body", actor_action)):
        lower = value.lower()
        hits = [marker for marker in CAMERA_MARKERS if marker.lower() in lower]
        if hits:
            errors.append(f"{label} mixes camera language ({','.join(hits)}); put camera movement in camera/photography only")

    dead_motion = ("自然微动作", "轻微呼吸", "保持不变", "无动作", "走来走去", "静止")
    for label, value in (("script_annotations.action", action), ("performance_beats.speaker_hands_body", actor_action)):
        if any(term in value for term in dead_motion):
            errors.append(f"{label} is non-dramatic placeholder motion; name a visible action and its consequence")

    # A pure transition is allowed only if its state change is explicit; it
    # cannot use camera movement as the only thing that happens.
    if "走" in action and _missing(rhythm.get("visible_consequence")):
        errors.append("walking/transition needs an explicit visible_consequence; movement alone is not a dramatic beat")

    status = "PASS" if not errors else "BLOCKED"
    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "production_authority": "NONE",
        "narrative_change_fields": list(narrative_change_fields),
    }


if __name__ == "__main__":
    raise SystemExit("Use validate_story_action_packet from the production gate")
