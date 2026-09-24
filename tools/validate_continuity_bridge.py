"""Validate camera, lighting and tail-to-head continuity metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED = ("previous_end_frame_state", "next_initial_state", "camera_state", "lighting_state", "tail_frame_state", "enter_direction", "exit_direction")
ASSET_KINDS = {"character", "scene", "prop", "clue", "ui_plate", "fx"}


def validate_bridge(bridge: dict[str, Any]) -> dict[str, Any]:
    errors = [f"missing {key}" for key in REQUIRED if not str(bridge.get(key) or "").strip()]
    if bridge.get("status") == "READY" and bridge.get("frame_proof_status") != "VERIFIED":
        errors.append("READY bridge requires frame_proof_status=VERIFIED")
    if bridge.get("from_shot") and bridge.get("to_shot") and bridge["from_shot"] == bridge["to_shot"]:
        errors.append("from_shot and to_shot must differ")
    warnings: list[str] = []
    register = bridge.get("asset_register")
    if register is not None:
        if not isinstance(register, list):
            errors.append("asset_register must be a list")
        else:
            for index, item in enumerate(register):
                if not isinstance(item, dict):
                    errors.append(f"asset_register[{index}] must be an object")
                    continue
                for key in ("asset_id", "kind", "initial", "change", "final"):
                    if not str(item.get(key) or "").strip():
                        errors.append(f"asset_register[{index}].{key} missing")
                if item.get("kind") not in (None, "", *ASSET_KINDS):
                    errors.append(f"asset_register[{index}].kind must be one of {sorted(ASSET_KINDS)}")
    world = str(bridge.get("world_position") or "").strip()
    screen = str(bridge.get("screen_left_right") or "").strip()
    if world and screen and world == screen:
        warnings.append("world_position copied as screen_left_right")
    force = bridge.get("force_and_contact")
    if force is not None and not str(force).strip():
        warnings.append("force_and_contact is present but empty")
    if not str(bridge.get("scene_state") or "").strip():
        warnings.append("scene_state missing; default is dynamic Scene State (place/time/light/space), not a scene jpg library")
    return {"status": "PASS" if not errors else "BLOCKED", "errors": errors, "warnings": warnings, "camera_state": bridge.get("camera_state"), "lighting_state": bridge.get("lighting_state"), "frame_proof_status": bridge.get("frame_proof_status", "PENDING")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    result = validate_bridge(json.loads(args.input.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
