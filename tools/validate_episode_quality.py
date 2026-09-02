"""Validate the seven-layer short-drama quality contract.

EXPERIMENTAL plans receive a gap report; FORMAL plans fail closed.  This keeps
Free Zone exploration open while preventing an under-specified plan from being
mistaken for a production-ready episode.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


SHOT_FIELDS = ("dramatic_function", "information_gain", "emotion_change", "action_beats", "camera", "continuity_bridge", "audio_beats")
ROOT_FIELDS = ("premise", "causal_chain", "plants", "payoffs", "viewer_knowledge_checkpoints")


def validate(plan: dict) -> dict:
    mode = str(plan.get("quality_mode", "EXPERIMENTAL")).upper()
    if mode not in {"EXPERIMENTAL", "FORMAL"}:
        return {"status": "INVALID", "mode": mode, "errors": ["quality_mode must be EXPERIMENTAL or FORMAL"], "warnings": []}
    missing: list[str] = []
    for field in ROOT_FIELDS:
        value = plan.get(field)
        if not value or (isinstance(value, list) and not value):
            missing.append(f"root.{field}")
    shots = plan.get("shots") if isinstance(plan.get("shots"), list) else []
    if not shots:
        missing.append("root.shots")
    for index, shot in enumerate(shots, start=1):
        shot_id = shot.get("shot_id", f"shot_{index}") if isinstance(shot, dict) else f"shot_{index}"
        for field in SHOT_FIELDS:
            value = shot.get(field) if isinstance(shot, dict) else None
            if not value or (isinstance(value, list) and not value):
                missing.append(f"{shot_id}.{field}")
        beats = shot.get("action_beats") if isinstance(shot, dict) else None
        if isinstance(beats, list) and len(beats) != 3:
            missing.append(f"{shot_id}.action_beats must contain [start, action, end]")
        camera = shot.get("camera") if isinstance(shot, dict) else None
        if camera and isinstance(camera, dict):
            for field in ("scale", "movement", "axis"):
                if not camera.get(field):
                    missing.append(f"{shot_id}.camera.{field}")
    if mode == "FORMAL" and missing:
        return {"status": "INVALID", "mode": mode, "errors": missing, "warnings": []}
    warnings = [f"quality contract gap: {item}" for item in missing]
    return {"status": "VALID" if not missing else "EXPERIMENTAL_WITH_GAPS", "mode": mode, "errors": [], "warnings": warnings, "gap_count": len(missing)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate(json.loads(args.plan.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        result = {"status": "INVALID", "mode": "UNKNOWN", "errors": [str(exc)], "warnings": []}
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["status"] in {"VALID", "EXPERIMENTAL_WITH_GAPS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
