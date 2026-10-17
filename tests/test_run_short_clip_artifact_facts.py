"""Counterexamples against the production runner's artifact status handling.

These drive ``tools/run_short_clip.main()`` end to end with a fake transport, so
they exercise the real status/receipt code path rather than a re-implementation.
Scope is ``legacy`` to keep the harness small; the status and fact logic under
test does not depend on scope.

Each test corresponds to a counterexample named in the 2026-10-17 directive:
provider 404, expired temporary URL, missing local artifact, hash mismatch.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools import run_short_clip

PAYLOAD = b"fake-mp4-bytes"


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, content=b""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.content = content

    def json(self):
        return self._payload

    @property
    def text(self):
        return json.dumps(self._payload)


class FakeTransport:
    """Serves the poll endpoint and the artifact URL separately."""

    def __init__(self, poll_responses, download_response=None, create_response=None):
        self.poll_responses = list(poll_responses)
        self.download_response = download_response
        self.create_response = create_response or FakeResponse(200, {"video_id": "task_new"})
        self.downloaded_urls = []

    def post(self, url, **kwargs):
        return self.create_response

    def get(self, url, **kwargs):
        # The status endpoint is the only one carrying "agnesapi"; everything
        # else is the artifact URL served by the download step.
        if "agnesapi" in url:
            return self.poll_responses.pop(0) if self.poll_responses else FakeResponse(200, {"status": "completed"})
        self.downloaded_urls.append(url)
        return self.download_response


@pytest.fixture()
def runner(monkeypatch, tmp_path):
    """Wire main() with every non-provider concern stubbed out."""
    monkeypatch.setenv("AGNES_API_KEY", "test-only")

    def install(transport):
        monkeypatch.setattr(run_short_clip, "_preflight_public_media_urls", lambda payload: None)
        monkeypatch.setattr(run_short_clip, "_build_payload", lambda args: {"model": args.model, "prompt": args.prompt})
        monkeypatch.setattr(
            run_short_clip,
            "_load_shot_contract",
            lambda path, shot_id: {
                "shot_id": shot_id,
                "prompt": "plain prompt",
                "creative_constraints": {"hard": {}, "flexible": {}, "deferred": []},
                "character_asset_manifest": {"sha256": "pack-sha"},
                "asset_refs": [{"sha256": "anchor-a"}, {"sha256": "anchor-b"}],
            },
        )
        monkeypatch.setattr(run_short_clip, "_bind_project_asset_manifest", lambda shot, payload, contract: None)
        monkeypatch.setattr(run_short_clip, "_verify_manifest_asset_transport", lambda shot: None)
        monkeypatch.setattr(run_short_clip, "_is_zhang_tietie_production_shot", lambda shot: False)
        monkeypatch.setattr(run_short_clip, "admit_provider_request", lambda *a, **k: {"status": "ADMITTED", "request_hash": "hash-1", "preflight": {"errors": []}})
        monkeypatch.setattr(run_short_clip, "assert_admission", lambda *a, **k: None)
        monkeypatch.setattr(run_short_clip, "build_canonical_generation_request", lambda *a, **k: {"shot_id": "S01", "model": "agnes-video-2.5-flash"})
        monkeypatch.setattr(run_short_clip, "requests", transport)
        monkeypatch.setattr(run_short_clip.time, "sleep", lambda _: None)

    def invoke(manifest: Path, output: Path, shot_id="S01"):
        monkeypatch.setattr("sys.argv", [
            "run_short_clip.py", "--shot-id", shot_id, "--prompt", "plain prompt",
            "--shot-contract", str(manifest.parent / "shot.json"),
            "--output", str(output), "--manifest", str(manifest),
            "--admission-scope", "legacy", "--timeout", "5",
        ])
        return run_short_clip.main()

    (manifest_dir := tmp_path).mkdir(exist_ok=True)
    (manifest_dir / "shot.json").write_text(json.dumps({"shot_id": "S01", "prompt": "plain prompt"}), encoding="utf-8")
    return install, invoke, manifest_dir


def _write_prior_record(manifest: Path, record: dict) -> None:
    manifest.write_text(json.dumps([record], ensure_ascii=False), encoding="utf-8")


def _record(manifest: Path, shot_id="S01") -> dict:
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    return next(row for row in rows if row.get("shot_id") == shot_id)


# --------------------------------------------------------------------------- #
# counterexample 1: provider no longer resolves a task we know was generated
# --------------------------------------------------------------------------- #

def test_evicted_task_does_not_rewrite_a_past_success_as_failure(runner, tmp_path):
    install, invoke, manifest_dir = runner
    manifest = manifest_dir / "tasks.json"
    output = manifest_dir / "gone.mp4"
    _write_prior_record(manifest, {
        "shot_id": "S01", "model_id": "agnes-video-2.5-flash", "status": "COMPLETED",
        "video_id": "task_old", "artifact_path": str(output),
        "artifact_sha256": hashlib.sha256(PAYLOAD).hexdigest(), "bytes": len(PAYLOAD),
    })
    install(FakeTransport(poll_responses=[FakeResponse(404, {"code": 404, "message": "task not found"})]))

    code = invoke(manifest, output)

    assert code == 1
    row = _record(manifest)
    # The historical fact must survive a later 404.
    assert row["artifact_sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
    assert row["status"] != "PROVIDER_FAILED"
    assert row["error_class"] == "PROVIDER_TASK_UNRESOLVABLE"
    assert row["reconcile_required"] is True
    facts = row["artifact_assessment"]
    assert facts["generation"]["generated"] is True
    assert facts["local"]["state"] == "ABSENT_LOCAL"
    assert facts["remote"]["state"] == "UNREACHABLE_REMOTE"
    assert facts["delivery_ready"] is False


def test_artifact_url_is_retained_so_a_lost_file_has_a_path_back(runner, tmp_path):
    install, invoke, manifest_dir = runner
    manifest = manifest_dir / "tasks.json"
    output = manifest_dir / "ok.mp4"
    install(FakeTransport(
        poll_responses=[FakeResponse(200, {"status": "completed", "url": "https://cdn/x.mp4"})],
        download_response=FakeResponse(200, headers={"content-type": "video/mp4"}, content=PAYLOAD),
    ))

    code = invoke(manifest, output)

    assert code == 0
    row = _record(manifest)
    assert row["status"] == "COMPLETED"
    assert row["artifact_url"] == "https://cdn/x.mp4"
    assert row["generation_fact"]["artifact_url"] == "https://cdn/x.mp4"
    assert row["download_content_type"] == "video/mp4"
    assert row["artifact_assessment"]["delivery_ready"] is True


# --------------------------------------------------------------------------- #
# counterexample 2: the temporary artifact URL has expired
# --------------------------------------------------------------------------- #

def test_expired_temporary_url_is_a_download_failure_not_a_completion(runner, tmp_path):
    install, invoke, manifest_dir = runner
    manifest = manifest_dir / "tasks.json"
    output = manifest_dir / "expired.mp4"
    install(FakeTransport(
        poll_responses=[FakeResponse(200, {"status": "completed", "url": "https://cdn/expired.mp4"})],
        download_response=FakeResponse(403, headers={"content-type": "text/html"}, content=b"expired"),
    ))

    code = invoke(manifest, output)

    assert code == 1
    row = _record(manifest)
    assert row["status"] == "DOWNLOAD_FAILED"
    assert row["error_class"] == "DOWNLOAD_HTTP_OR_CONTENT_TYPE"
    assert "artifact_sha256" not in row
    assert not output.exists()


# --------------------------------------------------------------------------- #
# counterexample 3: the local artifact is missing on a re-run
# --------------------------------------------------------------------------- #

def test_missing_local_artifact_is_not_short_circuited_as_complete(runner, tmp_path):
    install, invoke, manifest_dir = runner
    manifest = manifest_dir / "tasks.json"
    output = manifest_dir / "vanished.mp4"
    output.write_bytes(PAYLOAD)
    _write_prior_record(manifest, {
        "shot_id": "S01", "model_id": "agnes-video-2.5-flash", "status": "COMPLETED",
        "video_id": "task_old", "artifact_path": str(output),
        "artifact_sha256": hashlib.sha256(PAYLOAD).hexdigest(), "bytes": len(PAYLOAD),
    })
    output.unlink()
    transport = FakeTransport(
        poll_responses=[FakeResponse(200, {"status": "completed", "url": "https://cdn/x.mp4"})],
        download_response=FakeResponse(200, headers={"content-type": "video/mp4"}, content=PAYLOAD),
    )
    install(transport)

    code = invoke(manifest, output)

    # Recovery is attempted rather than the stale COMPLETED being trusted.
    assert transport.downloaded_urls == ["https://cdn/x.mp4"]
    assert code == 0
    assert output.is_file()
    assert _record(manifest)["artifact_assessment"]["delivery_ready"] is True


def test_present_and_verified_artifact_is_short_circuited(runner, tmp_path):
    install, invoke, manifest_dir = runner
    manifest = manifest_dir / "tasks.json"
    output = manifest_dir / "fine.mp4"
    output.write_bytes(PAYLOAD)
    _write_prior_record(manifest, {
        "shot_id": "S01", "model_id": "agnes-video-2.5-flash", "status": "COMPLETED",
        "video_id": "task_old", "artifact_path": str(output),
        "artifact_sha256": hashlib.sha256(PAYLOAD).hexdigest(), "bytes": len(PAYLOAD),
    })
    transport = FakeTransport(poll_responses=[])
    install(transport)

    assert invoke(manifest, output) == 0
    assert transport.downloaded_urls == []  # nothing re-fetched


# --------------------------------------------------------------------------- #
# counterexample 4: local content no longer matches the recorded hash
# --------------------------------------------------------------------------- #

def test_hash_mismatch_refuses_to_report_the_shot_complete(runner, tmp_path):
    install, invoke, manifest_dir = runner
    manifest = manifest_dir / "tasks.json"
    output = manifest_dir / "tampered.mp4"
    output.write_bytes(b"truncated-or-substituted")
    _write_prior_record(manifest, {
        "shot_id": "S01", "model_id": "agnes-video-2.5-flash", "status": "COMPLETED",
        "video_id": "task_old", "artifact_path": str(output),
        "artifact_sha256": hashlib.sha256(PAYLOAD).hexdigest(), "bytes": len(PAYLOAD),
    })
    transport = FakeTransport(poll_responses=[])
    install(transport)

    with pytest.raises(SystemExit, match="does not match the recorded generation hash"):
        invoke(manifest, output)

    assert transport.downloaded_urls == []


def test_refetched_bytes_that_disagree_are_an_integrity_failure(runner, tmp_path):
    install, invoke, manifest_dir = runner
    manifest = manifest_dir / "tasks.json"
    output = manifest_dir / "refetch.mp4"
    _write_prior_record(manifest, {
        "shot_id": "S01", "model_id": "agnes-video-2.5-flash", "status": "COMPLETED",
        "video_id": "task_old", "artifact_path": str(output),
        "generation_fact": {
            "generated": True, "sha256": hashlib.sha256(PAYLOAD).hexdigest(),
            "bytes": len(PAYLOAD), "path": str(output), "video_id": "task_old",
            "artifact_url": "https://cdn/x.mp4", "observed_at": "2026-09-17T00:00:00Z",
        },
    })
    install(FakeTransport(
        poll_responses=[FakeResponse(200, {"status": "completed", "url": "https://cdn/x.mp4"})],
        download_response=FakeResponse(200, headers={"content-type": "video/mp4"}, content=b"different-bytes"),
    ))

    code = invoke(manifest, output)

    assert code == 1
    row = _record(manifest)
    assert row["error_class"] == "REFETCH_SHA256_MISMATCH"
    assert row["status"] != "COMPLETED"
    # The original fact is still the recorded one.
    assert row["generation_fact"]["sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
