"""Regression tests for common_patch() undefined name (P1 crash).

ep01_r3_pipeline.build() crashed with NameError on every shot build:
common_patch() set ``shot["script_prompt_review"]["prompt_hash"]`` from
``sha(compiled)``, but ``compiled`` is neither a parameter of
common_patch nor defined in its body. The prompt does not exist yet at
common_patch() time — it is compiled later by update_prompt(), which
replaces the whole script_prompt_review packet with the computed audit
from audit_script_prompt_review().

The hardcoded pass-through review block in common_patch() was dead
data (always overwritten) and duplicated audit-conclusion values that
the acceptance review requires to be computed, not hardcoded. Tests
verify common_patch() completes without it and that the composed
common_patch() -> update_prompt() flow passes the admission gate.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.ep01_r3_pipeline as pipeline
from tools.validate_script_prompt_review import validate_script_prompt_review


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
        "shot_rhythm": {},
        "render": {},
        "state_contract": {"episode_state": {}},
        "dialogue_order": "单句对白",
    }


def _run_common_patch(shot):
    pipeline.common_patch(
        shot,
        shot_id=SHOT_ID,
        scene="office",
        scene_urls=[
            "https://example.com/scene.png",
            "https://example.com/pack.png",
        ],
        roles=["composition_still", "identity_reference"],
        scene_text=SCENE_TEXT,
        phone_state="NO_PHONE",
        seconds=4.0,
        camera_level="NONE",
        reason=CAMERA_REASON,
    )


def test_common_patch_completes_without_undefined_names():
    shot = _shot()
    _run_common_patch(shot)
    assert shot["status"] == "READY"
    assert shot["shot_id"] == SHOT_ID
    assert shot["shot_rhythm"]["camera_motion_reason"] == CAMERA_REASON
    assert "script_prompt_review" not in shot


def test_common_patch_then_update_prompt_passes_admission_gate():
    shot = _shot()
    _run_common_patch(shot)
    pipeline.update_prompt(
        shot,
        {"shot_id": SHOT_ID, "who": "test", "scene": None},
        SCENE_TEXT,
        vo=False,
        phone_state="NO_PHONE",
    )
    result = validate_script_prompt_review(
        shot["script_prompt_review"],
        shot_id=SHOT_ID,
        run_id=shot["run_id"],
        expected_script_hash=pipeline.sha("EP01_SCRIPT_LOCKED_R3_20260921"),
        compiled_prompt=shot["shot_prompt"]["compiled_prompt"],
    )
    assert result["status"] == "PASS", result["errors"]
    assert result["shot_id"] == SHOT_ID
    assert result["prompt_conclusion"] == "合格，可以生成"
