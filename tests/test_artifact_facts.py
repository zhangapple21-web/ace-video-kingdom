"""Counterexamples for the facts a generation receipt was asked to carry at once.

Each test here corresponds to a real failure mode, not a hypothetical one.
The first three reproduce defects that existed before ``tools/artifact_facts.py``
was wired into ``run_short_clip.py``; the rest lock the corrected behaviour in.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import artifact_facts
from tools.artifact_facts import (
    LOCAL_ABSENT,
    LOCAL_MISMATCH,
    LOCAL_VERIFIED,
    REMOTE_REACHABLE,
    REMOTE_UNREACHABLE,
    assess,
    delivery_block_reason,
    delivery_ready,
    record_generation_fact,
    record_remote_probe,
)

PAYLOAD = b"video-bytes-for-testing"


def _completed_record(path, sha, *, video_id="task_v1", artifact_url=None, **extra):
    record = {
        "shot_id": "S01",
        "model_id": "agnes-video-2.5-flash",
        "status": "COMPLETED",
        "video_id": video_id,
        "artifact_path": str(path),
        "artifact_sha256": sha,
        "bytes": len(PAYLOAD),
    }
    record.update(extra)
    return record


@pytest.fixture()
def written_artifact(tmp_path):
    import hashlib

    path = tmp_path / "shot.mp4"
    path.write_bytes(PAYLOAD)
    return path, hashlib.sha256(PAYLOAD).hexdigest()


# --------------------------------------------------------------------------- #
# the five facts stay separate
# --------------------------------------------------------------------------- #

def test_generated_once_but_file_gone_is_not_generation_failure(written_artifact, tmp_path):
    """A lost file must never be re-labelled as a failed generation."""
    path, sha = written_artifact
    record = _completed_record(tmp_path / "vanished.mp4", sha)

    result = assess(record, manifest_dir=tmp_path)

    assert result["generation"]["generated"] is True
    assert result["local"]["state"] == LOCAL_ABSENT
    assert result["delivery_ready"] is False
    # The single most important assertion: the generation fact survives.
    assert result["generation"]["sha256"] == sha


def test_provider_404_does_not_rewrite_the_generation_fact(written_artifact, tmp_path):
    """The exact regression from the 2026-10-17 incident."""
    path, sha = written_artifact
    path.unlink()
    record = _completed_record(path, sha)
    record["generation_fact"] = record_generation_fact(
        record, path=path, sha256=sha, bytes_count=len(PAYLOAD), video_id="task_v1", artifact_url="https://cdn/x.mp4",
    )

    record_remote_probe(record, reachable=False, http_status=404, error_class="HTTP_404")
    # A re-run that discovers the task is gone must not conclude generation failed.
    record["status"] = "COMPLETED"

    result = assess(record, manifest_dir=tmp_path)
    assert result["generation"]["generated"] is True
    assert result["remote"]["state"] == REMOTE_UNREACHABLE
    assert result["recoverable"] is False
    assert "provider no longer resolves" in delivery_block_reason(result)


def test_local_hash_mismatch_is_detected_not_accepted(written_artifact, tmp_path):
    """Content that no longer matches the recorded hash must not read as complete."""
    path, sha = written_artifact
    path.write_bytes(b"tampered-or-truncated")

    record = _completed_record(path, sha)
    result = assess(record, manifest_dir=tmp_path)

    assert result["local"]["state"] == LOCAL_MISMATCH
    assert result["local"]["hash_verified"] is False
    assert result["delivery_ready"] is False
    assert delivery_ready(record, manifest_dir=tmp_path) is False


def test_recorded_path_alone_is_not_evidence(written_artifact, tmp_path):
    """A COMPLETED status plus a path is a claim, not a verification."""
    path, sha = written_artifact
    path.unlink()
    record = _completed_record(path, sha)
    assert record["status"] == "COMPLETED"
    assert delivery_ready(record, manifest_dir=tmp_path) is False


def test_no_generation_fact_is_not_delivery_ready():
    assert delivery_ready({"status": "CREATING"}) is False


def test_verified_local_artifact_is_delivery_ready(written_artifact, tmp_path):
    path, sha = written_artifact
    record = _completed_record(path, sha)
    record["generation_fact"] = record_generation_fact(
        record, path=path, sha256=sha, bytes_count=len(PAYLOAD), video_id="task_v1", artifact_url=None,
    )
    result = assess(record, manifest_dir=tmp_path)
    assert result["local"]["state"] == LOCAL_VERIFIED
    assert result["local"]["hash_verified"] is True
    assert result["delivery_ready"] is True
    assert delivery_block_reason(result) is None


# --------------------------------------------------------------------------- #
# recoverability
# --------------------------------------------------------------------------- #

def test_a_confirmed_reachable_url_is_a_recovery_path_even_if_the_file_is_gone(written_artifact, tmp_path):
    path, sha = written_artifact
    path.unlink()
    record = _completed_record(path, sha)
    record_remote_probe(record, reachable=True, artifact_url="https://cdn/x.mp4", http_status=200)

    result = assess(record, manifest_dir=tmp_path)
    assert result["local"]["state"] == LOCAL_ABSENT
    assert result["remote"]["state"] == REMOTE_REACHABLE
    assert result["recoverable"] is True
    # Recoverable is not deliverable: the chain still needs the bytes here.
    assert result["delivery_ready"] is False


def test_a_recorded_but_unchecked_url_is_not_recoverability(written_artifact, tmp_path):
    """A URL nobody confirmed is not a recovery path."""
    path, sha = written_artifact
    path.unlink()
    record = _completed_record(path, sha)
    record["artifact_url"] = "https://cdn/x.mp4"  # never probed
    result = assess(record, manifest_dir=tmp_path)
    assert result["remote"]["state"] == "UNKNOWN_REMOTE"
    assert result["recoverable"] is False


def test_generation_fact_is_write_once():
    record: dict = {}
    first_path = Path("/a.mp4")
    first = record_generation_fact(record, path=first_path, sha256="aaa", bytes_count=1, video_id="v1", artifact_url="https://cdn/a")
    second = record_generation_fact(record, path=Path("/b.mp4"), sha256="bbb", bytes_count=2, video_id="v2", artifact_url="https://cdn/b")
    assert first == second
    assert record["generation_fact"]["sha256"] == "aaa"
    assert record["generation_fact"]["path"] == str(first_path)


def test_generation_fact_records_the_remote_handle(written_artifact):
    """The missing artifact_url is why the incident had no path back."""
    path, sha = written_artifact
    record: dict = {}
    fact = record_generation_fact(record, path=path, sha256=sha, bytes_count=len(PAYLOAD), video_id="task_v1", artifact_url="https://cdn/x.mp4")
    assert fact["artifact_url"] == "https://cdn/x.mp4"
    assert json.loads(json.dumps(fact))["artifact_url"] == "https://cdn/x.mp4"


def test_assessment_is_serializable_for_a_receipt():
    result = assess({"status": "COMPLETED", "artifact_path": None})
    assert json.loads(json.dumps(result))["schema"] == "video_kingdom.artifact_facts.v1"
