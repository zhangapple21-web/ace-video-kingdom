"""Regression tests for update_prompt() undefined names (P1 crash).

ep01_r3_pipeline.build() crashed with NameError on every shot build:
update_prompt() referenced ``shot_id`` and ``reason``, which are
neither parameters of update_prompt nor defined in its body. Both
values are already carried on the shot dict by common_patch(), which
always runs immediately before update_prompt() in build_one_first()
and build_one_from_clip().

Tests verify update_prompt() completes and produces a computed
script_prompt_review whose prompt_hash binds the compiled prompt, and
that the audit fields are computed from the prompt text rather than
hardcoded pass-through values.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.ep01_r3_pipeline as pipeline


SHOT_ID = "SHOT_TEST_R3"
CAMERA_REASON = "机位俯拍空间与表节拍，轻轨跟随"
SCENE_TEXT = "办公室工位中景，画面、桌、显示器和键盘成真实室内空间关系"


def _shot():
    return {
        "shot_id": SHOT_ID,
        "shot_prompt": {},
        "shot_contract": {
            "single_action": True,
            "max_primary_actions": 1,
            "cut_policy": "match_locked_script",
        },
        "shot_rhythm": {"camera_motion_reason": CAMERA_REASON},
        "dialogue_order": "单句对白",
    }


def _clip():
    return {"shot_id": SHOT_ID, "who": "test", "scene": None}


def test_update_prompt_completes_with_computed_review():
    shot = _shot()
    pipeline.update_prompt(shot, _clip(), SCENE_TEXT, vo=False, phone_state="NO_PHONE")
    review = shot["script_prompt_review"]
    assert review["shot_id"] == SHOT_ID
    assert review["run_id"] == pipeline.RUN_ID.lower() + "_" + SHOT_ID.lower()
    assert review["prompt_hash"] == pipeline.sha(shot["shot_prompt"]["compiled_prompt"])
    prompt_review = review["prompt_review"]
    assert prompt_review["distorts_script"] is False
    assert prompt_review["hard_rules_complete"] is True
    assert prompt_review["high_risk_extras"] is False
    assert prompt_review["reason"] == CAMERA_REASON
    assert review["script_review"]["verdict"] == "通过"
    assert review["prompt_review"]["conclusion"] == "合格，可以生成"


def test_audit_review_is_computed_not_hardcoded():
    review = pipeline.audit_script_prompt_review(
        "主体：测试。静态背景镜头",
        SHOT_ID,
        "NO_PHONE",
        _shot(),
        CAMERA_REASON,
    )
    assert review["prompt_review"]["distorts_script"] is True
    assert review["script_review"]["verdict"] == "不通过"
    assert review["prompt_review"]["conclusion"] == "不合格需修改"
