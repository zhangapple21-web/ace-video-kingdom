"""Deterministic checks for director prompt locks.

This is a lint gate, not a prompt generator. It catches the common external-
skill failures (style drift, subject loss, count drift and accidental UI text)
before a provider request is admitted. The camera/action warning heuristics
are adapted from the MIT-licensed Director Skills prompt lint pattern; this
module is an independent implementation and does not depend on that repo.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


LABELS = ("主体", "动作", "环境", "光线", "镜头", "风格")
UI_TERMS = ("微信", "聊天界面", "视频通话界面", "手机屏幕录制", "悬浮窗", "画中画", "chat ui", "phone screen")
EDIT_WORDS = ("切镜", "切换镜头", "转场", "蒙太奇", "jump cut", "cut to")
MOTION_GROUPS = {
    "camera": ("推", "拉", "摇", "移", "跟拍", "旋转", "zoom", "pan", "dolly", "tracking"),
    "subject": ("跑", "跳", "转身", "挥手", "拿起", "倒下", "奔跑"),
}


def validate_prompt(record: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    prompt = str(record.get("compiled_prompt") or "")
    elements = record.get("txt_prompt_elements") if isinstance(record.get("txt_prompt_elements"), dict) else {}
    for key in ("subject", "action", "environment", "lighting", "camera", "style"):
        if not str(elements.get(key) or "").strip():
            errors.append(f"missing txt_prompt_elements.{key}")
    strict_locks = bool(record.get("strict_locks", True))
    if strict_locks:
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
    if strict_locks and visual_mode != "UI_ANIMATION":
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
    if any(word in prompt.lower() for word in EDIT_WORDS):
        warnings.append("prompt contains an edit/cut instruction; keep one internal shot and move editing to assembly")
    camera_text = str(elements.get("camera") or prompt).lower()
    subject_text = str(elements.get("action") or prompt).lower()
    active_groups = [name for name, words in MOTION_GROUPS.items() if any(word in (camera_text if name == "camera" else subject_text) for word in words)]
    if len(active_groups) >= 2:
        warnings.append("camera and subject motion are both active; verify the primary visual event independently")
    return {"status": "PASS" if not errors else "BLOCKED", "errors": errors, "warnings": warnings, "checks": {"style_lock": bool(expected_style), "scene_lock": bool(scene_lock), "subject_lock": bool(subject_lock), "count_constraints": len(count_constraints), "negative_constraints": len(record.get("negative_constraints", []) or [])}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    result = validate_prompt(json.loads(args.input.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
