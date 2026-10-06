"""Feature tests for Bug #3: batch admission failures.

Bug #3 reported 41 batch admission failures with errors:
  - script_review missing
  - prompt_review not true
  - audio contract failed

Root cause: ep01_r3_pipeline.py set garbled text values and was MISSING
required fields in script_prompt_review:
  - script_review.role ("编剧")
  - script_review.dialogue_order
  - script_review.reviewed_at (ISO-8601 timestamp)
  - prompt_review.role ("导演")
  - prompt_review.distorts_script (False)
  - prompt_review.hard_rules_complete (True)
  - prompt_review.high_risk_extras (False)
  - prompt_review.reviewed_at (ISO-8601 timestamp)
  - script_prompt_review.schema
  - script_prompt_review.prompt_hash

Tests verify these fields are now present and the admission gate passes.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validate_script_prompt_review import (
    validate_script_prompt_review,
    SCHEMA,
    PASS_SCRIPT,
    PASS_PROMPT,
    prompt_hash,
)


def _sample_script_prompt_review():
    compiled = "any compiled prompt"
    return {
        "schema": SCHEMA,
        "shot_id": "S01A",
        "run_id": "r3",
        "script_hash": "a" * 64,
        "prompt_hash": prompt_hash(compiled),
        "script_review": {
            "role": "编剧",
            "verdict": PASS_SCRIPT,
            "phone_state": "PHONE_DESK",
            "dialogue_order": "单句对白",
            "unfilmable_risks": "屏幕内容不进入画面",
            "monologue_handling": "独白闭嘴后期叠加",
            "reviewed_at": "2026-09-21T12:00:00+08:00",
        },
        "prompt_review": {
            "role": "导演",
            "conclusion": PASS_PROMPT,
            "reason": "空间、身份已锁定",
            "distorts_script": False,
            "hard_rules_complete": True,
            "high_risk_extras": False,
            "reviewed_at": "2026-09-21T12:01:00+08:00",
        },
    }


def test_script_prompt_review_passes_validation():
    """Full script_prompt_review with all required fields should PASS admission."""
    review = _sample_script_prompt_review()
    result = validate_script_prompt_review(
        review,
        shot_id="S01A",
        run_id="r3",
        expected_script_hash="a" * 64,
        compiled_prompt="any compiled prompt",  # matches _sample_script_prompt_review()
    )
    assert result["status"] == "PASS"
    assert result["errors"] == []


def test_script_review_role_required():
    """Missing script_review.role should produce an error."""
    review = _sample_script_prompt_review()
    del review["script_review"]["role"]
    result = validate_script_prompt_review(review)
    assert result["status"] == "BLOCKED"
    assert any("role" in e for e in result["errors"])


def test_script_review_dialogue_order_required():
    """Missing script_review.dialogue_order should produce an error."""
    review = _sample_script_prompt_review()
    del review["script_review"]["dialogue_order"]
    result = validate_script_prompt_review(review)
    assert result["status"] == "BLOCKED"
    assert any("dialogue_order" in e for e in result["errors"])


def test_prompt_review_distorts_script_must_be_false():
    """prompt_review.distorts_script must be False."""
    review = _sample_script_prompt_review()
    review["prompt_review"]["distorts_script"] = True
    result = validate_script_prompt_review(review)
    assert result["status"] == "BLOCKED"
    assert any("distorts_script" in e for e in result["errors"])


def test_prompt_review_hard_rules_complete_must_be_true():
    """prompt_review.hard_rules_complete must be True."""
    review = _sample_script_prompt_review()
    review["prompt_review"]["hard_rules_complete"] = False
    result = validate_script_prompt_review(review)
    assert result["status"] == "BLOCKED"
    assert any("hard_rules_complete" in e for e in result["errors"])


def test_prompt_review_high_risk_extras_must_be_false():
    """prompt_review.high_risk_extras must be False."""
    review = _sample_script_prompt_review()
    review["prompt_review"]["high_risk_extras"] = True
    result = validate_script_prompt_review(review)
    assert result["status"] == "BLOCKED"
    assert any("high_risk_extras" in e for e in result["errors"])


def test_reviewed_at_must_be_iso8601():
    """reviewed_at must be a valid ISO-8601 timestamp."""
    review = _sample_script_prompt_review()
    review["script_review"]["reviewed_at"] = "not-a-timestamp"
    result = validate_script_prompt_review(review)
    assert result["status"] == "BLOCKED"
    assert any("reviewed_at" in e for e in result["errors"])


def _computed_review():
    """Audit packet computed by the pipeline's rule-based audit."""
    import tools.ep01_r3_pipeline as pipeline
    compiled = "主体：测试场景。避免风景照、静止背景。"
    shot = {
        "shot_contract": {
            "single_action": True,
            "max_primary_actions": 1,
            "cut_policy": "match_locked_script",
        },
        "dialogue_order": "单句对白",
    }
    return pipeline.audit_script_prompt_review(
        compiled, "S01A", "NO_PHONE", shot, "测试运镜原因",
    )


def test_ep01_r3_pipeline_sets_all_required_fields():
    """Verify the computed audit packet sets all required fields."""
    review = _computed_review()
    assert review["schema"] == "video_kingdom.script_prompt_review.v1"
    assert review["script_review"]["role"] == "编剧"
    assert review["prompt_review"]["role"] == "导演"
    assert review["prompt_review"]["distorts_script"] is False
    assert review["prompt_review"]["hard_rules_complete"] is True
    assert review["prompt_review"]["high_risk_extras"] is False
    assert "reviewed_at" in review["script_review"]
    assert "reviewed_at" in review["prompt_review"]
    assert review["script_review"]["dialogue_order"] == "单句对白"


def test_garbled_verdict_fixed():
    """The computed script verdict must match PASS_SCRIPT exactly."""
    from tools.validate_script_prompt_review import PASS_SCRIPT
    assert PASS_SCRIPT == "通过"
    review = _computed_review()
    assert review["script_review"]["verdict"] == PASS_SCRIPT
