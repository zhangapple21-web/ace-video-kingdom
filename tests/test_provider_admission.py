from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from runtime.provider_admission import (
    admit_provider_request,
    assert_admission,
    build_canonical_generation_request,
    delivery_gate,
)
from runtime.shot_core import run_take


def _shot() -> dict:
    return {
        "episode_id": "E1",
        "shot_id": "S01A",
        "prompt": "one bounded action",
        "action": "the hand closes the folder once",
        "camera": {"movement": "NONE", "internal_cuts": 0},
        "visible_entities": ["CHAR_MAIN"],
        "reference_assets": [{"asset_id": "CHAR_MAIN", "sha256": "a" * 64}],
        "duration": 6,
        "audio_contract": {"dialogue_duration": 0},
        "shot_contract": {"single_action": True, "max_primary_actions": 1, "internal_cuts_allowed": 0},
    }


def test_admission_receipt_hashes_one_canonical_request(tmp_path: Path) -> None:
    payload = {"model": "test", "prompt": "one bounded action", "seconds": "6"}
    request = build_canonical_generation_request(
        _shot(), payload, provider="test-provider", endpoint="https://provider.invalid/v1/videos",
        payload_schema="test.v1", model="test", scope="production",
    )
    receipt_path = tmp_path / "admission.json"
    receipt = admit_provider_request(request, receipt_path=receipt_path)
    assert receipt["status"] == "ADMITTED"
    assert receipt["provider_post_allowed"] is True
    assert receipt["request_hash"]
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["request_hash"] == receipt["request_hash"]
    assert_admission(receipt, receipt["request_hash"])


def test_admission_rejects_canonical_conflict(tmp_path: Path) -> None:
    request = build_canonical_generation_request(
        _shot(), {"model": "test", "prompt": "one bounded action"}, provider="p",
        endpoint="https://provider.invalid", payload_schema="test.v1", model="test",
    )
    receipt = admit_provider_request(request, existing_request_hash="0" * 64, receipt_path=tmp_path / "r.json")
    assert receipt["status"] == "REJECTED"
    assert "canonical_request_conflict" in receipt["preflight"]["errors"]
    with pytest.raises(ValueError):
        assert_admission(receipt, receipt["request_hash"])


def test_admission_rejects_local_agnes_reference_before_post(tmp_path: Path) -> None:
    request = build_canonical_generation_request(
        _shot(),
        {
            "model": "agnes-video-v2.0",
            "prompt": "one bounded action",
            "mode": "reference",
            "images": [r"C:\\tmp\\anchor.png"],
        },
        provider="agnes",
        endpoint="https://apihub.agnes-ai.com/v1/videos",
        payload_schema="agnes-video-cli.v1",
        model="agnes-video-v2.0",
    )
    receipt = admit_provider_request(request, receipt_path=tmp_path / "agnes.json")
    assert receipt["status"] == "REJECTED"
    assert "agnes_reference_requires_public_url:0" in receipt["preflight"]["errors"]


def test_assert_admission_rejects_tampered_receipt() -> None:
    request = build_canonical_generation_request(
        _shot(), {"model": "test", "prompt": "one bounded action"}, provider="p",
        endpoint="https://provider.invalid", payload_schema="test.v1", model="test",
    )
    receipt = admit_provider_request(request)
    receipt["canonical_request"]["prompt"] = "mutated after admission"
    with pytest.raises(ValueError, match="canonical request hash"):
        assert_admission(receipt, receipt["request_hash"])


def test_assert_admission_rejects_provider_payload_drift() -> None:
    payload = {"model": "test", "prompt": "one bounded action", "seconds": "6"}
    request = build_canonical_generation_request(
        _shot(), payload, provider="p", endpoint="https://provider.invalid",
        payload_schema="test.v1", model="test",
    )
    receipt = admit_provider_request(request)
    with pytest.raises(ValueError, match="provider payload mismatch"):
        assert_admission(receipt, receipt["request_hash"], provider_payload={**payload, "seconds": "7"})


def test_delivery_gate_never_upgrades_unknown_or_review() -> None:
    review = delivery_gate({"continuity": "PASS", "subtitle": "PASS", "audio": "UNKNOWN", "creative": "PASS"})
    assert review["delivery_approved"] is False
    assert review["status"] == "REVIEW_REQUIRED"
    blocked = delivery_gate({"continuity": "PASS", "subtitle": "PASS", "audio": "PASS", "creative": "FAIL"})
    assert blocked["delivery_approved"] is False
    assert blocked["status"] == "BLOCKED"
    empty = delivery_gate({})
    assert empty["delivery_approved"] is False
    assert empty["status"] == "BLOCKED"


def test_legacy_cli_rejects_before_provider_post(monkeypatch, tmp_path: Path) -> None:
    from tools import run_short_clip

    monkeypatch.setattr(run_short_clip.requests, "post", lambda *args, **kwargs: pytest.fail("POST must not be reached"))
    monkeypatch.setattr(sys, "argv", [
        "run_short_clip.py", "--shot-id", "S01A", "--prompt", "test",
        "--manifest", str(tmp_path / "manifest.json"), "--output", str(tmp_path / "out.mp4"),
    ])
    with pytest.raises(SystemExit, match="episode-contract or --shot-contract is required"):
        run_short_clip.main()


def test_shot_core_chain_persists_receipt_before_fake_provider_boundary(tmp_path: Path) -> None:
    from tests.test_shot_core_runtime import shot_fixture

    class Response:
        status_code = 200
        headers = {}
        text = '{"status":"failed"}'

        def json(self):
            return {"status": "failed", "error": "test-only fake provider"}

    class FakeSession:
        def __init__(self):
            self.posts = 0

        def post(self, *args, **kwargs):
            self.posts += 1
            return Response()

        def get(self, *args, **kwargs):
            return Response()

    manifest = tmp_path / "manifest.json"
    result = run_take(
        shot_fixture(), manifest_path=manifest, output_path=tmp_path / "out.mp4",
        api_key="test-only", session=(session := FakeSession()), timeout=1, poll_delay=1,
    )
    receipt_path = tmp_path / "manifest.PILOT_S01.admission.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert session.posts == 1
    assert receipt["status"] == "ADMITTED"
    assert receipt["request_hash"] == result["request_hash"]
    assert result["provider_status"] == "FAILED"


def test_zhipu_retry_reuses_the_hash_bound_request_payload(monkeypatch, tmp_path: Path) -> None:
    """A retry must re-assert the request body, not the previous response body."""
    from tools import run_zhipu_chore

    source = tmp_path / "brief.txt"
    source.write_text("bounded local research brief", encoding="utf-8")
    output = tmp_path / "result.json"
    monkeypatch.setenv("ZHIPU_KEY", "test-only")
    calls: list[dict] = []
    responses = iter([(429, {"error": "busy"}, 0), (200, {"result": "ok"}, None)])

    def fake_request(key: str, request_payload: dict, timeout: int, *, endpoint: str, admission: dict, request_hash: str):
        calls.append(dict(request_payload))
        return next(responses)

    monkeypatch.setattr(run_zhipu_chore, "_request", fake_request)
    monkeypatch.setattr(run_zhipu_chore.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(sys, "argv", [
        "run_zhipu_chore.py", "--input", str(source), "--output", str(output),
        "--task", "failed_attempt_digest", "--max-attempts", "2",
    ])

    assert run_zhipu_chore.main() == 0
    assert len(calls) == 2
    assert calls[0] == calls[1]
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "COMPLETED"
    assert len(result["attempts"]) == 2
