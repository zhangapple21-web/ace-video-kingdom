"""Validate Episode Dynamic Plan and Beat -> Shot linkage (read-only)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from content_control import DEGRADATION_LEVELS, validate_beat_shot_mapping
except ImportError:
    from tools.content_control import DEGRADATION_LEVELS, validate_beat_shot_mapping


def validate(plan: dict) -> dict:
    errors: list[str] = []
    dynamic = plan.get("dynamic_content_plan")
    if not isinstance(dynamic, dict):
        errors.append("dynamic_content_plan is missing")
        dynamic = {}
    mapping = validate_beat_shot_mapping(dynamic, plan.get("shots", []))
    errors.extend(mapping["errors"])
    control = plan.get("content_control") or {}
    state = control.get("content_state", "R0")
    if state not in DEGRADATION_LEVELS:
        errors.append(f"invalid content_state: {state}")
    if control.get("tech_route") in {"R0", "R1", "R2", "R3", "R4", "R5"}:
        errors.append("tech_route must be independent of content_state")
    for shot in plan.get("shots", []):
        if not isinstance(shot, dict):
            continue
        if shot.get("content_state") != state:
            errors.append(f"{shot.get('shot_id', 'UNKNOWN')} content_state does not match run")
        if not shot.get("beat_ids"):
            errors.append(f"{shot.get('shot_id', 'UNKNOWN')} has no beat_ids")
    return {
        "schema": "ace.video_kingdom.content_plan_validation.v1",
        "status": "PASS" if not errors else "FAIL",
        "verdict": "PASS" if not errors else "BLOCKED",
        "content_state": state,
        "tech_route": control.get("tech_route", "NORMAL"),
        "mapping": mapping,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate(json.loads(args.episode.read_text(encoding="utf-8")))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
