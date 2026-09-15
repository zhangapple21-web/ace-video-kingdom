"""Validate Coze-derived script executability rules against a compiled plan.

Checks five contracts extracted from 《AI 短剧制作完整工作流》 plus the medium lock:

1. signed medium_lock (story material is not the finished video medium)
2. persona_card on each character dossier / asset package
3. five-segment shot prompt (风格基准/起始空间/底声/分时序动作/余韵)
4. narrative causal self-check (Q1-Q5) sitting on premise/causal_chain/plants/payoffs
5. structured continuity_bridge (previous end frame, exit/enter, inherited state)

Severity:
- blocked  -> hard_failures  (unsigned medium_lock, UI-medium language mismatch, prompt missing 主生成指令/禁止行为)
- rework   -> rework         (missing persona / five-segment / causal / bridge fields)
- never promote plan-only REWORK into BLOCKED

A string continuity_bridge remains truthy for validate_episode_quality.py; this
validator reports it as rework, not blocked.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from medium_lock import validate_medium_lock
    from validate_shot_prompt import validate_prompt
except ImportError:  # support ``python -m tools.validate_script_executability``
    from tools.medium_lock import validate_medium_lock
    from tools.validate_shot_prompt import validate_prompt


ROOT = Path(__file__).resolve().parents[1]
CHECKLIST_PATH = ROOT / "assets" / "checklists" / "script_executability.v1.json"
CAUSAL_IDS = ("Q1_CAUSE", "Q2_INFO_PAYOFF", "Q3_HOOK_3S", "Q4_TURN_30S", "Q5_ENDING_HOOK")
CAUSAL_QUESTIONS = {
    "Q1_CAUSE": "每一场戏的发生，是否被上一场已经发生的事实逼出来，而不是作者突然安排？",
    "Q2_INFO_PAYOFF": "观众在这一镜新知道的信息，是否在后续有兑现（plants 对得上 payoffs）？",
    "Q3_HOOK_3S": "开场 3 秒内是否有钩子，能拦住划走？",
    "Q4_TURN_30S": "30 秒内是否出现转折（验证失败、代价出现或关系翻转）？",
    "Q5_ENDING_HOOK": "本集结尾是否留下强钩子，迫使下一集被点开？",
}
PERSONA_FIELDS = (
    "appearance", "personality", "motivation", "catchphrase",
    "voice_lock", "costume_lock", "makeup_sheet",
)
PROMPT_SEGMENTS = ("style_baseline", "opening_space", "underscore", "timed_action", "aftertaste")
PROMPT_LABELS = ("风格基准", "起始空间", "底声", "分时序动作", "余韵")
TXT_ELEMENTS = ("subject", "action", "environment", "lighting", "camera", "style")
DIRECTION_ENUM = {"left", "right", "up", "down", "toward_camera", "away", "hold", "none"}
OPPOSITE = {
    "left": "right",
    "right": "left",
    "up": "down",
    "down": "up",
    "toward_camera": "away",
    "away": "toward_camera",
}
INHERIT_KEYS = {
    "costume", "prop_state", "eyeline", "lighting_direction",
    "spatial_position", "weather_time", "identity",
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and not value.strip().startswith("【")
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _persona_errors(card: Any, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(card, dict):
        return [f"{label}: persona_card missing"]
    if card.get("schema") not in (None, "video_kingdom.persona_card.v1"):
        errors.append(f"{label}: persona_card.schema mismatch")
    for field in PERSONA_FIELDS:
        if not _nonempty(card.get(field)):
            errors.append(f"{label}: persona_card.{field} empty")
    sheet = card.get("makeup_sheet") if isinstance(card.get("makeup_sheet"), dict) else {}
    if sheet.get("naming_rule") != "{character_id}_{expression}_{angle}":
        errors.append(f"{label}: makeup_sheet.naming_rule must be {{character_id}}_{{expression}}_{{angle}}")
    views = sheet.get("required_views") if isinstance(sheet.get("required_views"), list) else []
    if len(views) < 2:
        errors.append(f"{label}: makeup_sheet.required_views needs front+side at minimum")
    expressions = sheet.get("required_expressions") if isinstance(sheet.get("required_expressions"), list) else []
    if len([item for item in expressions if _nonempty(item)]) < 3:
        errors.append(f"{label}: makeup_sheet.required_expressions needs >=3")
    return errors


def _prompt_errors(shot: dict[str, Any], shot_id: str) -> tuple[list[str], list[str]]:
    blocked: list[str] = []
    rework: list[str] = []
    prompt = str(shot.get("prompt") or "")
    if "主生成指令" not in prompt or "禁止行为" not in prompt:
        blocked.append(f"{shot_id}: prompt missing 主生成指令/禁止行为")
    structured = shot.get("shot_prompt")
    if not isinstance(structured, dict):
        rework.append(f"{shot_id}: shot_prompt object missing")
        structured = {}
    for field in PROMPT_SEGMENTS:
        if not _nonempty(structured.get(field)):
            rework.append(f"{shot_id}: shot_prompt.{field} empty")
    for label in PROMPT_LABELS:
        if label not in prompt:
            rework.append(f"{shot_id}: compiled prompt missing label {label}")
    elements = structured.get("txt_prompt_elements") if isinstance(structured.get("txt_prompt_elements"), dict) else {}
    for key in TXT_ELEMENTS:
        if not _nonempty(elements.get(key)):
            rework.append(f"{shot_id}: txt_prompt_elements.{key} empty")
    lint = validate_prompt({
        "compiled_prompt": prompt,
        "txt_prompt_elements": elements,
        "style_lock": structured.get("style_lock"),
        "scene_lock": structured.get("scene_lock"),
        "subject_lock": structured.get("subject_lock"),
        "count_constraints": structured.get("count_constraints"),
        "negative_constraints": structured.get("negative_constraints"),
        "visual_mode": shot.get("visual_mode"),
        "strict_locks": False,
    })
    for error in lint["errors"]:
        if error.startswith("forbidden UI term"):
            blocked.append(f"{shot_id}: {error}")
        elif error not in rework:
            rework.append(f"{shot_id}: prompt lint: {error}")
    return blocked, rework


def _bridge_errors(bridge: Any, shot_id: str) -> list[str]:
    if isinstance(bridge, str) and bridge.strip():
        return [f"{shot_id}: continuity_bridge is a legacy string; compile structured video_kingdom.continuity_bridge.v1"]
    if not isinstance(bridge, dict):
        return [f"{shot_id}: continuity_bridge missing"]
    errors: list[str] = []
    if not _nonempty(bridge.get("previous_end_frame_state")):
        errors.append(f"{shot_id}: previous_end_frame_state empty")
    exit_dir = bridge.get("exit_direction")
    enter_dir = bridge.get("enter_direction")
    if exit_dir not in DIRECTION_ENUM:
        errors.append(f"{shot_id}: exit_direction invalid")
    if enter_dir not in DIRECTION_ENUM:
        errors.append(f"{shot_id}: enter_direction invalid")
    items = bridge.get("inherited_state_items") if isinstance(bridge.get("inherited_state_items"), list) else []
    if len(items) < 3:
        errors.append(f"{shot_id}: inherited_state_items needs >=3")
    else:
        for item in items:
            if not isinstance(item, dict) or item.get("key") not in INHERIT_KEYS or not _nonempty(item.get("value")):
                errors.append(f"{shot_id}: inherited_state_items entry invalid")
                break
    return errors


def _pair_direction_errors(shots: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for index, shot in enumerate(shots):
        if index + 1 >= len(shots):
            break
        current = shot.get("continuity_bridge")
        nxt = shots[index + 1].get("continuity_bridge")
        if not isinstance(current, dict) or not isinstance(nxt, dict):
            continue
        exit_dir = current.get("exit_direction")
        enter_dir = nxt.get("enter_direction")
        if exit_dir in {"hold", "none"} or enter_dir in {"hold", "none"}:
            continue
        expected = OPPOSITE.get(str(exit_dir))
        if expected and enter_dir != expected:
            errors.append(
                f"{shot.get('shot_id')}: exit_direction={exit_dir} must pair with next enter_direction={expected}"
            )
    return errors


def _causal_errors(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    check = plan.get("narrative_causal_self_check")
    if not isinstance(check, dict):
        return ["narrative_causal_self_check missing"]
    if check.get("rhythm_rule") != "3秒钩子、30秒转折、每集结尾强钩子":
        errors.append("rhythm_rule must be 3秒钩子、30秒转折、每集结尾强钩子")
    answers = check.get("answers") if isinstance(check.get("answers"), list) else []
    by_id = {row.get("id"): row for row in answers if isinstance(row, dict)}
    for qid in CAUSAL_IDS:
        row = by_id.get(qid)
        if not isinstance(row, dict):
            errors.append(f"{qid} missing")
            continue
        if not _nonempty(row.get("answer")) or not _nonempty(row.get("evidence")):
            errors.append(f"{qid} answer/evidence empty")
        if row.get("pass") is not True:
            errors.append(f"{qid} not marked pass")
    if not plan.get("premise"):
        errors.append("root.premise empty")
    if not plan.get("causal_chain"):
        errors.append("root.causal_chain empty")
    if not plan.get("plants"):
        errors.append("root.plants empty")
    if not plan.get("payoffs"):
        errors.append("root.payoffs empty")
    return errors


def collect_persona_cards(plan: dict[str, Any], project_dir: Path | None) -> list[tuple[str, Any]]:
    cards: list[tuple[str, Any]] = []
    seen: set[str] = set()
    assets = plan.get("assets") if isinstance(plan.get("assets"), dict) else {}
    for item in assets.get("characters") or []:
        if not isinstance(item, dict):
            continue
        asset_id = str(item.get("asset_id") or "CHAR")
        if isinstance(item.get("persona_card"), dict):
            cards.append((asset_id, item["persona_card"]))
            seen.add(asset_id)
            continue
        dossier_value = item.get("dossier_path")
        if project_dir and dossier_value:
            dossier_path = (project_dir / str(dossier_value)).resolve()
            if dossier_path.is_file():
                try:
                    dossier = _load(dossier_path)
                except (OSError, json.JSONDecodeError):
                    cards.append((asset_id, None))
                    seen.add(asset_id)
                    continue
                cards.append((asset_id, dossier.get("persona_card")))
                seen.add(asset_id)
                continue
        cards.append((asset_id, None))
        seen.add(asset_id)
    if project_dir:
        for path in sorted((project_dir / "assets").glob("*_dossier.json")):
            try:
                dossier = _load(path)
            except (OSError, json.JSONDecodeError):
                continue
            character_id = str(dossier.get("character_id") or path.stem)
            if character_id in seen:
                continue
            cards.append((character_id, dossier.get("persona_card")))
    if not cards:
        cards.append(("CHAR_UNKNOWN", plan.get("persona_card")))
    return cards


def validate(plan: dict[str, Any], *, project_dir: Path | None = None) -> dict[str, Any]:
    hard_failures: list[str] = []
    rework: list[str] = []
    hard_failures.extend(validate_medium_lock(plan))
    shots = plan.get("shots") if isinstance(plan.get("shots"), list) else []
    if not shots:
        rework.append("plan has no shots")

    for label, card in collect_persona_cards(plan, project_dir):
        rework.extend(_persona_errors(card, label))

    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            rework.append(f"shot {index} is not an object")
            continue
        shot_id = str(shot.get("shot_id") or index)
        blocked, prompt_rework = _prompt_errors(shot, shot_id)
        hard_failures.extend(blocked)
        rework.extend(prompt_rework)
        rework.extend(_bridge_errors(shot.get("continuity_bridge"), shot_id))
    rework.extend(_pair_direction_errors([shot for shot in shots if isinstance(shot, dict)]))
    rework.extend(_causal_errors(plan))

    if hard_failures:
        verdict = "BLOCKED"
    elif rework:
        verdict = "REWORK"
    else:
        verdict = "READY"
    return {
        "schema": "video_kingdom.script_executability_receipt.v1",
        "verdict": verdict,
        "hard_failures": hard_failures,
        "rework": rework,
        "shot_count": len(shots),
        "rhythm_rule": "3秒钩子、30秒转折、每集结尾强钩子",
        "checklist": str(CHECKLIST_PATH.relative_to(ROOT).as_posix()) if CHECKLIST_PATH.is_file() else None,
    }


def compile_shot_prompt(
    *,
    main_generation_instruction: str,
    identity_lock: str,
    first_state: str,
    action: str,
    last_state: str,
    forbidden: list[str],
    setting_hint: str,
    visual_hint: str,
    style_baseline: str,
    opening_space: str,
    underscore: str,
    timed_action: str,
    aftertaste: str,
    txt_prompt_elements: dict[str, str],
) -> tuple[str, dict[str, Any]]:
    """Compile the five-segment object plus the provider-facing prompt string."""
    structured = {
        "schema": "video_kingdom.shot_prompt_template.v1",
        "style_baseline": style_baseline,
        "opening_space": opening_space,
        "underscore": underscore,
        "timed_action": timed_action,
        "aftertaste": aftertaste,
        "txt_prompt_elements": txt_prompt_elements,
    }
    prompt = (
        f"主生成指令：{main_generation_instruction}。"
        f"角色身份锁：{identity_lock}。"
        f"风格基准：{style_baseline}。"
        f"起始空间：{opening_space}。"
        f"底声：{underscore}。"
        f"分时序动作：{timed_action}。"
        f"余韵：{aftertaste}。"
        f"当前镜头合同：首态={first_state}；唯一主要视觉事件={action}；末态={last_state}；"
        "固定机位，镜头内部不切换。"
        f"禁止行为：{'；'.join(forbidden)}。"
        f"场景细节：{setting_hint}，{visual_hint}，竖屏9:16。"
    )
    return prompt, structured


def compile_continuity_bridge(
    *,
    from_shot: str,
    to_shot: str | None,
    label: str,
    previous_end_frame_state: str,
    next_initial_state: str,
    exit_direction: str,
    enter_direction: str,
    inherited_state_items: list[dict[str, str]],
    camera_state: str = "继承上一镜摄影机高度、方向、焦段感和运动速度",
    lighting_state: str = "继承上一镜主光方向、色温、曝光和天气",
    tail_frame_state: str = "继承上一镜末态的主体位置、动作阶段和视线",
    terminal: bool = False,
) -> dict[str, Any]:
    return {
        "schema": "video_kingdom.continuity_bridge.v1",
        "status": "TERMINAL" if terminal else "PENDING_FRAME_PROOF",
        "from_shot": from_shot,
        "to_shot": to_shot,
        "label": label,
        "previous_end_frame_state": previous_end_frame_state,
        "next_initial_state": next_initial_state,
        "exit_direction": exit_direction,
        "enter_direction": enter_direction,
        "inherited_state_items": inherited_state_items,
        "camera_state": camera_state,
        "lighting_state": lighting_state,
        "tail_frame_state": tail_frame_state,
        "frame_proof_status": "TERMINAL" if terminal else "PENDING",
        "invariants": ["服装不变", "身份不变", "轴线不变"],
        "evidence_basis": "compiled state transition; post-generation frame proof pending",
    }


def compile_persona_card(character_id: str, name: str, role: str) -> dict[str, Any]:
    return {
        "schema": "video_kingdom.persona_card.v1",
        "character_id": character_id,
        "name": name,
        "role": role,
        "appearance": f"原创虚构角色 {name}；东亚面部比例自然；年龄段与发型在本项目内固定",
        "personality": "先观察再行动；不靠口号代替表演",
        "motivation": "把可验证的记录带离当前席位",
        "catchphrase": "先记下来。",
        "voice_lock": f"VOICE_{character_id}_V1",
        "costume_lock": "深色无品牌无文字层装；全剧不得更换核心服装",
        "makeup_sheet": {
            "naming_rule": "{character_id}_{expression}_{angle}",
            "required_views": [
                {"angle": "front", "expression": "neutral", "required": True},
                {"angle": "side", "expression": "neutral", "required": True},
            ],
            "required_expressions": ["neutral", "tension", "reaction"],
        },
    }


def compile_causal_self_check(plan: dict[str, Any]) -> dict[str, Any]:
    shots = plan.get("shots") if isinstance(plan.get("shots"), list) else []
    first = shots[0] if shots and isinstance(shots[0], dict) else {}
    mid = shots[3] if len(shots) > 3 and isinstance(shots[3], dict) else (shots[-1] if shots and isinstance(shots[-1], dict) else {})
    last = shots[-1] if shots and isinstance(shots[-1], dict) else {}
    chain = plan.get("causal_chain") or []
    plants = plan.get("plants") or []
    payoffs = plan.get("payoffs") or []
    answers = [
        {
            "id": "Q1_CAUSE",
            "question": CAUSAL_QUESTIONS["Q1_CAUSE"],
            "answer": " → ".join(str(item) for item in chain) or "处境建立后被异常逼出验证",
            "pass": bool(chain),
            "evidence": "causal_chain",
        },
        {
            "id": "Q2_INFO_PAYOFF",
            "question": CAUSAL_QUESTIONS["Q2_INFO_PAYOFF"],
            "answer": f"plants={plants}; payoffs={payoffs}",
            "pass": bool(plants) and bool(payoffs),
            "evidence": "plants/payoffs",
        },
        {
            "id": "Q3_HOOK_3S",
            "question": CAUSAL_QUESTIONS["Q3_HOOK_3S"],
            "answer": str(first.get("action") or first.get("information_gain") or ""),
            "pass": bool(first.get("action") or first.get("information_gain")),
            "evidence": str(first.get("shot_id") or "S01A"),
        },
        {
            "id": "Q4_TURN_30S",
            "question": CAUSAL_QUESTIONS["Q4_TURN_30S"],
            "answer": str(mid.get("action") or mid.get("dramatic_function") or ""),
            "pass": bool(mid.get("action") or mid.get("dramatic_function")),
            "evidence": str(mid.get("shot_id") or "S04A"),
        },
        {
            "id": "Q5_ENDING_HOOK",
            "question": CAUSAL_QUESTIONS["Q5_ENDING_HOOK"],
            "answer": str(last.get("last_state") or last.get("information_gain") or ""),
            "pass": bool(last.get("last_state") or last.get("information_gain")),
            "evidence": str(last.get("shot_id") or "S06A"),
        },
    ]
    return {
        "schema": "video_kingdom.narrative_causal_self_check.v1",
        "rhythm_rule": "3秒钩子、30秒转折、每集结尾强钩子",
        "answers": answers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, help="episode_plan.json; omit to validate blank templates")
    parser.add_argument("--project-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.plan:
        plan = _load(args.plan)
        project_dir = args.project_dir or args.plan.parent
        receipt = validate(plan, project_dir=project_dir)
    else:
        receipt = {
            "schema": "video_kingdom.script_executability_receipt.v1",
            "verdict": "TEMPLATES_ONLY",
            "hard_failures": [],
            "rework": [],
            "templates": [
                "assets/templates/persona_card.v1.json",
                "assets/templates/character_asset_package.v1.json",
                "assets/templates/shot_prompt_template.v1.json",
                "assets/templates/continuity_bridge.v1.json",
                "assets/templates/narrative_causal_self_check.v1.json",
                "assets/templates/medium_lock.v1.json",
            ],
            "checklist": "assets/checklists/script_executability.v1.json",
            "rule": "Fill templates then re-run with --plan.",
        }
    payload = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if receipt.get("verdict") == "BLOCKED":
        return 3
    if receipt.get("verdict") == "REWORK":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
