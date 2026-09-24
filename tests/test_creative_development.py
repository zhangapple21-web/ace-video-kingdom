from __future__ import annotations

from pathlib import Path

from tools.creator_workflow import (
    build_creative_development_profile,
    validate_creative_development_profile,
)
from tools.run_idea_pipeline import _compile, _planning_conformance_check


def test_default_development_profile_is_explicit_and_non_authoritative():
    profile = build_creative_development_profile(title="雨夜重逢", source_text="写一个雨夜重逢的短剧")
    assert profile["schema"] == "ace.video_kingdom.creative_development_profile.v1"
    assert profile["status"] == "PENDING"
    assert profile["production_integration"] is False
    assert profile["input_classification"]["kind"] == "ORIGINAL_STORY"
    assert profile["input_classification"]["source_text_hash"]
    assert len(profile["character_signature_system"]["fields"]) == 10
    assert validate_creative_development_profile(profile)["status"] == "PASS"


def test_ready_development_profile_requires_story_evidence():
    profile = build_creative_development_profile(title="试播", status="READY")
    profile["character_roster"] = [{"character_id": "C001", "name": "文姬"}]
    profile["episode_structure"].update(
        {
            "opening_hook": "深夜电话突然响起",
            "conflict": "工作安排打断休息",
            "information_change": "文姬发现还有新的工作",
            "ending_question": "明天会发生什么？",
        }
    )
    assert validate_creative_development_profile(profile, require_ready=True)["status"] == "PASS"
    profile["episode_structure"]["ending_question"] = ""
    check = validate_creative_development_profile(profile, require_ready=True)
    assert check["status"] == "FAIL"
    assert "episode_structure missing ending_question" in check["errors"]


def test_pending_profile_with_broken_schema_is_not_silently_accepted():
    profile = build_creative_development_profile(title="坏样本")
    profile.pop("relationship_graph")
    check = validate_creative_development_profile(profile)
    assert check["status"] == "FAIL"
    assert "relationship_graph must declare nodes, edges and unknown_edges lists" in check["errors"]


def test_ready_profile_malformed_nested_sections_returns_failure_not_exception():
    profile = build_creative_development_profile(title="坏嵌套", status="READY")
    profile["character_roster"] = [{"character_id": "C001", "name": "文姬"}]
    profile["episode_structure"] = []
    profile["quality_review"] = []
    check = validate_creative_development_profile(profile)
    assert check["status"] == "FAIL"
    assert "episode_structure must be an object" in check["errors"]


def test_pipeline_consumes_development_profile_without_changing_provider(tmp_path: Path):
    plan = _compile("一个人在雨夜发现一段不能删除的录音", tmp_path, "development", target_seconds=30)
    assert plan["creative_development"]["production_integration"] is False
    assert plan["creator_brief"]["creative_development"]["schema"] == "ace.video_kingdom.creative_development_profile.v1"
    assert plan["render_defaults"]["model"] == "agnes-video-2.5-flash"
    assert _planning_conformance_check(plan)["status"] == "PASS"
