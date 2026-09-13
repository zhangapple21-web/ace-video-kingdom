import json
from pathlib import Path

from tools.medium_lock import character_performance_lock
from tools.validate_script_executability import (
    compile_causal_self_check,
    compile_continuity_bridge,
    compile_persona_card,
    compile_shot_prompt,
    validate,
)


ROOT = Path(__file__).resolve().parents[1]


def _filled_shot(shot_id: str = "S01A", *, prompt_ok: bool = True, bridge: object | None = None) -> dict:
    forbidden = ["不得新增人物"]
    prompt, shot_prompt = compile_shot_prompt(
        main_generation_instruction="只执行一个主要视觉事件",
        identity_lock="身份固定",
        first_state="稳定构图",
        action="按下回车",
        last_state="保留反应",
        forbidden=forbidden,
        setting_hint="深夜机房",
        visual_hint="抽象求救标记但不生成可读文字",
        style_baseline="竖屏9:16写实短剧",
        opening_space="深夜机房，CHAR_MAIN 中近景固定机位",
        underscore="机房底噪",
        timed_action="0-1s首态；按下回车；收势",
        aftertaste="保留反应交给下一镜",
        txt_prompt_elements={
            "subject": "CHAR_MAIN",
            "action": "按下回车",
            "environment": "深夜机房",
            "lighting": "屏幕冷光",
            "camera": "medium close-up, FIXED",
            "style": "写实短剧",
        },
    )
    if not prompt_ok:
        prompt = "一段没有硬合同的提示词"
    if bridge is None:
        bridge = compile_continuity_bridge(
            from_shot=shot_id,
            to_shot="S02A",
            label="SC01 -> S02A",
            previous_end_frame_state="动作完成后保留反应与留白",
            next_initial_state="下一镜首态",
            exit_direction="hold",
            enter_direction="hold",
            inherited_state_items=[
                {"key": "costume", "value": "深色无品牌层装", "source_shot": shot_id},
                {"key": "identity", "value": "CHAR_MAIN", "source_shot": shot_id},
                {"key": "spatial_position", "value": "机房记录台前", "source_shot": shot_id},
            ],
        )
    return {
        "shot_id": shot_id,
        "prompt": prompt,
        "shot_prompt": shot_prompt,
        "action": "按下回车",
        "last_state": "保留反应",
        "information_gain": "服务器还在跑",
        "dramatic_function": "建立处境",
        "continuity_bridge": bridge,
    }


def _filled_plan(**overrides) -> dict:
    shots = overrides.pop("shots", [_filled_shot("S01A"), _filled_shot("S02A")])
    plan = {
        "medium_lock": character_performance_lock(),
        "premise": "深夜发现代码里藏着求救",
        "causal_chain": ["处境建立", "异常显现"],
        "plants": ["矛盾记录"],
        "payoffs": ["证据脱离单一席位"],
        "assets": {
            "characters": [{
                "asset_id": "CHAR_MAIN",
                "persona_card": compile_persona_card("CHAR_MAIN", "主角", "观察者"),
            }]
        },
        "shots": shots,
    }
    plan["narrative_causal_self_check"] = compile_causal_self_check(plan)
    plan.update(overrides)
    return plan


def test_templates_and_checklist_exist():
    for rel in (
        "assets/schema/persona_card.v1.json",
        "assets/schema/character_asset_package.v1.json",
        "assets/schema/shot_prompt_template.v1.json",
        "assets/schema/continuity_bridge.v1.json",
        "assets/schema/narrative_causal_self_check.v1.json",
        "assets/schema/medium_lock.v1.json",
        "assets/templates/persona_card.v1.json",
        "assets/templates/character_asset_package.v1.json",
        "assets/templates/shot_prompt_template.v1.json",
        "assets/templates/continuity_bridge.v1.json",
        "assets/templates/narrative_causal_self_check.v1.json",
        "assets/templates/medium_lock.v1.json",
        "assets/checklists/script_executability.v1.json",
        "assets/checklists/script_executability.v1.md",
    ):
        assert (ROOT / rel).is_file(), rel


def test_filled_plan_is_ready():
    receipt = validate(_filled_plan())
    assert receipt["hard_failures"] == []
    assert receipt["rework"] == []
    assert receipt["verdict"] == "READY"


def test_missing_hard_prompt_is_blocked_not_rework():
    receipt = validate(_filled_plan(shots=[_filled_shot(prompt_ok=False)]))
    assert receipt["verdict"] == "BLOCKED"
    assert any("主生成指令" in item for item in receipt["hard_failures"])


def test_legacy_string_bridge_is_rework_not_blocked():
    receipt = validate(_filled_plan(shots=[_filled_shot(bridge="SC01 -> S02A")]))
    assert receipt["verdict"] == "REWORK"
    assert receipt["hard_failures"] == []
    assert any("legacy string" in item for item in receipt["rework"])


def test_placeholder_persona_is_rework():
    template = json.loads((ROOT / "assets" / "templates" / "persona_card.v1.json").read_text(encoding="utf-8"))
    receipt = validate(_filled_plan(assets={"characters": [{"asset_id": "CHAR_X", "persona_card": template}]}))
    assert receipt["verdict"] == "REWORK"
    assert receipt["hard_failures"] == []


def test_missing_medium_lock_is_blocked():
    plan = _filled_plan()
    plan.pop("medium_lock")
    receipt = validate(plan)
    assert receipt["verdict"] == "BLOCKED"
    assert any("medium_lock missing" in item for item in receipt["hard_failures"])


def test_chat_ui_prompt_is_blocked_unless_ui_animation():
    shot = _filled_shot("SHOT_01")
    shot["prompt"] += " 竖屏手机聊天界面，微信气泡弹出新消息"
    receipt = validate(_filled_plan(shots=[shot]))
    assert receipt["verdict"] == "BLOCKED"
    assert any("UI-medium language" in item for item in receipt["hard_failures"])


def test_ui_animation_medium_allows_chat_ui_language():
    lock = character_performance_lock()
    lock["output_medium"] = "UI_ANIMATION"
    shot = _filled_shot("SHOT_01")
    shot["prompt"] += " 竖屏手机聊天界面，微信气泡弹出新消息"
    receipt = validate(_filled_plan(medium_lock=lock, shots=[shot]))
    assert receipt["hard_failures"] == []
    assert receipt["verdict"] == "READY"


def test_char_001_dossier_has_persona_card():
    dossier = json.loads((ROOT / "characters" / "CHAR_001_dossier.v1.json").read_text(encoding="utf-8"))
    assert dossier["persona_card"]["appearance"]
    assert dossier["persona_card"]["makeup_sheet"]["naming_rule"] == "{character_id}_{expression}_{angle}"
    for field in ("visual", "negative_constraints", "behavioral", "relational"):
        assert dossier["identity_invariants"][field]
