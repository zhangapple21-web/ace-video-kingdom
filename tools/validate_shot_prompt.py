"""Deterministic checks for director prompt locks.

This is a lint gate, not a prompt generator. It catches the common external-
skill failures (style drift, subject loss, count drift and accidental UI text)
before a provider request is admitted.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


LABELS = ("主体", "动作", "环境", "光线", "镜头", "风格")
UI_TERMS = ("微信", "聊天界面", "视频通话界面", "手机屏幕录制", "悬浮窗", "画中画", "chat ui", "phone screen")


def validate_prompt(record: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    prompt = str(record.get("compiled_prompt") or "")
    elements = record.get("txt_prompt_elements") if isinstance(record.get("txt_prompt_elements"), dict) else {}
    for key in ("subject", "action", "environment", "lighting", "camera", "style"):
        if not str(elements.get(key) or "").strip():
            errors.append(f"missing txt_prompt_elements.{key}")
    for label in LABELS:
        if label not in prompt:
            errors.append(f"compiled prompt missing label {label}")
    expected_style = str(record.get("style_lock") or "").strip()
    if expected_style and expected_style not in prompt:
        errors.append("style_lock not present in compiled prompt")
    scene_lock = str(record.get("scene_lock") or "").strip()
    if scene_lock and scene_lock not in prompt:
        errors.append("scene_lock not present in compiled prompt")
    subject_lock = str(record.get("subject_lock") or "").strip()
    if subject_lock and subject_lock not in prompt:
        errors.append("subject_lock not present in compiled prompt")
    for constraint in record.get("negative_constraints", []) or []:
        if str(constraint).strip() and str(constraint) not in prompt:
            errors.append(f"negative constraint missing: {constraint}")
    visual_mode = str(record.get("visual_mode") or "FILM_NARRATIVE").upper()
    if visual_mode != "UI_ANIMATION":
        for term in UI_TERMS:
            if term.lower() in prompt.lower():
                errors.append(f"forbidden UI term in non-UI prompt: {term}")
    count_constraints = record.get("count_constraints") if isinstance(record.get("count_constraints"), list) else []
    for item in count_constraints:
        if isinstance(item, dict):
            entity = str(item.get("entity") or "").strip()
            count = item.get("count")
            if entity and count is not None and not re.search(rf"{re.escape(entity)}[^。\n]{{0,40}}{re.escape(str(count))}", prompt):
                errors.append(f"count constraint missing: {entity}={count}")
    return {"status": "PASS" if not errors else "BLOCKED", "errors": errors, "checks": {"style_lock": bool(expected_style), "scene_lock": bool(scene_lock), "subject_lock": bool(subject_lock), "count_constraints": len(count_constraints), "negative_constraints": len(record.get("negative_constraints", []) or [])}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    result = validate_prompt(json.loads(args.input.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
