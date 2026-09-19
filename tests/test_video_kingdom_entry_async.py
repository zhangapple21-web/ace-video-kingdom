from __future__ import annotations

from tools.video_kingdom_entry import (
    AGNES_FLASH_MODEL,
    build_client_token,
    extract_video_id,
    normalize_agnes_video_payload,
    poll_agnes_video,
    to_agnes_transport_payload,
)


def test_flash_payload_normalizes_multi_image_aliases_and_stable_token():
    source = {
        "model": AGNES_FLASH_MODEL,
        "prompt": "one bounded action",
        "images": [" https://cdn.example/a.webp ", {"url": "https://cdn.example/b.webp", "asset_id": "b"}],
    }
    first = normalize_agnes_video_payload(source)
    second = normalize_agnes_video_payload({"prompt": source["prompt"], "input_images": first["input_images"], "model": AGNES_FLASH_MODEL})

    assert first["input_images"] == ["https://cdn.example/a.webp", {"url": "https://cdn.example/b.webp", "asset_id": "b"}]
    assert "images" not in first
    assert first["client_token"] == second["client_token"] == build_client_token(first)
    assert to_agnes_transport_payload(first)["images"] == first["input_images"]
    assert "input_images" not in to_agnes_transport_payload(first)


def test_video_id_extraction_does_not_accept_unrelated_task_id():
    assert extract_video_id({"task_id": "task-1"}) is None
    assert extract_video_id({"data": {"video_id": "video-1", "task_id": "task-1"}}) == "video-1"


def test_poll_is_video_id_only_and_normalizes_nested_async_states():
    class Response:
        def __init__(self, body: dict, status_code: int = 200):
            self._body = body
            self.status_code = status_code
            self.headers: dict[str, str] = {}

        def json(self):
            return self._body

    class Session:
        def __init__(self):
            self.calls: list[dict] = []
            self.responses = iter([
                Response({"data": {"status": "processing"}}),
                Response({"data": {"status": "completed", "video_url": "https://cdn.example/video.mp4"}}),
            ])

        def get(self, endpoint, **kwargs):
            self.calls.append({"endpoint": endpoint, **kwargs})
            return next(self.responses)

    session = Session()
    result = poll_agnes_video("video-1", "test-key", session=session, poll_delay=0.01, sleep=lambda _: None)

    assert result["status"] == "COMPLETED"
    assert result["video_id"] == "video-1"
    assert result["artifact_url"] == "https://cdn.example/video.mp4"
    assert all(call["params"] == {"video_id": "video-1", "model_name": AGNES_FLASH_MODEL} for call in session.calls)
