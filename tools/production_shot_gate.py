"""Default production gate for every video shot provider request.

The gate is intentionally small and deterministic.  It sits at the provider
adapter boundary so a caller cannot accidentally skip the director prompt,
continuity, or spatial preflight checks merely by invoking a lower-level
wrapper.
"""

from __future__ import annotations

from typing import Any

from tools.validate_continuity_bridge import validate_bridge
from tools.validate_creative_constraints import validate_creative_constraints
from tools.validate_director_manifest import validate_manifest as validate_director_manifest
from tools.validate_shot_prompt import validate_prompt
from tools.validate_shot_rhythm import validate_shot_rhythm
from tools.validate_script_prompt_review import validate_script_prompt_review
from tools.validate_new_drama_semantics import is_new_drama, validate_new_drama_semantics


def validate_production_shot(canonical_shot: dict[str, Any], contract_prompt: str) -> dict[str, Any]:
    """Validate mandatory production checks before a provider request.

    ``legacy`` and ``research`` calls deliberately do not use this function;
    they are non-deliverable scopes.  Production calls must supply the same
    structured packet used by the video-kingdom workflow.
    """

    new_drama_check = None
    if is_new_drama(canonical_shot):
        new_drama_check = validate_new_drama_semantics(canonical_shot, enforce=True)
        if new_drama_check["status"] != "PASS":
            raise ValueError("new drama semantics failed: " + ";".join(new_drama_check["errors"]))

    creative_check = validate_creative_constraints(canonical_shot.get("creative_constraints"))
    if creative_check["status"] != "PASS":
        raise ValueError("creative constraints failed: " + ";".join(creative_check["errors"]))

    review_check = validate_script_prompt_review(
        canonical_shot.get("script_prompt_review"),
        shot_id=str(canonical_shot.get("shot_id") or ""),
        run_id=str(canonical_shot.get("run_id") or ""),
        compiled_prompt=contract_prompt,
    )
    if review_check["status"] != "PASS":
        raise ValueError("script/prompt review failed: " + ";".join(review_check["errors"]))

    shot_prompt = canonical_shot.get("shot_prompt")
    shot_prompt = shot_prompt if isinstance(shot_prompt, dict) else {}
    prompt_check = validate_prompt(
        {
            "compiled_prompt": contract_prompt,
            "txt_prompt_elements": shot_prompt.get("txt_prompt_elements", {}),
            "style_lock": shot_prompt.get("style_lock"),
            "scene_lock": shot_prompt.get("scene_lock"),
            "subject_lock": shot_prompt.get("subject_lock"),
            "count_constraints": shot_prompt.get("count_constraints", []),
            "negative_constraints": shot_prompt.get("negative_constraints", []),
            "visual_mode": canonical_shot.get("visual_mode"),
            "strict_locks": True,
        }
    )
    if prompt_check["status"] != "PASS":
        raise ValueError("director locks failed: " + ";".join(prompt_check["errors"]))

    continuity = canonical_shot.get("continuity_bridge")
    if not isinstance(continuity, dict):
        raise ValueError("structured continuity_bridge is required for production")
    continuity_check = validate_bridge(continuity)
    if continuity_check["status"] != "PASS":
        raise ValueError("continuity bridge failed: " + ";".join(continuity_check["errors"]))

    director_check = validate_director_manifest({"shots": [canonical_shot]}, strict=True)
    if director_check["status"] != "PASS":
        raise ValueError("director preflight failed: " + ";".join(director_check["errors"]))

    rhythm_packet = canonical_shot.get("shot_rhythm")
    if not isinstance(rhythm_packet, dict):
        raise ValueError("shot rhythm contract missing: attach assets/templates/shot_rhythm_contract.v1.json before provider submission")
    rhythm_check = validate_shot_rhythm(rhythm_packet)
    if rhythm_check["status"] == "BLOCKED":
        raise ValueError("shot rhythm contract failed: " + ";".join(rhythm_check["errors"]))
    # A production drama shot must contain a watchable event.  The rhythm
    # validator keeps legacy poison phrases as warnings for audit-only and
    # historical packets, but the provider boundary must reject the explicit
    # MCUSTATIC/id-photo pattern that repeatedly produced audio-backed stills.
    static_packet = " ".join(
        str(value or "")
        for value in (
            canonical_shot.get("shot_id"),
            contract_prompt,
            rhythm_packet.get("movement"),
            rhythm_packet.get("camera_motion_reason"),
        )
    ).upper()
    static_poison = (
        "MCUSTATIC", "证件照", "自然微动作", "轻微呼吸", "同一帧", "同一位置同一景别",
        "循环静止", "重复帧", "无动作",
    )
    if any(phrase in static_packet for phrase in static_poison):
        raise ValueError(
            "production shot rejected: static/id-photo framing is not a watchable video event; "
            "rewrite with a named action, listener reaction, or motivated camera change"
        )

    return {
        "status": "PASS",
        "creative": creative_check,
        "script_prompt_review": review_check,
        "prompt": prompt_check,
        "continuity": continuity_check,
        "director": director_check,
        "rhythm": rhythm_check,
        "new_drama": new_drama_check,
    }
