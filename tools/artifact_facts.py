"""Separate the facts a generation receipt has been asked to carry at once.

The problem this module exists to fix
-------------------------------------
A shot record used to answer five independent questions with one ``status``
string:

    1. did the provider generate this at all?
    2. did the bytes land on disk and match a hash?
    3. can the provider still serve it?
    4. if the local file is gone, can it be recovered?
    5. may the delivery chain treat this shot as complete?

Conflating them produced two real defects, both reproduced by the
counterexamples in ``tests/test_artifact_facts.py``:

* Re-running after the local file disappeared drove the record to
  ``PROVIDER_FAILED``.  That is a false statement: generation succeeded, the
  task record was later evicted.  The rewrite also left ``artifact_sha256``,
  ``bytes`` and ``artifact_path`` in place, so one record asserted both
  "provider failed" and "here is the verified artifact".
* A local file whose content no longer matched the recorded hash was accepted
  as complete, because the idempotent short-circuit only asked
  ``Path.is_file()`` and never re-verified.

Design rules
------------
* ``status`` keeps its existing vocabulary.  Downstream consumers
  (``patrol_and_doctor.py``, the resume path, the admission hash reuse rule)
  already branch on it, and this module does not get to redefine it.
* The generation fact is written **once** and never mutated.  Provider
  unavailability is recorded *beside* it, not on top of it.  A provider that
  can no longer resolve a task says nothing about whether it once produced it.
* ``delivery_ready`` is fail-closed: without fresh local evidence it is
  ``False``.  A ``COMPLETED`` status is not a delivery.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

FACTS_SCHEMA = "video_kingdom.artifact_facts.v1"

#: local artifact states
LOCAL_VERIFIED = "VERIFIED_LOCAL"
LOCAL_MISMATCH = "MISMATCH_LOCAL"
LOCAL_ABSENT = "ABSENT_LOCAL"
LOCAL_UNKNOWN = "UNKNOWN_LOCAL"

#: remote artifact states
REMOTE_REACHABLE = "REACHABLE_REMOTE"
REMOTE_UNREACHABLE = "UNREACHABLE_REMOTE"
REMOTE_UNKNOWN = "UNKNOWN_REMOTE"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(path: Path, *, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _resolve_candidates(path_value: Any, roots: Sequence[Path]) -> list[Path]:
    """Candidate locations for a recorded path, most specific first.

    A recorded relative ``artifact_path`` is ambiguous: records in this project
    have been written with paths relative to the manifest directory *and* to
    the repository root (``media_staging/episode_002_shot_004.mp4``), depending
    on which manifest was in use. Resolving against a single assumed root turns
    present media into a false ABSENT_LOCAL, which is worse than no answer
    because it blocks delivery on good footage. So every plausible root is
    tried, and the one that matched is recorded.
    """
    if not path_value:
        return []
    candidate = Path(str(path_value))
    if candidate.is_absolute():
        return [candidate]
    ordered: list[Path] = []
    for root in roots:
        resolved = (Path(root) / candidate).resolve()
        if resolved not in ordered:
            ordered.append(resolved)
    return ordered


def _resolve(path_value: Any, roots: Sequence[Path]) -> tuple[Path | None, Path | None]:
    candidates = _resolve_candidates(path_value, roots)
    if not candidates:
        return None, None
    for resolved in candidates:
        if resolved.is_file():
            return resolved, Path(roots[0]) if roots else None
    return candidates[0], None


def availability_lane(
    record: Mapping[str, Any],
    *,
    manifest_dir: Path | None = None,
    roots: Sequence[Path] | None = None,
    verify_hash: bool = True,
) -> str:
    """Express artifact availability as a delivery-gate lane value.

    The blocked-run path in ``tools/record_blocked_run_evidence.py`` already
    carries an ``"artifact": "NOT_PROVEN"`` lane, but the episode success path
    in ``tools/run_comedy_episode.py`` had no artifact lane at all. So a run
    whose six QC lanes all passed could still be approved without ever stating
    whether the source media was actually present and verified.

    ``PASS`` requires a currently verified local file. ``NOT_PROVEN`` means the
    record cannot answer, and ``delivery_gate`` treats it as blocking — so an
    absent answer never becomes an approval.
    """
    assessment = assess(record, manifest_dir=manifest_dir, roots=roots, verify_hash=verify_hash)
    if assessment["local"]["state"] == LOCAL_VERIFIED and assessment["generation"]["generated"]:
        return "PASS"
    if assessment["local"]["state"] in {LOCAL_ABSENT, LOCAL_MISMATCH}:
        return "FAIL"
    return "NOT_PROVEN"


def availability_lane_for_shots(
    records: Mapping[str, Mapping[str, Any]],
    shot_ids: Sequence[str],
    *,
    manifest_dir: Path | None = None,
    roots: Sequence[Path] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Worst-lane-wins across an episode's shots. Returns ``(lane, detail)``."""
    order = {"PASS": 0, "NOT_PROVEN": 1, "FAIL": 2}
    detail: dict[str, Any] = {}
    worst = "PASS"
    for shot_id in shot_ids:
        record = records.get(shot_id)
        if record is None:
            detail[shot_id] = {"lane": "NOT_PROVEN", "reason": "no durable manifest record"}
            worst = "NOT_PROVEN" if order[worst] < order["NOT_PROVEN"] else worst
            continue
        lane = availability_lane(record, manifest_dir=manifest_dir, roots=roots)
        assessment = assess(record, manifest_dir=manifest_dir, roots=roots)
        detail[shot_id] = {
            "lane": lane,
            "local": assessment["local"]["state"],
            "recoverable": assessment["recoverable"],
            "reason": delivery_block_reason(assessment),
        }
        if order[lane] > order[worst]:
            worst = lane
    return worst, detail


def record_generation_fact(
    record: dict[str, Any],
    *,
    path: Path,
    sha256: str,
    bytes_count: int,
    video_id: str | None,
    artifact_url: str | None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Write the one-time generation fact. Refuses to overwrite an existing one.

    Keeping this write-once is the whole point: a later failure must add a
    fact, never rewrite history.  If a fact already exists the extra arguments
    are ignored and the original is returned unchanged.
    """
    existing = record.get("generation_fact")
    if isinstance(existing, Mapping) and existing.get("generated"):
        return dict(existing)
    fact = {
        "generated": True,
        "sha256": sha256,
        "bytes": bytes_count,
        "path": str(path),
        "video_id": video_id,
        # The remote location is recorded because it is the only handle that
        # can outlive the local container.  Without it, a lost file has no
        # path back even while the provider still retains the task.
        "artifact_url": artifact_url,
        "observed_at": observed_at or _now(),
    }
    record["generation_fact"] = fact
    return fact


def classify_local(
    record: Mapping[str, Any],
    *,
    manifest_dir: Path | None = None,
    roots: Sequence[Path] | None = None,
    verify_hash: bool = True,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Re-derive the current state of the local artifact from the filesystem.

    This never trusts ``status`` and never trusts a recorded path alone.  A
    record that merely *claims* an artifact exists is not evidence.
    """
    fact = record.get("generation_fact") if isinstance(record.get("generation_fact"), Mapping) else {}
    path_value = fact.get("path") or record.get("artifact_path")
    expected = fact.get("sha256") or record.get("artifact_sha256")
    checked_at = observed_at or _now()
    search_roots = list(roots) if roots else ([manifest_dir] if manifest_dir else [])
    if manifest_dir and manifest_dir not in search_roots:
        search_roots.insert(0, manifest_dir)
    result: dict[str, Any] = {
        "state": LOCAL_UNKNOWN,
        "path": str(path_value) if path_value else None,
        "expected_sha256": expected,
        "actual_sha256": None,
        "bytes": None,
        "checked_at": checked_at,
        "hash_verified": False,
        "resolved_path": None,
        "searched_roots": [str(root) for root in search_roots],
    }
    resolved, _ = _resolve(path_value, search_roots)
    if resolved is None:
        result["state"] = LOCAL_UNKNOWN if not path_value else LOCAL_ABSENT
        return result
    result["resolved_path"] = str(resolved)
    if not resolved.is_file():
        # A path was recorded and the file is not under any candidate root.
        # That is a real, checkable statement — not an unknown.
        result["state"] = LOCAL_ABSENT
        return result
    try:
        stat = resolved.stat()
    except OSError:
        result["state"] = LOCAL_ABSENT
        return result
    result["bytes"] = stat.st_size
    if expected and verify_hash:
        try:
            actual = sha256_file(resolved)
        except OSError:
            result["state"] = LOCAL_UNKNOWN
            return result
        result["actual_sha256"] = actual
        result["hash_verified"] = actual == expected
        result["state"] = LOCAL_VERIFIED if actual == expected else LOCAL_MISMATCH
        return result
    if expected:
        # Hash comparison was declined; presence alone is not verification.
        result["state"] = LOCAL_UNKNOWN
        return result
    result["actual_sha256"] = None
    result["state"] = LOCAL_UNKNOWN
    return result


def classify_remote(record: Mapping[str, Any], *, observed_at: str | None = None) -> dict[str, Any]:
    """Read the recorded remote facts without making a network call.

    ``reconcile_required`` on the record means a remote check already ran and
    did not resolve; the answer is carried in the record rather than guessed.
    """
    fact = record.get("generation_fact") if isinstance(record.get("generation_fact"), Mapping) else {}
    remote = record.get("remote_artifact") if isinstance(record.get("remote_artifact"), Mapping) else {}
    result = {
        "state": REMOTE_UNKNOWN,
        "artifact_url": remote.get("artifact_url") or fact.get("artifact_url") or record.get("artifact_url"),
        "http_status": remote.get("http_status"),
        "checked_at": remote.get("checked_at") or observed_at or _now(),
        "error_class": remote.get("error_class"),
    }
    declared = str(remote.get("state") or "").strip()
    if declared in {REMOTE_REACHABLE, REMOTE_UNREACHABLE}:
        result["state"] = declared
        return result
    if record.get("reconcile_required"):
        result["state"] = REMOTE_UNREACHABLE
    return result


def assess(
    record: Mapping[str, Any],
    *,
    manifest_dir: Path | None = None,
    roots: Sequence[Path] | None = None,
    verify_hash: bool = True,
) -> dict[str, Any]:
    """Return the five separated facts plus the derived recovery answers.

    ``recoverable`` is deliberately conservative: a local verified copy always
    counts, and a remote URL only counts once a check has actually confirmed
    it resolves.  A recorded-but-unconfirmed URL is not a recovery path.
    """
    local = classify_local(record, manifest_dir=manifest_dir, roots=roots, verify_hash=verify_hash)
    remote = classify_remote(record)
    fact = record.get("generation_fact") if isinstance(record.get("generation_fact"), Mapping) else {}
    generated = bool(fact.get("generated")) or bool(record.get("artifact_sha256"))
    recoverable = bool(local["state"] == LOCAL_VERIFIED) or bool(remote["state"] == REMOTE_REACHABLE)
    delivery_ready = bool(generated and local["state"] == LOCAL_VERIFIED)
    return {
        "schema": FACTS_SCHEMA,
        "generation": {
            "generated": generated,
            "sha256": fact.get("sha256") or record.get("artifact_sha256"),
            "bytes": fact.get("bytes") if fact.get("bytes") is not None else record.get("bytes"),
            "observed_at": fact.get("observed_at"),
            "source": "generation_fact" if fact.get("generated") else ("legacy_flat_fields" if generated else "absent"),
        },
        "local": local,
        "remote": remote,
        "recoverable": recoverable,
        "delivery_ready": delivery_ready,
        "assessed_at": _now(),
    }


def delivery_ready(
    record: Mapping[str, Any],
    *,
    manifest_dir: Path | None = None,
    roots: Sequence[Path] | None = None,
    verify_hash: bool = True,
) -> bool:
    """The single question the delivery chain must ask. Fail-closed.

    ``True`` requires a generation fact *and* a currently verified local file.
    A ``COMPLETED`` status on its own is not enough — that is the exact gap
    this module was written to close.
    """
    return bool(
        assess(record, manifest_dir=manifest_dir, roots=roots, verify_hash=verify_hash)["delivery_ready"]
    )


def delivery_block_reason(assessment: Mapping[str, Any]) -> str | None:
    """Explain a refusal in words a receipt reader can act on."""
    if assessment.get("delivery_ready"):
        return None
    local = dict(assessment.get("local") or {})
    generation = dict(assessment.get("generation") or {})
    if not generation.get("generated"):
        return "no generation fact: this record never recorded a verified artifact"
    if local.get("state") == LOCAL_ABSENT:
        remote = dict(assessment.get("remote") or {})
        if remote.get("state") == REMOTE_UNREACHABLE:
            return "generated once and verified, but the local file is gone and the provider no longer resolves the task; recovery is not possible from this record alone"
        return "generated once and verified, but the local file is absent; re-fetch or investigate before delivery"
    if local.get("state") == LOCAL_MISMATCH:
        return f"local file content does not match the recorded generation hash {local.get('expected_sha256')}"
    if local.get("state") == LOCAL_UNKNOWN:
        return "local artifact could not be verified; a recorded path or hash is not evidence of a file"
    return "delivery is not ready"


def record_remote_probe(
    record: dict[str, Any],
    *,
    reachable: bool,
    artifact_url: str | None = None,
    http_status: int | None = None,
    error_class: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Record what the provider says about the artifact *now*.

    Written beside the generation fact, never in place of it.
    """
    fact = {
        "state": REMOTE_REACHABLE if reachable else REMOTE_UNREACHABLE,
        "artifact_url": artifact_url,
        "http_status": http_status,
        "error_class": error_class,
        "checked_at": observed_at or _now(),
    }
    record["remote_artifact"] = fact
    return fact
