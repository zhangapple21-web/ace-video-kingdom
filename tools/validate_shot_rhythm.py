"""Validate the generic shot rhythm and professional annotation contract."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

SCALES = {"wide", "medium", "close", "detail", "extreme_close"}
ANNOTATIONS = ("action", "dialogue", "emotion", "subtext", "motivation", "atmosphere")
PERFORMANCE = ("speaker_hands_body", "listener_reaction", "pause_point", "inner_voice_mouth_state", "cut_motivation")

def _blank(v: Any) -> bool:
    return v is None or v == "" or v == [] or v == {}

def validate_shot_rhythm(shot: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []; warnings: list[str] = []
    rhythm = shot.get("shot_rhythm") if isinstance(shot.get("shot_rhythm"), dict) else shot
    if rhythm.get("schema") and rhythm.get("schema") != "video_kingdom.shot_rhythm_contract.v1":
        errors.append("shot_rhythm schema mismatch")
    for key in ("shot_purpose", "scale", "transition_intent"):
        if _blank(rhythm.get(key)): errors.append(f"missing {key}")
    if rhythm.get("scale") and str(rhythm["scale"]).lower() not in SCALES:
        errors.append(f"unsupported scale: {rhythm['scale']}")
    annotations = rhythm.get("script_annotations") if isinstance(rhythm.get("script_annotations"), dict) else {}
    for key in ANNOTATIONS:
        if _blank(annotations.get(key)): errors.append(f"missing script_annotations.{key}")
    beats = rhythm.get("performance_beats") if isinstance(rhythm.get("performance_beats"), dict) else {}
    for key in PERFORMANCE:
        if _blank(beats.get(key)): errors.append(f"missing performance_beats.{key}")
    movement = str(rhythm.get("movement") or "static").lower()
    if movement not in {"static", "none", "固定", "无"} and _blank(rhythm.get("movement_motivation")):
        errors.append("moving camera requires movement_motivation")
    if annotations.get("dialogue") not in (None, "", "不适用", "无") or annotations.get("inner_voice"):
        anchor = rhythm.get("audio_anchor")
        if _blank(anchor): errors.append("dialogue or inner voice requires audio_anchor")
    timing = str(rhythm.get("timing_basis") or "").upper()
    if timing and timing not in {"AUDIO_DRIVEN", "ACTION_DRIVEN", "PENDING"}:
        errors.append("timing_basis must be AUDIO_DRIVEN, ACTION_DRIVEN or PENDING")
    if rhythm.get("fixed_cut_seconds") is not None:
        warnings.append("fixed_cut_seconds is advisory; verify against measured audio and action")
    if rhythm.get("same_scale_duration_seconds", 0) and float(rhythm["same_scale_duration_seconds"]) > 8:
        warnings.append("same-scale duration exceeds advisory 8s; retain only if performance requires it")
    return {"status": "PASS" if not errors else "BLOCKED", "errors": errors, "warnings": warnings}

def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--input", type=Path, required=True)
    result = validate_shot_rhythm(json.loads(p.parse_args().input.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result["status"] == "PASS" else 2

if __name__ == "__main__": raise SystemExit(main())
