"""A recorded path is ambiguous, and guessing wrong produces a false ABSENT.

Records in this project carry ``artifact_path`` values that are relative to the
repository root (``media_staging/episode_002_shot_004.mp4``) while other records
carry absolute paths. Resolving a relative path against only the manifest
directory reports present media as absent, which blocks delivery on good
footage. These tests pin the search behaviour, the project-wide audit, and the
per-shot gate that consumes it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools import artifact_facts, audit_artifact_integrity
from tools.artifact_facts import LOCAL_ABSENT, LOCAL_VERIFIED

PAYLOAD = b"episode-002-shot-bytes"


@pytest.fixture()
def repo_shaped(tmp_path):
    """A manifest in <root>/experiments whose artifact lives in <root>/."""
    root = tmp_path / "repo"
    (root / "experiments").mkdir(parents=True)
    staging = root / "media_staging"
    staging.mkdir()
    artifact = staging / "episode_002_shot_004.mp4"
    artifact.write_bytes(PAYLOAD)
    record = {
        "shot_id": "episode_002_shot_004",
        "status": "COMPLETED",
        "artifact_path": "media_staging/episode_002_shot_004.mp4",  # relative to the ROOT
        "artifact_sha256": hashlib.sha256(PAYLOAD).hexdigest(),
        "bytes": len(PAYLOAD),
    }
    manifest = root / "experiments" / "agnes_tasks.json"
    manifest.write_text(json.dumps([record]), encoding="utf-8")
    return root, manifest, artifact


def test_relative_path_resolves_against_the_repo_root_not_only_the_manifest(repo_shaped):
    """The false alarm this fixes: media present, reported absent."""
    root, manifest, _artifact = repo_shaped
    record = json.loads(manifest.read_text(encoding="utf-8"))[0]

    # Manifest-directory only: misses, because the path is root-relative.
    naive = artifact_facts.classify_local(record, manifest_dir=manifest.resolve().parent)
    assert naive["state"] == LOCAL_ABSENT

    # With the repository root offered as a candidate, it is found and verified.
    found = artifact_facts.assess(
        record, manifest_dir=manifest.resolve().parent, roots=[manifest.resolve().parent, root],
    )
    assert found["local"]["state"] == LOCAL_VERIFIED
    assert found["local"]["hash_verified"] is True
    assert found["delivery_ready"] is True


def test_the_root_actually_matched_is_recorded(repo_shaped):
    root, manifest, _artifact = repo_shaped
    record = json.loads(manifest.read_text(encoding="utf-8"))[0]
    local = artifact_facts.classify_local(record, roots=[manifest.resolve().parent, root])
    assert local["resolved_path"] == str((root / "media_staging" / "episode_002_shot_004.mp4").resolve())
    assert [str(r) for r in local["searched_roots"]]


def test_manifest_relative_path_is_still_found(tmp_path):
    manifest_dir = tmp_path / "experiments"
    (manifest_dir / "media_staging").mkdir(parents=True)
    artifact = manifest_dir / "media_staging" / "a.mp4"
    artifact.write_bytes(PAYLOAD)
    record = {"shot_id": "a", "status": "COMPLETED", "artifact_path": "media_staging/a.mp4",
              "artifact_sha256": hashlib.sha256(PAYLOAD).hexdigest()}
    local = artifact_facts.classify_local(record, manifest_dir=manifest_dir)
    assert local["state"] == LOCAL_VERIFIED


def test_absolute_path_needs_no_root(tmp_path):
    artifact = tmp_path / "x.mp4"
    artifact.write_bytes(PAYLOAD)
    record = {"shot_id": "x", "status": "COMPLETED", "artifact_path": str(artifact),
              "artifact_sha256": hashlib.sha256(PAYLOAD).hexdigest()}
    assert artifact_facts.classify_local(record, roots=[])["state"] == LOCAL_VERIFIED


def test_audit_reports_present_media_as_ready(repo_shaped):
    root, manifest, _artifact = repo_shaped
    receipt = audit_artifact_integrity.audit([manifest], roots=[root])
    assert receipt["verdict"] == "PASS"
    assert receipt["totals"]["delivery_ready"] == 1
    assert receipt["totals"]["generated_but_unrecoverable"] == 0
    assert receipt["approves_delivery"] is False


def test_audit_separates_verified_from_genuinely_lost(tmp_path):
    root = tmp_path / "repo"
    (root / "media_staging").mkdir(parents=True)
    good = root / "media_staging" / "good.mp4"
    good.write_bytes(PAYLOAD)
    sha = hashlib.sha256(PAYLOAD).hexdigest()
    manifest = root / "experiments" / "tasks.json"
    manifest.parent.mkdir(exist_ok=True)
    manifest.write_text(json.dumps([
        {"shot_id": "good", "status": "COMPLETED", "artifact_path": "media_staging/good.mp4", "artifact_sha256": sha},
        {"shot_id": "lost", "status": "COMPLETED", "artifact_path": "media_staging/lost.mp4", "artifact_sha256": sha},
    ]), encoding="utf-8")

    receipt = audit_artifact_integrity.audit([manifest], roots=[root])
    assert receipt["verdict"] == "REVIEW_REQUIRED"
    assert receipt["totals"]["delivery_ready"] == 1
    assert receipt["totals"]["not_delivery_ready"] == 1
    assert [s["shot_id"] for s in receipt["generated_but_unrecoverable"]] == ["lost"]
    assert receipt["local_states"] == {LOCAL_VERIFIED: 1, LOCAL_ABSENT: 1}


def test_audit_fails_closed_on_an_unreadable_manifest(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text("{not json", encoding="utf-8")
    receipt = audit_artifact_integrity.audit([bad])
    assert receipt["verdict"] == "BLOCKED"
    assert receipt["unreadable_manifests"]


def test_audit_never_approves_delivery(tmp_path):
    """Availability is not approval, no matter how clean it is."""
    good = tmp_path / "g.mp4"
    good.write_bytes(PAYLOAD)
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps([{"shot_id": "g", "status": "COMPLETED", "artifact_path": str(good),
                                    "artifact_sha256": hashlib.sha256(PAYLOAD).hexdigest()}]), encoding="utf-8")
    assert audit_artifact_integrity.audit([manifest])["approves_delivery"] is False


# --------------------------------------------------------------------------- #
# the per-shot gate the episode runner now calls
# --------------------------------------------------------------------------- #

def test_runner_gate_blocks_a_missing_artifact(tmp_path, monkeypatch):
    from tools import run_comedy_episode

    manifest = tmp_path / "tasks.json"
    manifest.write_text(json.dumps([
        {"shot_id": "S01", "status": "COMPLETED", "artifact_path": str(tmp_path / "gone.mp4"),
         "artifact_sha256": "deadbeef"},
    ]), encoding="utf-8")
    with pytest.raises(SystemExit, match="artifact integrity blocked for S01"):
        run_comedy_episode._verify_shot_artifact(manifest, "S01")


def test_runner_gate_blocks_a_hash_mismatch(tmp_path):
    from tools import run_comedy_episode

    artifact = tmp_path / "shot.mp4"
    artifact.write_bytes(b"truncated")
    manifest = tmp_path / "tasks.json"
    manifest.write_text(json.dumps([
        {"shot_id": "S01", "status": "COMPLETED", "artifact_path": str(artifact),
         "artifact_sha256": hashlib.sha256(b"the-original").hexdigest()},
    ]), encoding="utf-8")
    with pytest.raises(SystemExit, match="does not match the recorded generation hash"):
        run_comedy_episode._verify_shot_artifact(manifest, "S01")


def test_runner_gate_blocks_when_the_record_is_missing(tmp_path):
    from tools import run_comedy_episode

    manifest = tmp_path / "tasks.json"
    manifest.write_text(json.dumps([]), encoding="utf-8")
    with pytest.raises(SystemExit, match="no durable manifest record"):
        run_comedy_episode._verify_shot_artifact(manifest, "S01")


def test_runner_gate_passes_a_verified_shot(tmp_path):
    from tools import run_comedy_episode

    artifact = tmp_path / "shot.mp4"
    artifact.write_bytes(PAYLOAD)
    manifest = tmp_path / "tasks.json"
    manifest.write_text(json.dumps([
        {"shot_id": "S01", "status": "COMPLETED", "artifact_path": str(artifact),
         "artifact_sha256": hashlib.sha256(PAYLOAD).hexdigest()},
    ]), encoding="utf-8")
    assert run_comedy_episode._verify_shot_artifact(manifest, "S01")["delivery_ready"] is True


def test_assembler_shares_the_same_rule_and_still_fails_closed(tmp_path, monkeypatch):
    """The assembler used to re-implement this check inline. Both must agree."""
    from tools import assemble_episode

    artifact = tmp_path / "shot.mp4"
    artifact.write_bytes(b"truncated")
    manifest = tmp_path / "tasks.json"
    manifest.write_text(json.dumps([
        {"shot_id": "S01", "status": "COMPLETED", "artifact_path": str(artifact),
         "artifact_sha256": hashlib.sha256(b"the-original").hexdigest()},
    ]), encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "assemble_episode.py", "--manifest", str(manifest), "--shot-ids", "S01",
        "--output", str(tmp_path / "out.mp4"),
    ])
    with pytest.raises(SystemExit, match="artifact hash mismatch for S01"):
        assemble_episode.main()


def test_assembler_accepts_the_same_shot_the_audit_calls_ready(tmp_path, monkeypatch):
    """Positive path for the shared rule: a verified shot clears both."""
    import hashlib as _hashlib

    from tools import assemble_episode

    artifact = tmp_path / "shot.mp4"
    artifact.write_bytes(PAYLOAD)
    sha = _hashlib.sha256(PAYLOAD).hexdigest()
    manifest = tmp_path / "tasks.json"
    manifest.write_text(json.dumps([
        {"shot_id": "S01", "status": "COMPLETED", "artifact_path": str(artifact), "artifact_sha256": sha},
    ]), encoding="utf-8")

    # It must get past the integrity check and reach ffprobe, which this
    # non-media fixture cannot satisfy. Reaching that point proves the
    # verification gate passed rather than being skipped.
    monkeypatch.setattr("sys.argv", [
        "assemble_episode.py", "--manifest", str(manifest), "--shot-ids", "S01",
        "--output", str(tmp_path / "out.mp4"),
    ])
    monkeypatch.setattr(assemble_episode, "probe_media", lambda path: {"duration_seconds": 1.0, "width": 1080, "height": 1920})
    with pytest.raises(Exception) as caught:
        assemble_episode.main()
    assert "missing completed artifact" not in str(caught.value)
    assert "artifact hash mismatch" not in str(caught.value)


# --------------------------------------------------------------------------- #
# "absent" only means gone once the recorded bytes have been looked for
# --------------------------------------------------------------------------- #

def test_find_by_hash_matches_content_not_filename(tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir()
    renamed = archive / "totally_different_name_v2.mp4"
    renamed.write_bytes(PAYLOAD)
    assert audit_artifact_integrity.find_by_hash(hashlib.sha256(PAYLOAD).hexdigest(), [archive]) == [str(renamed)]


def test_find_by_hash_ignores_a_different_file(tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "other.mp4").write_bytes(b"re-encoded, different bytes")
    assert audit_artifact_integrity.find_by_hash(hashlib.sha256(PAYLOAD).hexdigest(), [archive]) == []


def test_find_by_hash_skips_by_size_before_hashing(tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir()
    candidate = archive / "sized.mp4"
    candidate.write_bytes(PAYLOAD)
    # A wrong size hint must not produce a match even though content would.
    assert audit_artifact_integrity.find_by_hash(
        hashlib.sha256(PAYLOAD).hexdigest(), [archive], size_hint=len(PAYLOAD) + 99,
    ) == []
    assert audit_artifact_integrity.find_by_hash(
        hashlib.sha256(PAYLOAD).hexdigest(), [archive], size_hint=len(PAYLOAD),
    ) == [str(candidate)]


def test_find_by_hash_does_not_move_or_edit_anything(tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir()
    keep = archive / "keep.mp4"
    keep.write_bytes(PAYLOAD)
    before = sorted(p.name for p in archive.iterdir())
    audit_artifact_integrity.find_by_hash(hashlib.sha256(PAYLOAD).hexdigest(), [archive])
    assert sorted(p.name for p in archive.iterdir()) == before
    assert keep.read_bytes() == PAYLOAD


def test_missing_artifact_found_elsewhere_is_recoverable_not_unrecoverable(tmp_path):
    """A moved file must not be reported as lost."""
    root = tmp_path / "repo"
    (root / "experiments").mkdir(parents=True)
    archive = root / "archive_copy"
    archive.mkdir()
    (archive / "renamed_on_the_way.mp4").write_bytes(PAYLOAD)
    sha = hashlib.sha256(PAYLOAD).hexdigest()
    manifest = root / "experiments" / "tasks.json"
    manifest.write_text(json.dumps([
        {"shot_id": "moved", "status": "COMPLETED", "artifact_path": "media_staging/moved.mp4",
         "artifact_sha256": sha, "bytes": len(PAYLOAD)},
    ]), encoding="utf-8")

    receipt = audit_artifact_integrity.audit([manifest], roots=[root], search_roots=[archive])
    shot = receipt["not_delivery_ready"][0]
    assert shot["recoverable_offline"] is True
    assert shot["recovery_locations"] == [str(archive / "renamed_on_the_way.mp4")]
    assert receipt["totals"]["generated_but_unrecoverable"] == 0
    assert receipt["totals"]["recovered_offline"] == 1
    # Still not delivery-ready: the bytes are somewhere else, not here.
    assert shot["delivery_ready"] is False


def test_absent_and_searched_and_still_gone_counts_as_unrecoverable(tmp_path):
    root = tmp_path / "repo"
    (root / "experiments").mkdir(parents=True)
    empty = root / "nowhere"
    empty.mkdir()
    manifest = root / "experiments" / "tasks.json"
    manifest.write_text(json.dumps([
        {"shot_id": "gone", "status": "COMPLETED", "artifact_path": "media_staging/gone.mp4",
         "artifact_sha256": hashlib.sha256(PAYLOAD).hexdigest(), "bytes": len(PAYLOAD)},
    ]), encoding="utf-8")

    receipt = audit_artifact_integrity.audit([manifest], roots=[root], search_roots=[empty])
    assert receipt["totals"]["generated_but_unrecoverable"] == 1
    assert receipt["totals"]["recovered_offline"] == 0


# --------------------------------------------------------------------------- #
# the automatic gate: availability is a lane, so nobody has to remember to check
# --------------------------------------------------------------------------- #

def _record_for(path, sha, status="COMPLETED"):
    return {"shot_id": "S01", "status": status, "artifact_path": str(path), "artifact_sha256": sha}


def test_availability_lane_passes_a_verified_artifact(tmp_path):
    artifact = tmp_path / "ok.mp4"
    artifact.write_bytes(PAYLOAD)
    sha = hashlib.sha256(PAYLOAD).hexdigest()
    assert artifact_facts.availability_lane(_record_for(artifact, sha)) == "PASS"


def test_availability_lane_fails_a_missing_artifact(tmp_path):
    sha = hashlib.sha256(PAYLOAD).hexdigest()
    assert artifact_facts.availability_lane(_record_for(tmp_path / "gone.mp4", sha)) == "FAIL"


def test_availability_lane_fails_a_tampered_artifact(tmp_path):
    artifact = tmp_path / "bad.mp4"
    artifact.write_bytes(b"substituted")
    sha = hashlib.sha256(PAYLOAD).hexdigest()
    assert artifact_facts.availability_lane(_record_for(artifact, sha)) == "FAIL"


def test_availability_lane_is_not_proven_without_a_generation_fact():
    """A record that claims nothing verifiable cannot claim a pass either."""
    assert artifact_facts.availability_lane({"shot_id": "S01", "status": "CREATING"}) == "NOT_PROVEN"
    assert artifact_facts.availability_lane({"shot_id": "S01"}) == "NOT_PROVEN"


def test_availability_lane_is_worst_wins_across_shots(tmp_path):
    good = tmp_path / "good.mp4"
    good.write_bytes(PAYLOAD)
    sha = hashlib.sha256(PAYLOAD).hexdigest()
    records = {
        "S01": _record_for(good, sha),
        "S02": _record_for(tmp_path / "gone.mp4", sha),
        "S03": {"shot_id": "S03"},
    }
    lane, detail = artifact_facts.availability_lane_for_shots(records, ["S01", "S02", "S03"])
    assert lane == "FAIL"
    assert detail["S01"]["lane"] == "PASS"
    assert detail["S02"]["lane"] == "FAIL"
    assert detail["S03"]["lane"] == "NOT_PROVEN"

    lane, _ = artifact_facts.availability_lane_for_shots({"S01": _record_for(good, sha)}, ["S01"])
    assert lane == "PASS"


def test_a_shot_with_no_record_at_all_blocks_rather_than_passes():
    lane, detail = artifact_facts.availability_lane_for_shots({}, ["S01"])
    assert lane == "NOT_PROVEN"
    assert "no durable manifest record" in detail["S01"]["reason"]


def test_six_passing_qc_lanes_cannot_approve_unverified_media(tmp_path):
    """The exact hole: all quality lanes green, artifact never verified."""
    from runtime.provider_admission import delivery_gate

    perfect_qc = {
        "media_integrity": "PASS",
        "continuity": "PASS",
        "repetition": "PASS",
        "subtitle": "PASS",
        "audio": "PASS",
        "creative": "PASS",
    }
    sha = hashlib.sha256(PAYLOAD).hexdigest()
    records = {"S01": _record_for(tmp_path / "never_verified.mp4", sha)}
    lane, _ = artifact_facts.availability_lane_for_shots(records, ["S01"])
    assert lane == "FAIL"

    without_lane = delivery_gate(perfect_qc)
    assert without_lane["delivery_approved"] is True  # the old behaviour

    with_lane = delivery_gate({**perfect_qc, "artifact": lane})
    assert with_lane["delivery_approved"] is False
    assert with_lane["status"] == "BLOCKED"
    assert "artifact" in with_lane["blocking"]


def test_unproven_artifact_lane_is_review_required_not_pass(tmp_path):
    from runtime.provider_admission import delivery_gate

    gate = delivery_gate({
        "media_integrity": "PASS", "continuity": "PASS", "repetition": "PASS",
        "subtitle": "PASS", "audio": "PASS", "creative": "PASS", "artifact": "NOT_PROVEN",
    })
    assert gate["delivery_approved"] is False
    assert gate["status"] == "REVIEW_REQUIRED"


def test_episode_records_loader_tolerates_a_broken_manifest(tmp_path):
    from tools.run_comedy_episode import _load_episode_records

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert _load_episode_records(broken) == {}
    missing = _load_episode_records(tmp_path / "absent.json")
    assert missing == {}
    # A broken manifest must block via the lane, never by crashing the run.
    lane, detail = artifact_facts.availability_lane_for_shots(missing, ["S01"])
    assert lane == "NOT_PROVEN"
