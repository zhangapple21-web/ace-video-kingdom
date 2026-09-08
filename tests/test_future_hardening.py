import json
import hashlib
from pathlib import Path

import pytest

from tools.burn_subtitles import _require_delivery_review
from tools.patrol_and_doctor import inspect
from tools.run_short_clip import _build_payload
from tools.build_longmen_strict_plan import _compress_webp, _image_reference
from tools.run_idea_pipeline import _materialize_image_response


def test_idea_pipeline_materializes_provider_image_as_bounded_webp(tmp_path: Path):
    from PIL import Image
    import base64
    import io

    source = io.BytesIO()
    Image.new("RGB", (256, 256), (20, 40, 60)).save(source, format="PNG")
    result = {"data": [{"b64_json": base64.b64encode(source.getvalue()).decode("ascii")}]}
    target = tmp_path / "char_main_reference.webp"

    reference = _materialize_image_response(result, target)

    assert target.is_file()
    assert target.suffix == ".webp"
    assert reference["path"] == str(target.resolve())
    assert reference["size_bytes"] == target.stat().st_size
    assert reference["size_bytes"] < 500 * 1024
    assert len(reference["sha256"]) == 64
    with Image.open(target) as image:
        assert image.format == "WEBP"


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


def test_local_image_reference_is_path_hash_metadata_and_bounded_webp(tmp_path: Path):
    from PIL import Image
    import argparse

    source = tmp_path / "source.png"
    Image.new("RGB", (64, 64), (20, 40, 60)).save(source, format="PNG")
    args = argparse.Namespace(model="agnes-video-v2.0", prompt="reference", seconds=5,
                              size="720P", aspect_ratio="9:16", flash_mode="text",
                              seed=None, flash_first_frame_url=None, flash_last_frame_url=None,
                              flash_reference_image_url=[], flash_reference_audio_url=[], reference_video_url=[], reference_video_require_audio=False,
                              image=str(source), keyframe_image=None, width=1152, height=768, num_frames=121,
                              frame_rate=24, negative_prompt=None)

    with pytest.raises(ValueError, match="Provider-compatible"):
        _build_payload(args)


def test_data_uri_image_reference_is_rejected():
    import argparse

    args = argparse.Namespace(model="agnes-video-v2.0", prompt="reference", seconds=5,
                              size="720P", aspect_ratio="9:16", flash_mode="text",
                              seed=None, flash_first_frame_url=None, flash_last_frame_url=None,
                              flash_reference_image_url=[], flash_reference_audio_url=[], reference_video_url=[], reference_video_require_audio=False,
                              image="data:image/png;base64,ZmFrZQ==", keyframe_image=None, width=1152, height=768, num_frames=121,
                              frame_rate=24, negative_prompt=None)

    with pytest.raises(ValueError, match="data URI"):
        _build_payload(args)


def test_longmen_strict_plan_materializes_bounded_webp_reference(tmp_path: Path):
    from PIL import Image

    source = tmp_path / "source.png"
    Image.new("RGB", (128, 128), (20, 40, 60)).save(source, format="PNG")
    target = _compress_webp(source)
    reference = _image_reference(target)

    assert target.suffix == ".webp"
    assert reference["path"] == str(target.resolve())
    assert reference["size_bytes"] == target.stat().st_size
    assert reference["size_bytes"] < 500 * 1024
    assert len(reference["sha256"]) == 64
    with Image.open(target) as image:
        assert image.format == "WEBP"


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
