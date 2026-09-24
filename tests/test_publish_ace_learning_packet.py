import json

import pytest

from tools.publish_ace_learning_packet import publish


def test_publish_accepts_only_video_learning_receipts(tmp_path, monkeypatch):
    import tools.publish_ace_learning_packet as module

    module.VIDEO_ROOT = tmp_path / "video"
    module.ACE_CORE_ROOT = module.Path(r"C:\tmp\ace_core")
    module.ACE_ROOT = tmp_path / "ace"
    run_dir = module.VIDEO_ROOT / "research" / "external_learning_runs"
    run_dir.mkdir(parents=True)
    run = run_dir / "EL-test.json"
    run.write_text(json.dumps({"schema": "video_kingdom.external_learning_run.v1", "run_id": "EL-test", "source_boundary": "PUBLIC_PRIMARY_SOURCES_ONLY", "promotion": {"status": "NONE"}, "records": [{"source_id": "x", "status": "NEW_OR_CHANGED"}]}), encoding="utf-8")
    result = publish(run, module.ACE_ROOT / "08_GOVERNANCE" / "video_learning_bridge" / "bridge.jsonl")
    assert result["packets"] == 1
    assert result["production_integration"] is False
    assert (module.ACE_ROOT / "08_GOVERNANCE" / "video_learning_bridge" / "bridge.jsonl").exists()


def test_publish_rejects_outside_path(tmp_path, monkeypatch):
    import tools.publish_ace_learning_packet as module

    module.VIDEO_ROOT = tmp_path / "video"
    module.ACE_CORE_ROOT = module.Path(r"C:\tmp\ace_core")
    module.ACE_ROOT = tmp_path / "ace"
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="inside_video_learning_runs"):
        publish(outside)


def test_publish_rejects_bad_name_and_output_boundary(tmp_path):
    import tools.publish_ace_learning_packet as module

    module.VIDEO_ROOT = tmp_path / "video"
    module.ACE_CORE_ROOT = module.Path(r"C:\tmp\ace_core")
    module.ACE_ROOT = tmp_path / "ace"
    run_dir = module.VIDEO_ROOT / "research" / "external_learning_runs"
    run_dir.mkdir(parents=True)
    payload = {"schema": "video_kingdom.external_learning_run.v1", "source_boundary": "PUBLIC_PRIMARY_SOURCES_ONLY", "promotion": {"status": "NONE"}, "records": [{"source_id": "x", "status": "NEW_OR_CHANGED"}]}
    bad_name = run_dir / "not-a-run.json"
    bad_name.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="EL_json"):
        publish(bad_name)
    good = run_dir / "EL-good.json"
    good.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="out_must_be_inside"):
        publish(good, tmp_path / "outside.json")


def test_publish_rejects_malformed_receipt(tmp_path):
    import tools.publish_ace_learning_packet as module

    module.VIDEO_ROOT = tmp_path / "video"
    module.ACE_CORE_ROOT = module.Path(r"C:\tmp\ace_core")
    module.ACE_ROOT = tmp_path / "ace"
    run_dir = module.VIDEO_ROOT / "research" / "external_learning_runs"
    run_dir.mkdir(parents=True)
    run = run_dir / "EL-bad.json"
    run.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        publish(run)
