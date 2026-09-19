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

from tools.validate_creative_constraints import validate_creative_constraints
from tools.validate_role_audit import validate_role_audit


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
        creative_constraints = shot.get("creative_constraints")
        if creative_constraints is None:
            (errors if strict else warnings).append(f"{shot_id}: creative_constraints envelope missing")
        else:
            creative_check = validate_creative_constraints(creative_constraints)
            if creative_check["status"] != "PASS":
                (errors if strict else warnings).extend(f"{shot_id}: {error}" for error in creative_check["errors"])
        role_audit = shot.get("role_audit") if isinstance(shot.get("role_audit"), dict) else None
        if role_audit is None:
            (errors if strict else warnings).append(f"{shot_id}: role_audit receipt missing")
        else:
            audit_check = validate_role_audit(role_audit)
            if audit_check["status"] != "PASS":
                (errors if strict else warnings).extend(f"{shot_id}: {error}" for error in audit_check["errors"])
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
        world = str(spatial.get("world_position") or "").strip()
        screen = str(spatial.get("screen_left_right") or "").strip()
        if world and screen and world == screen:
            warnings.append(f"{shot_id}: world_position copied as screen_left_right")
        if spatial.get("world_not_equal_screen") is False and world and screen:
            warnings.append(f"{shot_id}: world_not_equal_screen is false")
        if spatial.get("locked_shot_no_added_beats") is False:
            warnings.append(f"{shot_id}: locked shot added beats")
        if lighting.get("recompute_on_camera_change") is False:
            motion = str(camera.get("main_motion") or "")
            if motion and motion not in {"固定", "static", "none", "无"}:
                warnings.append(f"{shot_id}: camera changed but key light not marked for recompute")
        compile_order = shot.get("compile_order") if isinstance(shot.get("compile_order"), dict) else director.get("compile_order") if isinstance(director.get("compile_order"), dict) else {}
        if compile_order and compile_order.get("director_packet_before_prompt") is False:
            warnings.append(f"{shot_id}: compile_order inverted; fill director packet before prompt")
        knowledge = shot.get("knowledge_status") if isinstance(shot.get("knowledge_status"), dict) else {}
        if knowledge:
            mixed = set(map(str, knowledge.get("facts") or [])) & set(map(str, knowledge.get("assumptions") or []))
            if mixed:
                warnings.append(f"{shot_id}: facts and assumptions overlap")
        force = performance.get("force_and_contact")
        if force is not None and (force == "" or force == []):
            warnings.append(f"{shot_id}: performance.force_and_contact empty")
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
