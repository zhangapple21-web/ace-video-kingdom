"""Tests for Bug #4: shots stuck at COMPILED_PENDING_FRAME_PROOF.

The bug: episode_plan.json uses S01A-style shot IDs while shot_core_manifest.v1.json
uses SHOT_01A_ZHANG_R3-style shot IDs. There is no mapping, no frame-proof validation,
and no status advancement from COMPILED_PENDING_FRAME_PROOF to READY.

These tests verify:
1. Naming schema mapping (S01A <-> SHOT_01A_ZHANG_R3)
2. Frame evidence checking (video file, QC report, lip-sync QC, continuity evidence)
3. Status advancement logic (advance if evidence present, stay pending if missing)
"""
import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def ep01_r3_module():
    import importlib
    import tools.ep01_r3_pipeline as mod
    importlib.reload(mod)
    return mod


@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path


class TestNamingSchemaMapping:
    """Test the naming schema mapping between episode_plan and pipeline shot IDs."""

    def test_map_episode_to_pipeline_basic(self, ep01_r3_module):
        """S01A should map to SHOT_01A_ZHANG_R3 (first shot in ORDER)."""
        ep_module = ep01_r3_module
        ORDER = ep_module.ORDER
        assert ORDER[0] == "SHOT_01A_ZHANG_R3"

    def test_episode_plan_shots_are_subset_of_order(self, ep01_r3_module):
        """All episode plan shot IDs should map to a shot in ORDER."""
        ep_module = ep01_r3_module
        ORDER = ep_module.ORDER

        # Episode plan uses S01A, S02A, ..., S06A
        episode_plan_shots = ["S01A", "S02A", "S03A", "S04A", "S05A", "S06A"]

        for ep_shot in episode_plan_shots:
            pipeline_id = ep_module.map_episode_plan_to_pipeline_shot(ep_shot, ORDER)
            assert pipeline_id is not None, f"No pipeline mapping for {ep_shot}"
            assert pipeline_id in ORDER, f"Mapped shot {pipeline_id} not in ORDER"

    def test_map_episode_to_pipeline_01c_vo(self, ep01_r3_module):
        """S01C should map to SHOT_01C_WENJI_VO_R3."""
        ep_module = ep01_r3_module
        ORDER = ep_module.ORDER
        result = ep_module.map_episode_plan_to_pipeline_shot("S01C", ORDER)
        assert result == "SHOT_01C_WENJI_VO_R3"

    def test_map_episode_to_pipeline_unknown(self, ep01_r3_module):
        """S99A should return None (not in ORDER)."""
        ep_module = ep01_r3_module
        ORDER = ep_module.ORDER
        result = ep_module.map_episode_plan_to_pipeline_shot("S99A", ORDER)
        assert result is None

    def test_map_pipeline_to_episode_basic(self, ep01_r3_module):
        """SHOT_01A_ZHANG_R3 should map back to S01A."""
        ep_module = ep01_r3_module
        result = ep_module.map_pipeline_to_episode_plan("SHOT_01A_ZHANG_R3")
        assert result == "S01A"

    def test_map_pipeline_to_episode_035c_slip(self, ep01_r3_module):
        """SHOT_035C_WENJI_SLIP_V9 should map to S035C."""
        ep_module = ep01_r3_module
        result = ep_module.map_pipeline_to_episode_plan("SHOT_035C_WENJI_SLIP_V9")
        assert result == "S035C"

    def test_map_pipeline_to_episode_06f_vo(self, ep01_r3_module):
        """SHOT_06F_WENJI_VO_V9 should map to S06F."""
        ep_module = ep01_r3_module
        result = ep_module.map_pipeline_to_episode_plan("SHOT_06F_WENJI_VO_V9")
        assert result == "S06F"


class TestFrameEvidenceCheck:
    """Test frame evidence checking logic."""

    def test_frame_evidence_complete_when_all_present(self, ep01_r3_module, temp_dir):
        """All frame evidence present should return all checks as PASS."""
        ep_module = ep01_r3_module
        shot_id = "SHOT_01A_ZHANG_R3"

        video_file = temp_dir / f"{shot_id}.mp4"
        video_file.write_bytes(b"fakedata" * 1000)

        qc_base = temp_dir / "frame_qc" / shot_id
        qc_base.mkdir(parents=True)
        (qc_base / "video_qc_report.json").write_text(json.dumps({
            "technical_status": "PASS",
            "creative_status": "PASS",
            "provider_status": "SUCCESS",
        }), encoding="utf-8")

        continuity_base = temp_dir / "continuity"
        continuity_base.mkdir(parents=True)
        (continuity_base / f"{shot_id}_pass_ready.json").write_text(json.dumps({
            "status": "PASS",
            "ready_for_next": True,
        }), encoding="utf-8")

        lip_sync_base = temp_dir / "lip_sync"
        lip_sync_base.mkdir(parents=True)
        (lip_sync_base / f"{shot_id}_qc.json").write_text(json.dumps({
            "status": "PASS",
        }), encoding="utf-8")

        result = ep_module.check_frame_evidence(
            shot_id, temp_dir,
            frame_videos_dir=temp_dir,
            qc_dir=temp_dir / "frame_qc",
            continuity_dir=continuity_base,
            lip_sync_dir=lip_sync_base,
        )

        assert result["provider_video"] is True
        assert result["frame_qc_pass"] is True
        assert result["continuity_evidence"] is True
        assert result["lip_sync_qc"] is True
        assert result["all_pass"] is True
        assert len(result["missing"]) == 0

    def test_frame_evidence_missing_video(self, ep01_r3_module, temp_dir):
        """Missing video file should fail provider_video check."""
        ep_module = ep01_r3_module
        shot_id = "SHOT_01A_ZHANG_R3"

        result = ep_module.check_frame_evidence(
            shot_id, temp_dir,
            frame_videos_dir=temp_dir,
            qc_dir=temp_dir / "frame_qc",
            continuity_dir=temp_dir / "continuity",
            lip_sync_dir=temp_dir / "lip_sync",
        )

        assert result["provider_video"] is False
        assert result["all_pass"] is False
        assert "provider_video" in result["missing"]

    def test_frame_evidence_missing_qc_report(self, ep01_r3_module, temp_dir):
        """Missing QC report should fail frame_qc_pass check."""
        ep_module = ep01_r3_module
        shot_id = "SHOT_01A_ZHANG_R3"

        video_file = temp_dir / f"{shot_id}.mp4"
        video_file.write_bytes(b"data" * 1000)

        result = ep_module.check_frame_evidence(
            shot_id, temp_dir,
            frame_videos_dir=temp_dir,
            qc_dir=temp_dir / "frame_qc",
            continuity_dir=temp_dir / "continuity",
            lip_sync_dir=temp_dir / "lip_sync",
        )

        assert result["frame_qc_pass"] is False
        assert result["all_pass"] is False
        assert "frame_qc_pass" in result["missing"]

    def test_frame_evidence_qc_fail(self, ep01_r3_module, temp_dir):
        """QC report with FAIL status should fail frame_qc_pass check."""
        ep_module = ep01_r3_module
        shot_id = "SHOT_01A_ZHANG_R3"

        video_file = temp_dir / f"{shot_id}.mp4"
        video_file.write_bytes(b"data" * 1000)

        qc_dir = temp_dir / "frame_qc" / shot_id
        qc_dir.mkdir(parents=True)
        (qc_dir / "video_qc_report.json").write_text(json.dumps({
            "technical_status": "PASS",
            "creative_status": "FAIL",
            "provider_status": "SUCCESS",
        }), encoding="utf-8")

        result = ep_module.check_frame_evidence(
            shot_id, temp_dir,
            frame_videos_dir=temp_dir,
            qc_dir=temp_dir / "frame_qc",
            continuity_dir=temp_dir / "continuity",
            lip_sync_dir=temp_dir / "lip_sync",
        )

        assert result["frame_qc_pass"] is False
        assert result["all_pass"] is False
        assert "frame_qc_pass" in result["missing"]

    def test_frame_evidence_missing_continuity(self, ep01_r3_module, temp_dir):
        """Missing continuity evidence should fail continuity_evidence check."""
        ep_module = ep01_r3_module
        shot_id = "SHOT_01A_ZHANG_R3"

        video_file = temp_dir / f"{shot_id}.mp4"
        video_file.write_bytes(b"data" * 1000)

        result = ep_module.check_frame_evidence(
            shot_id, temp_dir,
            frame_videos_dir=temp_dir,
            qc_dir=temp_dir / "frame_qc",
            continuity_dir=temp_dir / "continuity",
            lip_sync_dir=temp_dir / "lip_sync",
        )

        assert result["continuity_evidence"] is False
        assert result["all_pass"] is False
        assert "continuity_evidence" in result["missing"]

    def test_frame_evidence_missing_lip_sync(self, ep01_r3_module, temp_dir):
        """Missing lip-sync QC should fail lip_sync_qc check."""
        ep_module = ep01_r3_module
        shot_id = "SHOT_01A_ZHANG_R3"

        video_file = temp_dir / f"{shot_id}.mp4"
        video_file.write_bytes(b"data" * 1000)

        result = ep_module.check_frame_evidence(
            shot_id, temp_dir,
            frame_videos_dir=temp_dir,
            qc_dir=temp_dir / "nonexistent_qc",
            continuity_dir=temp_dir / "nonexistent_continuity",
            lip_sync_dir=temp_dir / "lip_sync",
        )

        assert result["lip_sync_qc"] is False
        assert result["all_pass"] is False
        assert "lip_sync_qc" in result["missing"]


class TestStatusAdvancement:
    """Test status advancement from COMPILED_PENDING_FRAME_PROOF."""

    def test_advance_frame_proof_with_complete_evidence(self, ep01_r3_module, temp_dir):
        """Shots with all frame evidence should advance to READY."""
        ep_module = ep01_r3_module
        shot_id = "SHOT_01A_ZHANG_R3"

        video_file = temp_dir / f"{shot_id}.mp4"
        video_file.write_bytes(b"data" * 1000)

        qc_dir = temp_dir / "frame_qc" / shot_id
        qc_dir.mkdir(parents=True)
        (qc_dir / "video_qc_report.json").write_text(json.dumps({
            "technical_status": "PASS",
            "creative_status": "PASS",
            "provider_status": "SUCCESS",
        }), encoding="utf-8")

        continuity_dir = temp_dir / "continuity"
        continuity_dir.mkdir(parents=True)
        (continuity_dir / f"{shot_id}_pass_ready.json").write_text(json.dumps({
            "status": "PASS",
            "ready_for_next": True,
        }), encoding="utf-8")

        lip_sync_dir = temp_dir / "lip_sync"
        lip_sync_dir.mkdir(parents=True)
        (lip_sync_dir / f"{shot_id}_qc.json").write_text(json.dumps({
            "status": "PASS",
        }), encoding="utf-8")

        episode_plan = {
            "status": "COMPILED_PENDING_FRAME_PROOF",
            "shots": [
                {"shot_id": "S01A", "status": "COMPILED_PENDING_FRAME_PROOF"}
            ]
        }
        plan_file = temp_dir / "episode_plan.json"
        ep_module.atomic_write_json(plan_file, episode_plan)

        result = ep_module.advance_frame_proof(
            plan_file, temp_dir,
            frame_videos_dir=temp_dir,
            qc_base=temp_dir / "frame_qc",
            continuity_base=continuity_dir,
            lip_sync_base=lip_sync_dir,
        )

        assert result["total"] == 1
        assert result["advanced"] == 1
        assert result["stuck"] == 0
        assert len(result["advanced_shots"]) == 1
        assert result["advanced_shots"][0]["episode_shot_id"] == "S01A"
        assert result["advanced_shots"][0]["pipeline_shot_id"] == "SHOT_01A_ZHANG_R3"

    def test_advance_frame_proof_missing_evidence_stays_pending(self, ep01_r3_module, temp_dir):
        """Shots without frame evidence should stay at COMPILED_PENDING_FRAME_PROOF."""
        ep_module = ep01_r3_module

        episode_plan = {
            "status": "COMPILED_PENDING_FRAME_PROOF",
            "shots": [
                {"shot_id": "S01A", "status": "COMPILED_PENDING_FRAME_PROOF"}
            ]
        }
        plan_file = temp_dir / "episode_plan.json"
        ep_module.atomic_write_json(plan_file, episode_plan)

        result = ep_module.advance_frame_proof(
            plan_file, temp_dir,
            frame_videos_dir=temp_dir,
            qc_base=temp_dir / "frame_qc",
            continuity_base=temp_dir / "continuity",
            lip_sync_base=temp_dir / "lip_sync",
        )

        assert result["total"] == 1
        assert result["advanced"] == 0
        assert result["stuck"] == 1
        assert len(result["stuck_shots"]) == 1
        assert result["stuck_shots"][0]["episode_shot_id"] == "S01A"
        assert len(result["stuck_shots"][0]["missing_evidence"]) > 0

    def test_advance_frame_proof_updates_status(self, ep01_r3_module, temp_dir):
        """Advanced shot status should change in episode_plan.json."""
        ep_module = ep01_r3_module
        shot_id = "SHOT_01A_ZHANG_R3"

        video_file = temp_dir / f"{shot_id}.mp4"
        video_file.write_bytes(b"data" * 1000)

        qc_dir = temp_dir / "frame_qc" / shot_id
        qc_dir.mkdir(parents=True)
        (qc_dir / "video_qc_report.json").write_text(json.dumps({
            "technical_status": "PASS",
            "creative_status": "PASS",
            "provider_status": "SUCCESS",
        }), encoding="utf-8")

        continuity_dir = temp_dir / "continuity"
        continuity_dir.mkdir(parents=True)
        (continuity_dir / f"{shot_id}_pass_ready.json").write_text(json.dumps({
            "status": "PASS",
            "ready_for_next": True,
        }), encoding="utf-8")

        lip_sync_dir = temp_dir / "lip_sync"
        lip_sync_dir.mkdir(parents=True)
        (lip_sync_dir / f"{shot_id}_qc.json").write_text(json.dumps({
            "status": "PASS",
        }), encoding="utf-8")

        episode_plan = {
            "status": "COMPILED_PENDING_FRAME_PROOF",
            "shots": [
                {"shot_id": "S01A", "status": "COMPILED_PENDING_FRAME_PROOF"}
            ]
        }
        plan_file = temp_dir / "episode_plan.json"
        ep_module.atomic_write_json(plan_file, episode_plan)

        ep_module.advance_frame_proof(
            plan_file, temp_dir,
            frame_videos_dir=temp_dir,
            qc_base=temp_dir / "frame_qc",
            continuity_base=continuity_dir,
            lip_sync_base=lip_sync_dir,
        )

        updated = json.loads(plan_file.read_text(encoding="utf-8"))
        assert updated["shots"][0]["status"] == "READY"

    def test_advance_frame_proof_unmapped_shot_skipped(self, ep01_r3_module, temp_dir):
        """Shots without a pipeline mapping should be skipped with a warning."""
        ep_module = ep01_r3_module

        episode_plan = {
            "status": "COMPILED_PENDING_FRAME_PROOF",
            "shots": [
                {"shot_id": "S99A", "status": "COMPILED_PENDING_FRAME_PROOF"}
            ]
        }
        plan_file = temp_dir / "episode_plan.json"
        ep_module.atomic_write_json(plan_file, episode_plan)

        result = ep_module.advance_frame_proof(
            plan_file, temp_dir,
            frame_videos_dir=temp_dir,
            qc_base=temp_dir / "frame_qc",
            continuity_base=temp_dir / "continuity",
            lip_sync_base=temp_dir / "lip_sync",
        )

        assert result["total"] == 1
        assert result["advanced"] == 0
        assert len(result["skipped_shots"]) == 1
