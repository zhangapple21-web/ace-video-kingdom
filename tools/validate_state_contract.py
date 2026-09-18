"""Validate the explicit Identity/State/Scene State/Shot State boundary."""
from __future__ import annotations

from typing import Any


def validate_state_contract(contract: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return {"status": "BLOCKED", "errors": ["state_contract must be an object"]}
    if contract.get("schema") != "video_kingdom.state_contract.v1":
        errors.append("state_contract schema mismatch")
    if not str(contract.get("identity_ref") or "").strip():
        errors.append("state_contract.identity_ref is required")
    for layer in ("episode_state", "scene_state", "shot_state"):
        if not isinstance(contract.get(layer), dict) or not contract[layer]:
            errors.append(f"state_contract.{layer} is required")
    shot = contract.get("shot_state") if isinstance(contract.get("shot_state"), dict) else {}
    for key in ("start_pose", "primary_action", "emotion_start_end", "camera", "end_state"):
        value = str(shot.get(key) or "").strip().upper()
        if not value or value in {"REQUIRED", "UNKNOWN", "N/A", "NONE"}:
            errors.append(f"state_contract.shot_state.{key} must be concrete")
    if not isinstance(contract.get("approved_for_next_shot"), bool):
        errors.append("state_contract.approved_for_next_shot must be boolean")
    return {"status": "PASS" if not errors else "BLOCKED", "errors": errors}


__all__ = ["validate_state_contract"]
