import base64
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from production_control.image_assets import (
    AssetStore,
    InlineImageError,
    assert_model_boundary,
    build_frame_analysis_plan,
    sample_frame_indices,
)
from production_control.model_transport import build_chat_payload, build_responses_payload
from production_control.projection import prepare_model_request, project_messages


def _data_url(size=(1400, 900)):
    image = Image.new("RGB", size, (30, 90, 160))
    raw = io.BytesIO()
    image.save(raw, format="PNG")
    return "data:image/png;base64," + base64.b64encode(raw.getvalue()).decode("ascii")


def test_repeated_ui_image_is_one_asset_and_never_inline(tmp_path: Path):
    store = AssetStore(tmp_path / "transport")
    data_url = _data_url()
    result = project_messages(
        [{"role": "user", "text": f"第{i}轮参考图", "image": data_url} for i in range(40)],
        asset_store=store,
    )

    assert result["inline_images"] == 24  # stable head + dynamic tail are bounded
    assert result["image_bytes"] == 0
    assert len(result["unique_asset_ids"]) == 1
    assert all("data:image" not in json.dumps(message) for message in result["messages"])
    assert all("b64_json" not in message and "data" not in message for message in result["messages"])
    assert len(json.dumps(result["messages"], ensure_ascii=False)) < 20_000
    short = prepare_model_request([{"role": "user", "text": "参考图", "image": data_url}], asset_store=store)
    long = prepare_model_request([{"role": "user", "text": "参考图", "image": data_url}] * 1000, asset_store=store)
    assert len(long["messages"]) == 24
    bounded = prepare_model_request([{"role": "user", "text": "参考图", "image": data_url}] * 1000, asset_store=store, stable_head=1000, dynamic_tail=1000)
    assert len(bounded["messages"]) == bounded["projection"]["history_cap"] == 24
    assert len(json.dumps(long, ensure_ascii=False)) < len(json.dumps(short, ensure_ascii=False)) * 30


def test_model_boundary_rejects_inline_and_accepts_asset_reference(tmp_path: Path):
    with pytest.raises(InlineImageError):
        assert_model_boundary({"messages": [{"role": "user", "image_url": "data:image/png;base64,AAAA"}]})
    with pytest.raises(InlineImageError):
        assert_model_boundary({"messages": [{"role": "user", "b64_json": "AAAA"}]})

    store = AssetStore(tmp_path / "transport")
    payload = prepare_model_request([{"role": "user", "image": _data_url()}], asset_store=store)
    assert payload["asset_ids"]
    assert_model_boundary(payload)
    assert "data:image" not in json.dumps(payload)
    assert "b64_json" not in json.dumps(payload)


def test_openai_nested_image_content_is_projected_then_resolved_at_provider_edge(tmp_path: Path):
    public_url = "https://raw.githubusercontent.com/zhangapple21-web/-/main/ace-video-kingdom/wenji-episode-006/SCENE_02_typing_log_anchor.png"
    payload, model_request = build_chat_payload(
        model="gpt-5.4",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "描述这张图，只返回一句话"},
                    {"type": "image_url", "image_url": {"url": public_url}},
                ],
            }
        ],
        asset_store=tmp_path / "transport",
    )
    assert model_request["asset_ids"]
    assert payload["messages"][0]["content"][1]["image_url"]["url"] == public_url
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "data:image" not in serialized
    assert "b64_json" not in serialized
    assert "asset_id" not in serialized


def test_responses_payload_uses_public_reference_not_inline_image(tmp_path: Path):
    public_url = "https://raw.githubusercontent.com/zhangapple21-web/-/main/ace-video-kingdom/wenji-episode-006/SCENE_02_typing_log_anchor.png"
    payload, model_request = build_responses_payload(
        model="gpt-5.4-mini",
        messages=[{"role": "user", "content": [{"type": "text", "text": "描述"}, {"type": "image_url", "image_url": {"url": public_url}}]}],
        asset_store=tmp_path / "transport",
        max_output_tokens=20,
    )
    assert model_request["asset_ids"]
    assert payload["input"][0]["content"][1] == {"type": "input_image", "image_url": public_url}
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "data:image" not in serialized and "b64_json" not in serialized


def test_derived_variants_are_lazy_and_vision_analysis_is_reused(tmp_path: Path):
    store = AssetStore(tmp_path / "transport")
    reference = store.register(base64.b64decode(_data_url().split(",", 1)[1]), mime="image/png")
    asset_id = reference["asset_id"]
    manifest_dir = tmp_path / "transport" / "assets" / reference["sha256"][:2] / reference["sha256"]
    assert not (manifest_dir / "768.webp").exists()
    derived = store.derive(asset_id, "768")
    assert derived.exists()
    assert Path(store.resolve_for_provider(reference, variant="768")) == derived
    assert not (manifest_dir / "1280.webp").exists()

    calls = []

    def analyzer(ref):
        calls.append(ref)
        return {"summary": "蓝色测试图"}

    first, cached_first = store.analyze_once(asset_id, "vision:v1", analyzer)
    second, cached_second = store.analyze_once(asset_id, "vision:v1", analyzer)
    assert first == second
    assert cached_first is False
    assert cached_second is True
    assert len(calls) == 1
    assert calls[0]["variant"] == "768"


def test_frame_analysis_samples_and_limits_suspects():
    assert sample_frame_indices(1000, max_samples=10) == [0, 111, 222, 333, 444, 555, 666, 777, 888, 999]
    frames = [{"frame_id": i, "suspect": i in {3, 701}} for i in range(1000)]
    plan = build_frame_analysis_plan(frames, max_samples=10, max_suspects=4)
    assert plan["total_frames"] == 1000
    assert 3 in plan["selected_indices"] and 701 in plan["selected_indices"]
    assert plan["high_cost_indices"] == [3, 701]
    assert len(plan["selected_indices"]) <= 14
    assert plan["omitted_frames"] > 0


def test_projection_does_not_inject_all_video_frames(tmp_path: Path):
    store = AssetStore(tmp_path / "transport")
    frames = [{"image": _data_url((64, 64)), "suspect": i == 37} for i in range(100)]
    result = project_messages([{"role": "user", "text": "抽样检查", "frames": frames}], asset_store=store)
    message = result["messages"][0]
    assert len(message["frames"]) <= 25
    assert message["frame_analysis_plan"]["omitted_frames"] > 0
    assert all("data:image" not in json.dumps(frame) for frame in message["frames"])
