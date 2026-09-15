"""Validate camera, lighting and tail-to-head continuity metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED = ("previous_end_frame_state", "next_initial_state", "camera_state", "lighting_state", "tail_frame_state", "enter_direction", "exit_direction")


def validate_bridge(bridge: dict[str, Any]) -> dict[str, Any]:
    errors = [f"missing {key}" for key in REQUIRED if not str(bridge.get(key) or "").strip()]
    if bridge.get("status") == "READY" and bridge.get("frame_proof_status") != "VERIFIED":
        errors.append("READY bridge requires frame_proof_status=VERIFIED")
    if bridge.get("from_shot") and bridge.get("to_shot") and bridge["from_shot"] == bridge["to_shot"]:
        errors.append("from_shot and to_shot must differ")
    return {"status": "PASS" if not errors else "BLOCKED", "errors": errors, "camera_state": bridge.get("camera_state"), "lighting_state": bridge.get("lighting_state"), "frame_proof_status": bridge.get("frame_proof_status", "PENDING")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    result = validate_bridge(json.loads(args.input.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
