"""Episode-level content feasibility and monotonic degradation primitives.

This module is deliberately independent of provider routing.  Ratios and
duration are diagnostics; a content transition is only valid when there is
evidence that the narrative cannot reasonably fit the current plan.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any


DEGRADATION_LEVELS = ("R0", "R1", "R2", "R3", "R4", "R5")
REASON_CODES = {
    "REDUNDANT_DIALOGUE",
    "VISUALIZATION_SUBSTITUTION",
    "REDUNDANT_SHOT",
    "NON_CORE_SETUP_REMOVAL",
    "NARRATIVE_CORE_UNSATISFIABLE",
}
FAILURE_CLASSES = {"CONTENT_FAILURE", "TECHNICAL_FAILURE", "PROVIDER_FAILURE"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_episode_dynamic_plan(
    *, idea: str, plan: dict[str, Any], target_seconds: int | None = None
) -> dict[str, Any]:
    """Compile a traceable content plan from the existing episode plan."""
    shots = [shot for shot in plan.get("shots", []) if isinstance(shot, dict)]
    target = int(target_seconds or plan.get("render_defaults", {}).get("seconds", 6) * max(1, len(shots)))
    target = max(1, target)
    margin = max(4, round(target * 0.08))
    spine = plan.get("story", {}).get("root_brief", {})
    causal_chain = list(spine.get("mainline_events") or [])
    beats: list[dict[str, Any]] = []
    for index, shot in enumerate(shots, start=1):
        shot_id = str(shot.get("shot_id", f"S{index:02d}"))
        beat_id = f"BEAT-{index:02d}"
        dependencies = [f"BEAT-{index - 1:02d}"] if index > 1 else []
        beats.append(
            {
                "beat_id": beat_id,
                "purpose": shot.get("dramatic_function") or (causal_chain[index - 1] if index <= len(causal_chain) else "UNSPECIFIED"),
                "must_keep": index in (1, len(shots)) or bool(shot.get("information_gain")),
                "order": index,
                "dependencies": dependencies,
                "mapped_shots": [shot_id],
            }
        )
        shot.setdefault("beat_ids", []).append(beat_id)
    dialogue = [str(shot.get("information_gain") or "") for shot in shots]
    monologue = [str(shot.get("monologue_text") or "") for shot in shots if shot.get("monologue_text")]
    actions = [str(shot.get("action") or "") for shot in shots]
    dialogue_weight = sum(len(item) for item in dialogue)
    action_weight = sum(len(item) for item in actions)
    action_signal = bool(re.search(r"冲进|撞开|抢回|追上|奔跑|打碎|砸|拔刀|逃跑", idea))
    return {
        "episode_plan_version": "v1",
        "source_word_count": sum(1 for ch in idea if "\u4e00" <= ch <= "\u9fff") + len(re.findall(r"[A-Za-z0-9]+", idea)),
        "narrative_type": "ACTION_LED" if action_signal or action_weight > dialogue_weight else "DIALOGUE_LED",
        "target_seconds": target,
        "acceptable_duration_range": [max(1, target - margin), target + margin],
        "story_spine": {
            "conflict": [spine.get("relationship_and_conflict", "")],
            "turning_points": causal_chain[1:-1],
            "relationship_changes": [shot.get("emotion_change", "") for shot in shots if shot.get("emotion_change")],
            "ending_hook": causal_chain[-1:] or ["UNSPECIFIED"],
            "causal_dependencies": causal_chain,
        },
        "pacing_profile": {
            "dialogue": {"expected": dialogue, "role": "diagnostic"},
            "monologue": {"expected": monologue, "role": "diagnostic"},
            "action": {"expected": actions, "role": "diagnostic"},
        },
        "must_preserve": [beat["beat_id"] for beat in beats if beat["must_keep"]],
        "beats": beats,
    }


def initial_content_control() -> dict[str, Any]:
    return {
        "schema": "ace.video_kingdom.content_control.v1",
        "content_state": "R0",
        "tech_route": "NORMAL",
        "failure_class": None,
        "transition_authority": "CONTENT_FEASIBILITY_GATE_ONLY",
        "automatic_transition": False,
        "canonical_story_immutable": True,
        "lineage": [],
    }


def propagate_content_state(plan: dict[str, Any]) -> dict[str, Any]:
    """Copy run state and Beat identity into every Shot/sidecar record."""
    control = plan.setdefault("content_control", initial_content_control())
    state = control.get("content_state", "R0")
    lineage_ref = "content_control.v1.json"
    shot_beats = {
        str(shot.get("shot_id")): list(shot.get("beat_ids") or [])
        for shot in plan.get("shots", []) if isinstance(shot, dict)
    }
    for shot in plan.get("shots", []):
        if not isinstance(shot, dict):
            continue
        shot["content_state"] = state
        shot["content_lineage_ref"] = lineage_ref
    contract = plan.get("_six_module_contract")
    if isinstance(contract, dict):
        for shot in contract.get("shots", []):
            if not isinstance(shot, dict):
                continue
            shot_id = str(shot.get("shot_id", ""))
            shot["beat_ids"] = shot_beats.get(shot_id, list(shot.get("beat_ids") or []))
            shot["content_state"] = state
            shot["content_lineage_ref"] = lineage_ref
    return plan


def apply_content_transition(plan: dict[str, Any], to_level: str, **kwargs: Any) -> dict[str, Any]:
    """Apply an authorized transition and carry the new state into all Shots."""
    control = transition_content_state(plan.setdefault("content_control", initial_content_control()), to_level, **kwargs)
    state = control["content_state"]
    for shot in plan.get("shots", []):
        if isinstance(shot, dict):
            shot["content_state"] = state
            shot["content_lineage_ref"] = "content_control.v1.json"
    return plan


def evaluate_content_feasibility(
    dynamic_plan: dict[str, Any],
    *,
    actual_duration: float | None = None,
    repeated_information: bool = False,
    redundant_action: bool = False,
    unnecessary_pause: bool = False,
    missing_core_beats: list[str] | None = None,
    failure_class: str | None = None,
) -> dict[str, Any]:
    """Return a diagnostic verdict without silently changing content state."""
    if failure_class and failure_class not in FAILURE_CLASSES:
        raise ValueError(f"unknown failure class: {failure_class}")
    missing = list(missing_core_beats or [])
    if missing:
        verdict = "CONTENT_INCOMPLETE"
    elif failure_class == "TECHNICAL_FAILURE":
        verdict = "TECHNICAL_FAILURE"
    elif failure_class == "PROVIDER_FAILURE":
        verdict = "PROVIDER_FAILURE"
    else:
        low, high = dynamic_plan.get("acceptable_duration_range", [0, 0])
        over_budget = isinstance(actual_duration, (int, float)) and actual_duration > high
        has_redundancy = repeated_information or redundant_action or unnecessary_pause
        verdict = "CONTENT_DEGRADED" if over_budget and has_redundancy else "CONTENT_VALID"
    return {
        "schema": "ace.video_kingdom.content_feasibility.v1",
        "verdict": verdict,
        "content_failure": verdict in {"CONTENT_DEGRADED", "CONTENT_INCOMPLETE"},
        "failure_class": failure_class or ("CONTENT_FAILURE" if verdict in {"CONTENT_DEGRADED", "CONTENT_INCOMPLETE"} else None),
        "actual_duration": actual_duration,
        "acceptable_duration_range": dynamic_plan.get("acceptable_duration_range"),
        "diagnostics": {
            "repeated_information": bool(repeated_information),
            "redundant_action": bool(redundant_action),
            "unnecessary_pause": bool(unnecessary_pause),
            "missing_core_beats": missing,
            "ratio_role": "diagnostic_only",
        },
    }


def transition_content_state(
    control: dict[str, Any],
    to_level: str,
    *,
    reason: str,
    reason_code: str,
    changed_items: list[str] | None = None,
    preserved_beats: list[str] | None = None,
    removed_items: list[str] | None = None,
    impact: str = "UNKNOWN",
    failure_class: str = "CONTENT_FAILURE",
) -> dict[str, Any]:
    """Apply one monotonic content transition and append immutable lineage."""
    if to_level not in DEGRADATION_LEVELS:
        raise ValueError(f"invalid degradation level: {to_level}")
    if reason_code not in REASON_CODES:
        raise ValueError(f"invalid degradation reason_code: {reason_code}")
    if failure_class != "CONTENT_FAILURE":
        raise ValueError("only CONTENT_FAILURE may trigger content degradation")
    current = control.get("content_state", "R0")
    if current not in DEGRADATION_LEVELS:
        raise ValueError(f"invalid current degradation level: {current}")
    if control.get("terminal"):
        raise ValueError("R5 is terminal; start a new production run for another attempt")
    if DEGRADATION_LEVELS.index(to_level) <= DEGRADATION_LEVELS.index(current):
        raise ValueError(f"content degradation must be monotonic: {current} -> {to_level}")
    if to_level == "R5" and reason_code != "NARRATIVE_CORE_UNSATISFIABLE":
        raise ValueError("R5 requires NARRATIVE_CORE_UNSATISFIABLE")
    if to_level != "R5" and reason_code == "NARRATIVE_CORE_UNSATISFIABLE":
        raise ValueError("NARRATIVE_CORE_UNSATISFIABLE is reserved for R5")
    entry = {
        "from": current,
        "to": to_level,
        "reason": reason,
        "reason_code": reason_code,
        "changed_items": list(changed_items or []),
        "preserved_beats": list(preserved_beats or []),
        "removed_items": list(removed_items or []),
        "impact": impact,
        "timestamp": _now(),
    }
    control.setdefault("lineage", []).append(entry)
    control["content_state"] = to_level
    control["failure_class"] = failure_class
    if to_level == "R5":
        control["terminal"] = True
        control["terminal_reason"] = "REWRITE_REQUIRED"
    return control


def classify_route_failure(kind: str) -> str:
    """Map an explicit runtime failure to its class; never infer content loss."""
    normalized = str(kind).upper()
    if normalized in FAILURE_CLASSES:
        return normalized
    if normalized in {"PROVIDER", "HTTP", "QUOTA", "MODEL", "GENERATION"}:
        return "PROVIDER_FAILURE"
    if normalized in {"TECH", "MEDIA", "FFMPEG", "AUDIO", "CONTINUITY"}:
        return "TECHNICAL_FAILURE"
    if normalized in {"CONTENT", "NARRATIVE", "BUDGET", "OVERLOADED"}:
        return "CONTENT_FAILURE"
    return "TECHNICAL_FAILURE"


def validate_beat_shot_mapping(dynamic_plan: dict[str, Any], shots: list[dict[str, Any]]) -> dict[str, Any]:
    """Check that every declared beat has an ordered, extant Shot carrier."""
    errors: list[str] = []
    shot_ids = {str(shot.get("shot_id")) for shot in shots if shot.get("shot_id")}
    seen_orders: list[int] = []
    for beat in dynamic_plan.get("beats", []):
        if not isinstance(beat, dict):
            errors.append("beat is not an object")
            continue
        beat_id = str(beat.get("beat_id", "UNKNOWN"))
        mapped = beat.get("mapped_shots")
        if not isinstance(mapped, list) or not mapped:
            errors.append(f"{beat_id} has no mapped_shots")
        else:
            missing = [str(item) for item in mapped if str(item) not in shot_ids]
            errors.extend(f"{beat_id} maps to missing shot {item}" for item in missing)
        order = beat.get("order")
        if not isinstance(order, int):
            errors.append(f"{beat_id} order must be an integer")
        else:
            seen_orders.append(order)
        for dep in beat.get("dependencies", []) or []:
            if dep not in {str(item.get("beat_id")) for item in dynamic_plan.get("beats", []) if isinstance(item, dict)}:
                errors.append(f"{beat_id} depends on missing beat {dep}")
    if seen_orders != sorted(seen_orders):
        errors.append("beat order is not monotonic")
    return {
        "schema": "ace.video_kingdom.beat_shot_mapping.v1",
        "status": "PASS" if not errors else "FAIL",
        "beat_count": len(dynamic_plan.get("beats", [])),
        "shot_count": len(shots),
        "errors": errors,
    }


def build_post_diagnostics(
    dynamic_plan: dict[str, Any],
    *,
    actual_duration: float | None = None,
    dialogue_seconds: float | None = None,
    monologue_seconds: float | None = None,
    action_seconds: float | None = None,
    failure_class: str | None = None,
    repeated_information: bool = False,
    redundant_action: bool = False,
    unnecessary_pause: bool = False,
    missing_core_beats: list[str] | None = None,
) -> dict[str, Any]:
    """Create the post-production diagnostic receipt without a ratio hard gate."""
    feasibility = evaluate_content_feasibility(
        dynamic_plan,
        actual_duration=actual_duration,
        failure_class=failure_class,
        repeated_information=repeated_information,
        redundant_action=redundant_action,
        unnecessary_pause=unnecessary_pause,
        missing_core_beats=missing_core_beats,
    )
    total = sum(value for value in (dialogue_seconds, monologue_seconds, action_seconds) if isinstance(value, (int, float)))
    speech_rate = None
    if isinstance(dialogue_seconds, (int, float)) and dialogue_seconds > 0:
        speech_rate = {"dialogue_seconds": dialogue_seconds, "words_per_second": None}
    return {
        "schema": "ace.video_kingdom.post_production_diagnostics.v1",
        "classification": feasibility["verdict"],
        "actual_duration": actual_duration,
        "dialogue_seconds": dialogue_seconds,
        "monologue_seconds": monologue_seconds,
        "action_seconds": action_seconds,
        "measured_content_seconds": total or None,
        "speech_rate": speech_rate,
        "first_conflict_time": None,
        "mid_episode_information_change": None,
        "relationship_change": None,
        "ending_hook": None,
        "repeated_information": bool(repeated_information),
        "redundant_action": bool(redundant_action),
        "unnecessary_pause": bool(unnecessary_pause),
        "semantic_freeze": False,
        "ratio_policy": "diagnostic_only; never a standalone pass/fail gate",
        "feasibility": feasibility,
    }
