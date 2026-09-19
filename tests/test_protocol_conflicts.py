import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dispatch_kernel_does_not_make_scene_anchor_a_global_submission_gate():
    kernel = json.loads(
        (ROOT / "governance" / "short_drama_dispatch_kernel.v1.json").read_text(encoding="utf-8")
    )
    boundary = kernel["capability_boundary"]
    assert boundary["verified_video_paths"] == ["agnes-video-2.5-flash"]
    gate = kernel["asset_gate"]
    assert "scene_action_anchor" not in gate["required_before_submission"]
    assert "scene_action_anchor" in gate["optional_before_submission"]


def test_archived_short_series_manifest_cannot_switch_video_provider():
    manifest = json.loads(
        (ROOT / "experiments" / "short_series_pipeline.v1.json").read_text(encoding="utf-8")
    )
    assignments = manifest["model_assignments"]
    assert assignments["video"] == "agnes-video-2.5-flash"
    assert assignments["video_fallback"] is None
    assert assignments["fallback_policy"].startswith("NO_PROVIDER_SWITCH")
    assert assignments["lifecycle"] == "ARCHIVED_REFERENCE_ONLY"
