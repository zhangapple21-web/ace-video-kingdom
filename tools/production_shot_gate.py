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


def validate_production_shot(canonical_shot: dict[str, Any], contract_prompt: str) -> dict[str, Any]:
    """Validate mandatory production checks before a provider request.

    ``legacy`` and ``research`` calls deliberately do not use this function;
    they are non-deliverable scopes.  Production calls must supply the same
    structured packet used by the video-kingdom workflow.
    """

    creative_check = validate_creative_constraints(canonical_shot.get("creative_constraints"))
    if creative_check["status"] != "PASS":
        raise ValueError("creative constraints failed: " + ";".join(creative_check["errors"]))

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

    return {
        "status": "PASS",
        "creative": creative_check,
        "prompt": prompt_check,
        "continuity": continuity_check,
        "director": director_check,
    }
