"""Validate the director-side shot packet before provider admission.

The checks are an independent implementation of the useful Director Skills
pattern: audit the source frame's space, subject path, camera path and light
before writing a generation prompt.  It never calls a provider.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SPATIAL_FIELDS = ("foreground", "midground", "background", "camera_start", "allowed_content", "forbidden_additions")
CAMERA_FIELDS = ("main_motion", "tracking_subject", "camera_end")
LIGHT_FIELDS = ("motivation", "key_source", "direction")
PERFORMANCE_FIELDS = (
    "speaker_action",
    "listener_expression",
    "pause_points",
    "monologue_mouth_state",
    "edit_intent",
)


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def validate_manifest(manifest: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    shots = manifest.get("shots") if isinstance(manifest.get("shots"), list) else []
    seen: set[str] = set()
    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            errors.append(f"row-{index}: shot must be an object")
            continue
        shot_id = str(shot.get("shot_id") or f"row-{index}")
        if shot_id in seen:
            errors.append(f"{shot_id}: duplicate shot_id")
        seen.add(shot_id)
        director = shot.get("director_preflight") if isinstance(shot.get("director_preflight"), dict) else {}
        required = ("story_goal", "duration_seconds", "source_frame")
        for key in required:
            if _empty(shot.get(key)):
                (errors if strict else warnings).append(f"{shot_id}: missing {key}")
        spatial = director.get("spatial_audit") if isinstance(director.get("spatial_audit"), dict) else {}
        camera = director.get("camera") if isinstance(director.get("camera"), dict) else {}
        lighting = director.get("lighting") if isinstance(director.get("lighting"), dict) else {}
        performance = director.get("performance") if isinstance(director.get("performance"), dict) else {}
        for key in SPATIAL_FIELDS:
            if _empty(spatial.get(key)):
                warnings.append(f"{shot_id}: spatial_audit.{key} missing")
        for key in CAMERA_FIELDS:
            if _empty(camera.get(key)):
                warnings.append(f"{shot_id}: camera.{key} missing")
        for key in LIGHT_FIELDS:
            if _empty(lighting.get(key)):
                warnings.append(f"{shot_id}: lighting.{key} missing")
        for key in ("exposure_lock", "white_balance_lock"):
            if lighting.get(key) is not True:
                warnings.append(f"{shot_id}: lighting.{key} not locked")
        for key in PERFORMANCE_FIELDS:
            if _empty(performance.get(key)):
                (errors if strict else warnings).append(f"{shot_id}: performance.{key} missing")
        if not spatial.get("subjects_present") and not spatial.get("allowed_entries"):
            warnings.append(f"{shot_id}: source frame has no subject and no allowed entry path")
        bridge = shot.get("continuity_bridge") if isinstance(shot.get("continuity_bridge"), dict) else {}
        if bridge and bridge.get("status") == "READY" and bridge.get("frame_proof_status") != "VERIFIED":
            errors.append(f"{shot_id}: READY continuity bridge lacks verified frame proof")
    return {
        "status": "BLOCKED" if errors else "PASS",
        "errors": errors,
        "warnings": warnings,
        "shot_count": len(shots),
        "strict": strict,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = validate_manifest(json.loads(args.manifest.read_text(encoding="utf-8")), strict=args.strict)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
