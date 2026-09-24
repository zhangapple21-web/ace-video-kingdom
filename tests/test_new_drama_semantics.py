import json
from pathlib import Path

import pytest

from tools.production_shot_gate import validate_production_shot
from tools.validate_new_drama_semantics import is_new_drama, validate_new_drama_semantics
from tools.workflow_decision_matrix import build_workflow_policy_receipt

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _workflow_policy(script_hash: str = "a" * 64):
    quality_review = {
        "reviewer": "independent-source-review",
        "evidence_refs": ["role-room-receipt.json#contrarian_auditor"],
        "source_quality_criteria": {
            key: {"score": 2, "evidence": f"source evidence for {key}"}
            for key in ("hook", "conflict", "character_goal", "escalation", "payoff", "visual_action", "production_fit")
        },
        "project_selection_criteria": {
            key: {"score": 2, "evidence": f"selection evidence for {key}"}
            for key in ("hook", "conflict", "visual_action", "character_memorability", "episode_payload", "continuation", "production_fit")
        },
    }
    return build_workflow_policy_receipt(
        ROOT,
        creative_development={"quality_review": quality_review},
        reviewed_script_hash=script_hash,
    )


def _new_drama_packet(**overrides):
    packet = {
        "production_semantics": "new_drama",
        "shot_id": "ND01",
        "script_hash": "a" * 64,
        "character_asset_package": {"character_id": "CHAR_A", "name": "hero"},
        "scene_asset_package": {"scene_id": "SCENE_A", "name": "living-room"},
        "prop_asset_package": {"prop_id": "PROP_A", "name": "cup"},
        "workflow_policy": _workflow_policy(),
        "director_preflight": {
            "spatial_audit": {
                "locked_shot_no_added_beats": True,
                "forbidden_additions": "no extra extras",
                "world_position": "sofa left facing window",
                "screen_left_right": "frame right",
                "world_not_equal_screen": True,
            }
        },
        "shot_rhythm": {"overflow_policy": "split_or_extend_never_swallow"},
        "continuity_bridge": {
            "asset_register": [
                {"asset_id": "CHAR_A", "kind": "character", "initial": "sit", "change": "stand", "final": "stand"},
                {"asset_id": "SCENE_A", "kind": "scene", "initial": "day", "change": "none", "final": "day"},
                {"asset_id": "PROP_A", "kind": "prop", "initial": "table", "change": "lift", "final": "hand"},
            ]
        },
        "knowledge_status": {"facts": ["day interior"], "assumptions": ["street noise"], "unknowns": ["neighbor"]},
        "creative_constraints": {
            "negative_constraints_policy": {
                "evidence_required": True,
                "genre_hard_bans_always_written": True,
            }
        },
    }
    packet.update(overrides)
    return packet


def test_legacy_packet_is_skipped():
    assert is_new_drama({"shot_id": "S01"}) is False
    result = validate_new_drama_semantics({"shot_id": "S01"})
    assert result["status"] == "SKIPPED"


def test_new_drama_pipeline_and_six_checks_pass():
    result = validate_new_drama_semantics(_new_drama_packet())
    assert result["status"] == "PASS"
    assert result["checks"] == ["A01", "A02", "A06", "A09", "A13", "A14"]


def test_asset_register_ids_must_resolve_to_matching_typed_packages():
    packet = _new_drama_packet()
    packet["continuity_bridge"]["asset_register"][2]["asset_id"] = "PROP_OTHER"
    result = validate_new_drama_semantics(packet)
    assert result["status"] == "BLOCKED"
    assert any("PROP_OTHER does not resolve in the prop asset package" in item for item in result["errors"])


def test_provider_spend_blocks_when_source_or_project_selection_is_not_passed():
    packet = _new_drama_packet()
    packet["workflow_policy"]["source_quality_assessment"]["status"] = "PENDING"
    result = validate_new_drama_semantics(packet)
    assert result["status"] == "BLOCKED"
    assert any("source_quality_assessment must have current criterion evidence" in item for item in result["errors"])


def test_provider_spend_blocks_stale_quality_review_after_script_change():
    packet = _new_drama_packet()
    packet["script_hash"] = "b" * 64
    result = validate_new_drama_semantics(packet)
    assert result["status"] == "BLOCKED"
    assert any("reviewed_script_hash must match" in item for item in result["errors"])


def test_provider_spend_recomputes_reported_quality_scores():
    packet = _new_drama_packet()
    packet["workflow_policy"]["source_quality_assessment"]["score"] = 0
    result = validate_new_drama_semantics(packet)
    assert result["status"] == "BLOCKED"
    assert any("score does not match" in item for item in result["errors"])


def test_props_are_optional_when_the_shot_has_no_registered_props():
    packet = _new_drama_packet()
    packet.pop("prop_asset_package")
    packet["continuity_bridge"]["asset_register"] = packet["continuity_bridge"]["asset_register"][:2]
    result = validate_new_drama_semantics(packet)
    assert result["status"] == "PASS"


def test_clue_ui_plate_and_fx_assets_can_be_declared_by_typed_packages():
    packet = _new_drama_packet(asset_packages={"clues": {"clue_id": "CLUE_A"}, "ui_plates": {"ui_plate_id": "UI_A"}, "fx": {"fx_id": "FX_A"}})
    packet["continuity_bridge"]["asset_register"].extend([
        {"asset_id": "CLUE_A", "kind": "clue", "initial": "sealed", "change": "opened", "final": "evidence visible"},
        {"asset_id": "UI_A", "kind": "ui_plate", "initial": "hidden", "change": "post overlay", "final": "approved overlay"},
        {"asset_id": "FX_A", "kind": "fx", "initial": "off", "change": "brief flash", "final": "off"},
    ])
    assert validate_new_drama_semantics(packet)["status"] == "PASS"


def test_missing_scene_or_prop_blocks():
    packet = _new_drama_packet()
    del packet["scene_asset_package"]
    del packet["prop_asset_package"]
    result = validate_new_drama_semantics(packet)
    assert result["status"] == "BLOCKED"
    assert any("scene assets missing" in item for item in result["errors"])
    assert any("references prop asset without a declared package" in item for item in result["errors"])


def test_world_copied_as_screen_blocks_on_new_drama_only():
    bad = _new_drama_packet()
    bad["director_preflight"]["spatial_audit"]["world_position"] = "frame right"
    bad["director_preflight"]["spatial_audit"]["screen_left_right"] = "frame right"
    result = validate_new_drama_semantics(bad)
    assert result["status"] == "BLOCKED"
    assert any(item.startswith("A02:") for item in result["errors"])
    skipped = dict(bad)
    skipped["production_semantics"] = "legacy"
    assert validate_new_drama_semantics(skipped)["status"] == "SKIPPED"


def test_semantics_contract_matches_gate_ids():
    contract = _load("governance/new_drama_production_semantics.v1.json")
    checklist = _load("assets/checklists/generic_default_layer.v1.json")
    assert contract["pipeline"][-2]["checks"] == ["A01", "A02", "A06", "A09", "A13", "A14"]
    assert checklist["new_drama_production_semantics"]["gate_ids"] == contract["pipeline"][-2]["checks"]
    joined = " ".join(contract["does_not_replace"])
    assert "video_kingdom_entry.py" in joined
    assert "agnes-video-2.5-flash" in joined


def test_production_shot_gate_legacy_does_not_require_new_drama_fields():
    with pytest.raises(ValueError, match="creative constraints failed"):
        validate_production_shot({"shot_id": "S01"}, "prompt")


def test_production_shot_gate_new_drama_blocks_before_agnes_shape():
    with pytest.raises(ValueError, match="new drama semantics failed"):
        validate_production_shot(
            {
                "production_semantics": "new_drama",
                "shot_id": "ND01",
                "creative_constraints": {
                    "hard": {
                        key: {"status": "LOCKED", "rules": ["rule"]}
                        for key in (
                            "identity_reference",
                            "narrative_order",
                            "spatial_relationship",
                            "visibility_and_exclusions",
                            "performance_and_audio",
                        )
                    },
                    "flexible": {},
                    "deferred": [],
                    "negative_constraints_policy": {
                        "evidence_required": True,
                        "genre_hard_bans_always_written": True,
                    },
                },
                "script_prompt_review": {
                    "shot_id": "ND01",
                    "run_id": "run-1",
                    "script_hash": "abc",
                    "prompt_hash": "def",
                    "script_review": {"conclusion": "通过"},
                    "prompt_review": {"conclusion": "合格，可以生成"},
                },
            },
            "compiled",
        )
