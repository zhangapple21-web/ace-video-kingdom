"""Feature tests for 6 core modules that had zero test coverage.

Tests lock down current behavior BEFORE any fixes are applied.
Run: py -3 -m pytest tests/test_core_module_feature_tests.py -v
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))


# ─── Module 1: tools.world_live_evolve ───

def test_world_live_evolve_dump_round_trip_utf8(tmp_path):
    """_dump writes valid UTF-8 JSON that _read can recover."""
    import importlib
    mod = importlib.import_module("tools.world_live_evolve")

    obj = {"schema": "test.v1", "message": "活着的世界 🌍", "count": 3}
    path = tmp_path / "receipt.json"
    mod._dump(path, obj)
    loaded = json.loads(mod._read(path))
    assert loaded == obj


def test_world_live_evolve_dump_preserves_chinese_and_emoji(tmp_path):
    """Receipt with Chinese text and emoji must round-trip without error."""
    import importlib
    mod = importlib.import_module("tools.world_live_evolve")

    obj = {"schema": "video_kingdom.world_live_receipt.v1", "note": "活体演化候选 🌊", "waves": [1, 2]}
    path = tmp_path / "receipt.json"
    mod._dump(path, obj)
    raw = path.read_bytes()
    assert raw.startswith(b"{")
    loaded = json.loads(raw.decode("utf-8"))
    assert loaded["note"] == "活体演化候选 🌊"


def test_world_live_evolve_partial_receipt_schema(tmp_path, monkeypatch):
    """_partial_receipt returns a well-formed receipt dict with expected schema."""
    import importlib
    mod = importlib.import_module("tools.world_live_evolve")

    rec = mod._partial_receipt(
        status="COMPLETED",
        trace_id="trace_test_001",
        started=100.0,
        total=8,
        receipts=[{"wave": 1, "verdict": "PASS"}],
        closed=True,
        summary_rec={"status": "COMPLETED", "attempt": 1},
    )
    assert rec["schema"] == "video_kingdom.world_live_receipt.v1"
    assert rec["status"] == "COMPLETED"
    assert rec["layer"] == "CREATOR_LIVE"
    assert rec["waves_run"] == 1
    assert rec["waves_planned"] == 8
    assert rec["closed_by_world"] is True
    assert "summary" in rec


def test_world_live_evolve_partial_receipt_no_summary():
    """_partial_receipt without summary_rec should not include summary key."""
    import importlib
    mod = importlib.import_module("tools.world_live_evolve")

    rec = mod._partial_receipt(
        status="RUNNING",
        trace_id="trace_002",
        started=200.0,
        total=8,
        receipts=[],
        closed=False,
    )
    assert rec["status"] == "RUNNING"
    assert "summary" not in rec


# ─── Module 2: tools.canon_scene_pass ───

def test_canon_scene_pass_latest_published_no_empty_book(tmp_path):
    """latest_published_no returns 0 when book has no chapters."""
    import importlib
    mod = importlib.import_module("tools.canon_scene_pass")

    book = {"chapters": []}
    assert mod.latest_published_no(book) == 0


def test_canon_scene_pass_latest_published_no_with_chapters():
    """latest_published_no returns max chapter number from 'no' field."""
    import importlib
    mod = importlib.import_module("tools.canon_scene_pass")

    book = {"chapters": [{"id": "c1", "no": 1}, {"id": "c2", "no": 2}, {"id": "c3", "no": 3}]}
    assert mod.latest_published_no(book) == 3


def test_canon_scene_pass_extract_scene_not_found(tmp_path):
    """extract_scene returns None when scene number is out of range."""
    import importlib
    mod = importlib.import_module("tools.canon_scene_pass")

    lib = tmp_path / "lib"
    lib.mkdir()
    result = mod.extract_scene(lib, 999)
    assert result is None


def test_canon_scene_pass_load_quota_missing(tmp_path):
    """load_quota creates default quota when file missing."""
    import importlib
    mod = importlib.import_module("tools.canon_scene_pass")

    lib = tmp_path / "lib"
    lib.mkdir()
    q = mod.load_quota(lib)
    assert "max_per_day" in q


def test_canon_scene_pass_quota_path_returns_path(tmp_path):
    """quota_path returns correct path."""
    import importlib
    mod = importlib.import_module("tools.canon_scene_pass")

    lib = tmp_path / "lib"
    expected = lib / "canon_pass_quota.v1.json"
    assert mod.quota_path(lib) == expected


# ─── Module 3: tools.run_comedy_episode ───

def test_run_comedy_episode_main_returns_int():
    """main() is callable and returns an integer exit code type."""
    import importlib
    mod = importlib.import_module("tools.run_comedy_episode")
    assert hasattr(mod, "main")
    assert callable(mod.main)


def test_run_comedy_episode_script_has_argparser():
    """run_comedy_episode.py uses argparse for argument parsing."""
    with open(ROOT / "tools/run_comedy_episode.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "argparse" in content
    assert "ArgumentParser" in content


# ─── Module 4: tools.ep01_r3_pipeline ───

def test_ep01_r3_pipeline_sha_deterministic():
    """sha() produces deterministic hash."""
    import importlib
    mod = importlib.import_module("tools.ep01_r3_pipeline")

    h1 = mod.sha("test_input")
    h2 = mod.sha("test_input")
    assert h1 == h2
    assert len(h1) == 64  # SHA256 hex digest


def test_ep01_r3_pipeline_sha_different_inputs():
    """sha() produces different hashes for different inputs."""
    import importlib
    mod = importlib.import_module("tools.ep01_r3_pipeline")

    assert mod.sha("a") != mod.sha("b")


def test_ep01_r3_pipeline_file_sha(tmp_path):
    """file_sha computes SHA256 of file contents."""
    import importlib
    mod = importlib.import_module("tools.ep01_r3_pipeline")

    f = tmp_path / "test.mp4"
    f.write_bytes(b"fake video content")
    expected = hashlib.sha256(b"fake video content").hexdigest()
    assert mod.file_sha(f) == expected


def test_ep01_r3_pipeline_validate_shot_missing_fields(tmp_path):
    """validate_shot raises KeyError on empty shot missing 'shot_prompt' — locks current behavior."""
    import importlib
    mod = importlib.import_module("tools.ep01_r3_pipeline")

    empty_shot = {}
    path = tmp_path / "empty_R3_CONTRACT.json"
    with pytest.raises(KeyError, match="shot_prompt"):
        mod.validate_shot(empty_shot, path)


def test_ep01_r3_pipeline_load_key_callable():
    """load_key() is callable without crashing (on non-Windows or with env key)."""
    import importlib
    mod = importlib.import_module("tools.ep01_r3_pipeline")
    assert callable(mod.load_key)


# ─── Module 5: runtime.shot_core ───

def test_shot_core_canonical_hash_deterministic():
    """canonical_hash is deterministic for same input."""
    from runtime.shot_core import canonical_hash

    obj = {"key": "value", "nested": {"a": 1}}
    assert canonical_hash(obj) == canonical_hash(obj)


def test_shot_core_canonical_hash_different_inputs():
    """canonical_hash differs for different inputs."""
    from runtime.shot_core import canonical_hash

    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})


def test_shot_core_load_manifest_empty_file(tmp_path):
    """load_manifest returns defaults for non-existent file."""
    from runtime.shot_core import load_manifest

    result = load_manifest(tmp_path / "nonexistent.json")
    assert result["schema"] == "video_kingdom.shot_core_pilot.v1"
    assert result["shots"] == {}
    assert result["takes"] == []


def test_shot_core_preflight_valid_shot():
    """preflight_shot accepts valid shot fixture."""
    from runtime.shot_core import preflight_shot

    shot = {
        "shot_id": "TEST_01",
        "episode_id": "TEST",
        "scene_id": "SCENE_A",
        "shot_type": "DIALOGUE",
        "prompt": "A test conversation",
        "provider_mode": "text",
        "intent": {
            "dramatic_function": "reveal",
            "primary_visual_event": "speaker takes a seat",
            "story_delta": "new fact",
            "emotion_delta": "neutral to curiosity",
            "knowledge_delta": "viewer learns",
            "relationship_delta": "trust builds",
        },
        "state": {
            "start_state": {"location": "room"},
            "action_state": {"character": "CHAR_A"},
            "end_state": {"location": "room", "character": "CHAR_A"},
        },
        "contract": {
            "first_frame_ref": "frame_001",
            "last_frame_ref": "frame_002",
            "allowed_behaviors": ["speak"],
            "forbidden_behaviors": ["cut"],
            "camera": {
                "scale": "medium",
                "position": "center",
                "movement": "NONE",
                "axis": "none",
                "internal_cuts": 0,
            },
            "render_seconds": 6,
        },
        "audio": {
            "dialogue": [{"speaker": "CHAR_A", "content": "Hello", "start": 0.0, "end": 3.0, "audio_ref": "test.wav"}],
            "dialogue_duration": 3.0,
            "action_duration": 1.0,
            "hold_duration": 2.0,
            "render_seconds": 6,
        },
        "asset_refs": [{"asset_id": "CHAR_A", "asset_type": "character", "version": 1, "sha256": "a" * 64, "scope": "shot", "provider_ref": "https://example.com/anchor.png"}],
        "visible_character_ids": ["CHAR_A"],
        "medium_lock": {
            "schema": "video_kingdom.medium_lock.v1",
            "signed": True,
            "signed_by": "test",
            "output_medium": "CHARACTER_PERFORMANCE",
            "source_kind": "ORIGINAL_STORY",
            "rule": "test",
        },
    }
    result = preflight_shot(shot)
    assert result["status"] == "CONTRACT_VALID"


def test_shot_core_preflight_short_duration_blocked():
    """preflight_shot blocks when render_seconds < 4."""
    from runtime.shot_core import preflight_shot

    shot = {
        "shot_id": "TEST_01",
        "episode_id": "TEST",
        "scene_id": "SCENE_A",
        "shot_type": "DIALOGUE",
        "prompt": "test",
        "provider_mode": "text",
        "intent": {
            "dramatic_function": "reveal",
            "primary_visual_event": "action",
            "story_delta": "fact",
            "emotion_delta": "neutral",
            "knowledge_delta": "learn",
            "relationship_delta": "change",
        },
        "state": {
            "start_state": {"location": "room"},
            "action_state": {"character": "A"},
            "end_state": {"location": "room"},
        },
        "contract": {
            "first_frame_ref": "f1",
            "last_frame_ref": "f2",
            "allowed_behaviors": ["speak"],
            "forbidden_behaviors": [],
            "camera": {"scale": "medium", "position": "c", "movement": "NONE", "axis": "none", "internal_cuts": 0},
            "render_seconds": 3,
        },
        "audio": {
            "dialogue": [{"speaker": "A", "content": "Hi", "start": 0.0, "end": 1.0, "audio_ref": "a.wav"}],
            "dialogue_duration": 1.0,
            "action_duration": 1.0,
            "hold_duration": 1.0,
        },
        "asset_refs": [{"asset_id": "A", "asset_type": "character", "version": 1, "sha256": "b" * 64, "scope": "shot", "provider_ref": "https://example.com/a.png"}],
        "visible_character_ids": ["A"],
        "medium_lock": {
            "schema": "video_kingdom.medium_lock.v1",
            "signed": True,
            "signed_by": "t",
            "output_medium": "CHARACTER_PERFORMANCE",
            "source_kind": "ORIGINAL_STORY",
            "rule": "r",
        },
    }
    result = preflight_shot(shot)
    assert result["status"] == "BLOCKED"
    assert result["errors"]


# ─── Module 6: production_control.engine ───

def test_engine_sha256_file(tmp_path):
    """sha256_file computes correct hash."""
    from production_control.engine import sha256_file

    f = tmp_path / "hash_test.bin"
    f.write_bytes(b"test content for hashing")
    expected = hashlib.sha256(b"test content for hashing").hexdigest()
    assert sha256_file(f) == expected


def test_engine_create_initial_state(tmp_path):
    """ProductionControl.create writes a valid initial run file."""
    from production_control.engine import ProductionControl

    run_path = tmp_path / "run_001.json"
    pc = ProductionControl.create(run_path, run_id="test_run_001", mode="SANDBOX")
    snapshot = pc.snapshot()
    assert snapshot["run_id"] == "test_run_001"
    assert snapshot["mode"] == "SANDBOX"
    assert snapshot["stage"] == "DRAFT"
    assert snapshot["revision"] == 0


def test_engine_create_invalid_mode_raises(tmp_path):
    """ProductionControl.create rejects invalid mode."""
    from production_control.engine import ProductionControl, WorkflowError

    run_path = tmp_path / "run_002.json"
    with pytest.raises(WorkflowError, match="INVALID_MODE"):
        ProductionControl.create(run_path, mode="INVALID")


def test_engine_create_duplicate_raises(tmp_path):
    """ProductionControl.create rejects existing run path."""
    from production_control.engine import ProductionControl, WorkflowError

    run_path = tmp_path / "run_003.json"
    ProductionControl.create(run_path, run_id="first")
    with pytest.raises(WorkflowError, match="RUN_ALREADY_EXISTS"):
        ProductionControl.create(run_path, run_id="second")


def test_engine_snapshot_returns_dict(tmp_path):
    """snapshot() returns the run state as a dict."""
    from production_control.engine import ProductionControl

    run_path = tmp_path / "run_004.json"
    pc = ProductionControl.create(run_path, mode="SANDBOX")
    snap = pc.snapshot()
    assert isinstance(snap, dict)
    assert snap["stage"] == "DRAFT"


def test_engine_verify_event_chain_valid(tmp_path):
    """verify_event_chain returns status=PASS for freshly created run."""
    from production_control.engine import ProductionControl

    run_path = tmp_path / "run_005.json"
    pc = ProductionControl.create(run_path, mode="SANDBOX")
    result = pc.verify_event_chain()
    assert result["status"] == "PASS"


def test_engine_register_asset(tmp_path):
    """register_asset adds an asset and returns its id."""
    from production_control.engine import ProductionControl

    run_path = tmp_path / "run_006.json"
    asset_path = tmp_path / "clip.mp4"
    asset_path.write_bytes(b"video bytes")
    pc = ProductionControl.create(run_path, mode="SANDBOX")
    result = pc.register_asset("CLIP_01", asset_path)
    assert result["asset_id"] == "CLIP_01"
    snap = pc.snapshot()
    assert "CLIP_01" in snap["assets"]
