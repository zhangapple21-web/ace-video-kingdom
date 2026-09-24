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
    scene = contract.get("scene_state") if isinstance(contract.get("scene_state"), dict) else {}
    scene_id = str(scene.get("scene_id") or "").strip().upper()
    if not scene_id or scene_id in {"REQUIRED", "UNKNOWN", "N/A", "NONE"}:
        errors.append("state_contract.scene_state.scene_id must be a stable scene asset ID")
    for key in ("location", "time", "lighting", "space", "physical_layout", "interaction_surface"):
        value = str(scene.get(key) or "").strip().upper()
        if not value or value in {"REQUIRED", "UNKNOWN", "N/A", "NONE"}:
            errors.append(f"state_contract.scene_state.{key} must be concrete")
    scene_mode = str(scene.get("scene_mode") or "").strip().upper()
    if scene_mode != "LIVE_DIEGETIC_SPACE":
        errors.append("state_contract.scene_state.scene_mode must be LIVE_DIEGETIC_SPACE")
    scene_blob = " ".join(str(scene.get(key) or "") for key in ("location", "space", "physical_layout", "interaction_surface"))
    if any(token in scene_blob for token in ("风景画", "景观图", "纯背景", "唯美背景", "无人物空间")):
        errors.append("state_contract.scene_state must describe a playable diegetic space, not a scenic still")
    for key in ("start_pose", "primary_action", "emotion_start_end", "camera", "end_state"):
        value = str(shot.get(key) or "").strip().upper()
        if not value or value in {"REQUIRED", "UNKNOWN", "N/A", "NONE"}:
            errors.append(f"state_contract.shot_state.{key} must be concrete")
    action_blob = " ".join(str(shot.get(key) or "") for key in ("start_pose", "primary_action", "end_state"))
    if any(token in action_blob for token in ("不表现状态变化", "保持不变", "自然微动作", "轻微呼吸")):
        errors.append("state_contract.shot_state contains static/no-change performance language")
    if not isinstance(contract.get("approved_for_next_shot"), bool):
        errors.append("state_contract.approved_for_next_shot must be boolean")
    return {"status": "PASS" if not errors else "BLOCKED", "errors": errors}


__all__ = ["validate_state_contract"]
