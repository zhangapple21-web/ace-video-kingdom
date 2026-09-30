from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.video_kingdom_entry import dispatch


def _reference_deconstruction_payload() -> dict:
    return {
        "schema": "video_kingdom.reference_deconstruction.v1",
        "deconstruction_id": "RDX-20260924-test",
        "status": "OBSERVED",
        "authority": "RESEARCH_ONLY",
        "production_authority": "NONE",
        "source": {
            "kind": "FAILED_TAKE",
            "locator": "local-test-clip.mp4",
            "duration_seconds": 5.0,
            "sha256": "a" * 64,
            "project_id": "test-project",
            "run_id": "run-1",
            "shot_id": "shot-1",
        },
        "observations": [
            {
                "id": "OBS-01",
                "time_start_seconds": 0.0,
                "time_end_seconds": 2.0,
                "channel": "VISUAL",
                "dimension": "ACTION_PERFORMANCE",
                "observable_fact": "角色保持坐姿，只有嘴部出现变化。",
                "confidence": 1.0,
            }
        ],
        "inferences": [
            {
                "id": "INF-01",
                "claim": "可能缺少可见的身体动作任务。",
                "observation_ids": ["OBS-01"],
                "confidence": 0.6,
                "status": "HYPOTHESIS",
            }
        ],
        "candidate_rules": [],
        "comparison": {"gaps": ["合同动作未出现在成片中"]},
        "learning": {
            "baseline": "",
            "change": "",
            "evaluation": "",
            "independent_repetitions": 0,
            "outcome": "UNTESTED",
            "promoted_to_default": False,
        },
    }


def test_unified_entry_routes_video_without_provider_submission(tmp_path: Path, monkeypatch):
    receipt = dispatch(text="制作第1镜视频", out=tmp_path / "entry.json")
    assert receipt["entrypoint"] == "video-kingdom"
    assert receipt["control_plane"] == "production_control"
    assert receipt["dispatch"] == "media_route"
    assert receipt["provider_submission"] == "NOT_PERFORMED"
    assert receipt["creative_development"]["schema"] == "ace.video_kingdom.creative_development_profile.v1"
    assert receipt["creative_development_check"]["status"] == "PASS"
    assert Path(receipt["creative_development_artifact"]).is_file()
    assert receipt["workflow_policy"]["schema"] == "ace.video_kingdom.video_workflow_decision_matrix.v1"
    assert receipt["workflow_policy"]["stage_order"] == [1, 2, 3, 4, 5, 6, 7]
    assert receipt["workflow_policy"]["validation"]["status"] == "PASS"
    assert len(receipt["workflow_policy"]["sha256"]) == 64
    assert receipt["collaboration"]["mode"] == "DEFAULT_MULTI_WINDOW"
    assert receipt["collaboration"]["authority"] == "DEFAULT_METHOD_ONLY"
    assert len(receipt["collaboration"]["contract_sha256"]) == 64
    assert json.loads((tmp_path / "entry.json").read_text(encoding="utf-8"))["entry_id"] == receipt["entry_id"]


def test_unified_entry_sends_narrative_to_role_room(tmp_path: Path, monkeypatch):
    called: list[list[str]] = []
    monkeypatch.setattr("tools.video_kingdom_entry.role_room.main", lambda argv: called.append(argv) or 0)
    receipt = dispatch(text="写一个雨夜重逢的短剧大纲", out=tmp_path / "entry.json", profile="rapid")
    assert receipt["dispatch"] == "role_room"
    assert called and "--profile" in called[0]


def test_script_review_with_video_keywords_still_goes_to_role_room(tmp_path: Path, monkeypatch):
    called: list[list[str]] = []
    monkeypatch.setattr("tools.video_kingdom_entry.role_room.main", lambda argv: called.append(argv) or 0)
    receipt = dispatch(
        text="先审这个剧本、补齐分镜，再制作视频镜头。",
        out=tmp_path / "entry.json",
        profile="standard",
    )
    assert receipt["routing_decision"] == "NARRATIVE_FIRST"
    assert receipt["detected_media_intent"] == "VIDEO"
    assert receipt["dispatch"] == "role_room"
    assert called


def test_unified_entry_binds_valid_reference_deconstruction_as_non_authoritative_evidence(tmp_path: Path):
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps(_reference_deconstruction_payload()), encoding="utf-8")

    receipt = dispatch(
        text="分析这条失败镜头并优化拍摄方案",
        out=tmp_path / "entry.json",
        reference_deconstruction=reference,
    )

    attached = receipt["reference_deconstruction"]
    assert attached["deconstruction_id"] == "RDX-20260924-test"
    assert attached["artifact_sha256"] == hashlib.sha256(reference.read_bytes()).hexdigest()
    assert attached["authority"] == "RESEARCH_ONLY"
    assert attached["production_authority"] == "NONE"
    assert attached["validation"]["status"] == "PASS"
    assert receipt["provider_submission"] == "NOT_PERFORMED"


def test_unified_entry_blocks_invalid_reference_deconstruction(tmp_path: Path):
    reference = tmp_path / "invalid-reference.json"
    payload = _reference_deconstruction_payload()
    payload["authority"] = "PRODUCTION"
    reference.write_text(json.dumps(payload), encoding="utf-8")

    try:
        dispatch(
            text="分析失败镜头",
            out=tmp_path / "entry.json",
            reference_deconstruction=reference,
        )
    except ValueError as exc:
        assert "REFERENCE_DECONSTRUCTION_INVALID" in str(exc)
    else:
        raise AssertionError("invalid reverse-deconstruction receipt must be blocked")
