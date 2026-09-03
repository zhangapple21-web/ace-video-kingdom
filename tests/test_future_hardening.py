import json
import hashlib
from pathlib import Path

import pytest

from tools.burn_subtitles import _require_delivery_review
from tools.patrol_and_doctor import inspect
from tools.run_short_clip import _build_payload


def test_patrol_has_no_duplicate_shot_ids_in_current_manifests():
    report = inspect(Path(__file__).parents[1])
    assert not any(item.get("issue") == "DUPLICATE_SHOT_ID_ACROSS_MANIFESTS" for item in report["warnings"])


def test_payload_fingerprint_input_is_stable():
    import argparse
    args = argparse.Namespace(model="agnes-video-2.5-flash", prompt="a distinct action", seconds=5,
                              size="720P", aspect_ratio="9:16", flash_mode="reference",
                              seed=None, flash_first_frame_url=None, flash_last_frame_url=None,
                              flash_reference_image_url=["https://example.invalid/anchor.png"],
                              flash_reference_audio_url=[], reference_video_url=[], reference_video_require_audio=False,
                              image=None, keyframe_image=None, width=1152, height=768, num_frames=121,
                              frame_rate=24, negative_prompt=None)
    payload = _build_payload(args)
    assert json.dumps(payload, sort_keys=True, separators=(",", ":"))
    assert payload["mode"] == "reference"


def test_final_packaging_requires_a_hash_bound_approved_review(tmp_path: Path):
    base = tmp_path / "base.mp4"
    base.write_bytes(b"verified base")
    with pytest.raises(SystemExit, match="delivery-review"):
        _require_delivery_review(base, tmp_path / "episode_final.mp4", None)
    review = tmp_path / "review.json"
    review.write_text(json.dumps({
        "project_id": "test_project",
        "status": "DELIVERY_APPROVED",
        "source_sha256": hashlib.sha256(base.read_bytes()).hexdigest(),
        "reviewed_shot_ids": ["S01"],
        "identity_verdict": "PASS",
        "narrative_verdict": "PASS",
        "subtitle_sync_verdict": "PASS",
        "audio_verdict": "NOT_REQUESTED",
    }), encoding="utf-8")
    _require_delivery_review(base, tmp_path / "episode_final.mp4", review)
