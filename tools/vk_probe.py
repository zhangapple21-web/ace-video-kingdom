"""vk_probe — uniform, read-only introspection for provider tasks.

Why this exists
---------------
The pipeline's real cost is not "we cannot fetch the media" — it is that we
cannot *ask a provider what it produced* without paying for the bytes and
writing a file first.  Drift (resolution, duration, internal cuts) is
therefore discovered late, after the submission, the download, and the
hash.  ``research/longmen_s01a_t03_receipt_20260905.md`` is exactly that
shape: the Provider returned media that had already left the contract.

This tool separates the two operations yt-dlp made a habit of separating:

    INSPECT  ->  metadata, cheap, repeatable, no artifact on disk
    FETCH    ->  bytes, expensive, owned by the production entry

``vk_probe`` only ever does INSPECT.  It deliberately has no ``--fetch``:
adding one would make this a second production path and would bypass
``video_kingdom_entry.py``.  When a question cannot be answered remotely the
receipt says so instead of guessing — ``evidence_tier`` is ``REMOTE_ONLY``
and ``contract_check.verdict`` is ``NOT_PROVEN`` with the offending fields
listed.  ``NOT_PROVEN`` is never an approval.

Design borrowed from yt-dlp, and why each part generalizes
---------------------------------------------------------
1. *A site is a data descriptor, not a code branch.*  yt-dlp grew a hundred
   extractors without growing a dispatcher.  We had the opposite disease:
   adding a Provider meant editing ``research/capability_registry.v2.json``,
   a ``.ps1`` shim allowlist, ``run_short_clip.py`` argparse choices and the
   payload branch, and ``video_kingdom_entry.py`` — four code sites.  Here a
   Provider is one JSON file in ``research/provider_inspectors/`` and the
   engine in this module never grows.
2. *The query is the interface, not the schema.*  yt-dlp's most-copied idea
   is ``--print`` templates.  ``--print "%(state)s %(duration_seconds)s"``
   keeps every consumer out of the JSON shape.
3. *A declarative selection expression.*  yt-dlp's ``-f`` selector is data,
   not branching code.  ``field_map`` plays that role: normalized field ->
   ordered JSON paths, first hit wins.
4. *An archive of what is already known.*  ``--download-archive`` stops
   yt-dlp from re-asking about work it already paid for.  Here ``--archive``
   additionally yields *drift over time* for the same task id, which is the
   empirical form of the provider contract drift this project has only ever
   recorded as a risk-register assumption.

Deliberately out of scope
-------------------------
No POST, no submission, no download, no delivery decision, no Provider
selection, no default change.  This tool cannot approve a shot; it can only
make a provider's own claims legible and checkable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.atomic_io import atomic_write_json

sys.stdout.reconfigure(encoding="utf-8")  # match the other tools: GBK consoles crash on Chinese output

DESCRIPTOR_SCHEMA = "vk_probe.provider_descriptor.v1"
RECEIPT_SCHEMA = "vk_probe.receipt.v1"
DESCRIPTOR_DIR = ROOT / "research" / "provider_inspectors"

#: Questions a task endpoint can plausibly answer, and questions that need the
#: bytes.  Kept explicit so no downstream gate can mistake a remote-only
#: observation for a media-quality verdict.
REMOTE_ANSWERABLE = ("task_id", "state", "artifact_url", "duration_seconds", "width", "height", "fps", "has_audio", "error")
REQUIRES_LOCAL_MEDIA = ("internal_cuts", "black_frames", "freeze_tail", "frame_continuity", "subtitle_coverage", "audio_alignment")

_RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}
_TEMPLATE_RE = re.compile(r"%\(([a-z_][a-z0-9_.]*)\)s")
_TRANSFORMS: dict[str, Callable[[Any], Any]] = {
    "str": lambda value: str(value),
    "int": lambda value: int(float(value)),
    "float": lambda value: float(value),
    "bool": lambda value: bool(value) if not isinstance(value, str) else value.strip().lower() in {"1", "true", "yes"},
    "lower": lambda value: str(value).strip().lower(),
    "upper": lambda value: str(value).strip().upper(),
    "none": lambda value: value,
    # Providers commonly answer with ``{"code": ..., "message": ...}``; keep
    # the human part instead of a Python dict repr in the receipt.
    "message": lambda value: (
        f"{value.get('code')}: {value.get('message')}"
        if isinstance(value, Mapping) and value.get("message")
        else str(value)
    ),
}
_DURATION_TOLERANCE = 0.75


# --------------------------------------------------------------------------- #
# descriptors
# --------------------------------------------------------------------------- #

def _read_descriptor(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"unreadable descriptor {path.name}: {error}") from error
    if not isinstance(data, Mapping):
        raise ValueError(f"descriptor {path.name} must be a JSON object")
    if str(data.get("schema") or "") != DESCRIPTOR_SCHEMA:
        raise ValueError(f"descriptor {path.name} must declare schema {DESCRIPTOR_SCHEMA}")
    return dict(data)


def load_descriptor(provider: str) -> dict[str, Any]:
    """Load one provider descriptor by its ``provider`` id."""
    if not provider.strip():
        raise ValueError("provider is required")
    for path in sorted(DESCRIPTOR_DIR.glob("*.json")):
        descriptor = _read_descriptor(path)
        if str(descriptor.get("provider") or "") == provider.strip():
            return descriptor
    known = ", ".join(available_providers()) or "(none)"
    raise ValueError(f"no descriptor for provider {provider!r}; known: {known}")


def available_providers() -> list[str]:
    providers: list[str] = []
    for path in sorted(DESCRIPTOR_DIR.glob("*.json")):
        try:
            descriptor = _read_descriptor(path)
        except ValueError:
            continue
        name = str(descriptor.get("provider") or "").strip()
        if name:
            providers.append(name)
    return providers


def introspectable_providers() -> list[str]:
    """Providers that actually expose a task endpoint to inspect."""
    result: list[str] = []
    for name in available_providers():
        try:
            descriptor = load_descriptor(name)
        except ValueError:
            continue
        if descriptor.get("introspection_supported") is False or not descriptor.get("endpoint"):
            continue
        result.append(name)
    return result


def declared_fields(provider: str) -> list[str]:
    field_map = load_descriptor(provider).get("field_map") or {}
    return sorted(str(name) for name in field_map)


# --------------------------------------------------------------------------- #
# field extraction
# --------------------------------------------------------------------------- #

def _promoted_view(body: Any) -> dict[str, Any]:
    """Promote ``data`` the way the rest of the codebase already does.

    ``normalize_video_status`` in ``tools/video_kingdom_entry.py`` merges
    ``data`` over the top level.  Reusing that convention keeps one meaning
    of "the provider's answer" across the project instead of two.
    """
    if not isinstance(body, Mapping):
        return {}
    nested = body.get("data")
    view = dict(body)
    if isinstance(nested, Mapping):
        view.update(nested)
    return view


def _dig(view: Mapping[str, Any], dotted: str) -> tuple[bool, Any]:
    current: Any = view
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    if current is None:
        return False, None
    return True, current


def extract_fields(body: Any, field_map: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Resolve a declarative field map against one response body.

    Returns the normalized values plus the names that had no resolvable path,
    so an unmapped field is reported instead of silently becoming ``None``.
    """
    view = _promoted_view(body)
    normalized: dict[str, Any] = {}
    unmapped: list[str] = []
    for name, spec in field_map.items():
        if isinstance(spec, Mapping):
            paths = spec.get("paths") or []
            transform = str(spec.get("transform") or "none")
        else:  # tolerate the short form: a bare list of paths
            paths = list(spec or [])
            transform = "none"
        value: Any = None
        found = False
        for dotted in paths:
            hit, candidate = _dig(view, str(dotted))
            if not hit:
                continue
            coerce = _TRANSFORMS.get(transform)
            if coerce is None:
                raise ValueError(f"unknown transform {transform!r} for field {name!r}")
            try:
                value = coerce(candidate)
            except (TypeError, ValueError):
                continue
            found = True
            break
        if found:
            normalized[str(name)] = value
        else:
            unmapped.append(str(name))
    return normalized, sorted(unmapped)


# --------------------------------------------------------------------------- #
# remote inspection
# --------------------------------------------------------------------------- #

def _auth_header(descriptor: Mapping[str, Any], credential: str) -> str:
    template = str(descriptor.get("auth_header") or "").strip()
    if not template:
        return ""
    return template.replace("{credential}", credential)


def probe_once(
    descriptor: Mapping[str, Any],
    task_id: str,
    *,
    credential: str,
    session: Any = requests,
    timeout: float = 30,
) -> dict[str, Any]:
    """One read-only GET against a provider task endpoint.

    Only the response digest and its key names are recorded.  Values are not
    copied into the receipt wholesale, which keeps a provider response that
    echoes a credential out of the on-disk evidence.
    """
    endpoint = str(descriptor.get("endpoint") or "").strip()
    if not endpoint:
        raise ValueError(f"descriptor {descriptor.get('provider')!r} has no endpoint")
    params = {str(descriptor["task_id_param"]): task_id}
    params.update(dict(descriptor.get("extra_params") or {}))

    headers = {"Accept": "application/json"}
    auth = _auth_header(descriptor, credential)
    if auth:
        headers["Authorization"] = auth

    method = str(descriptor.get("method") or "GET").upper()
    if method != "GET":
        raise ValueError(f"vk_probe only issues GET; descriptor requests {method}")

    try:
        response = session.get(endpoint, params=params, headers=headers, timeout=timeout)
    except requests.RequestException as error:
        return {
            "schema": RECEIPT_SCHEMA,
            "probe_id": f"probe-{uuid.uuid4().hex[:16]}",
            "inspected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "UNREACHABLE",
            "evidence_tier": "REMOTE_ONLY",
            "provider": str(descriptor.get("provider") or ""),
            "capability": str(descriptor.get("capability") or ""),
            "task_ref": {"kind": "task_id", "value": task_id},
            "request": {"endpoint": endpoint, "method": "GET", "param_map_applied": {k: v for k, v in params.items() if k != str(descriptor.get("task_id_param"))}},
            "normalized": {},
            "evidence_limits": {
                "remote_answerable": list(REMOTE_ANSWERABLE),
                "requires_local_media": list(REQUIRES_LOCAL_MEDIA),
            },
            "error_class": "NETWORK_ERROR",
            "error": str(error)[:500],
        }

    raw = getattr(response, "content", b"") or b""
    status_code = getattr(response, "status_code", None)
    data = getattr(response, "json", lambda: {})()
    normalized, unmapped = extract_fields(data, descriptor.get("field_map") or {})

    retry_after = None
    response_headers = getattr(response, "headers", None)
    if response_headers:
        retry_after = response_headers.get("Retry-After")

    return {
        "schema": RECEIPT_SCHEMA,
        "probe_id": f"probe-{uuid.uuid4().hex[:16]}",
        "inspected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "PROBED" if status_code is not None and int(status_code) < 300 else "UNREACHABLE",
        "evidence_tier": "REMOTE_ONLY",
        "provider": str(descriptor.get("provider") or ""),
        "capability": str(descriptor.get("capability") or ""),
        "task_ref": {"kind": "task_id", "value": task_id},
        "request": {
            "endpoint": endpoint,
            "method": "GET",
            "http_status": status_code,
            "param_map_applied": {k: v for k, v in params.items() if k != str(descriptor.get("task_id_param"))},
            "response_sha256": hashlib.sha256(raw).hexdigest(),
            "response_top_level_keys": sorted(str(key) for key in (data if isinstance(data, Mapping) else {})),
        },
        "normalized": normalized,
        "unmapped_fields": unmapped,
        "retry_after_seconds": retry_after,
        "evidence_limits": {
            "remote_answerable": list(REMOTE_ANSWERABLE),
            "requires_local_media": list(REQUIRES_LOCAL_MEDIA),
        },
        **({"error_class": f"HTTP_{status_code}"} if status_code is not None and int(status_code) >= 300 else {}),
    }


def probe_until_terminal(
    descriptor: Mapping[str, Any],
    task_id: str,
    *,
    credential: str,
    session: Any = requests,
    timeout: float = 360,
    poll_delay: float = 2,
    max_delay: float = 60,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Poll a task until it reaches a terminal state, then return that receipt.

    Read-only like :func:`probe_once`.  Honoring ``Retry-After`` matches
    ``run_short_clip.py`` so the two do not disagree about backoff.
    """
    terminal = {str(value).strip().lower() for value in descriptor.get("terminal_states") or []}
    deadline = time.monotonic() + timeout
    delay = poll_delay
    receipt: dict[str, Any] = {}
    polls = 0
    while True:
        polls += 1
        receipt = probe_once(descriptor, task_id, credential=credential, session=session)
        receipt["polls"] = polls
        state = str(receipt.get("normalized", {}).get("state") or "").strip().lower()
        code = receipt.get("request", {}).get("http_status")
        if state and terminal and state in terminal:
            receipt["status"] = "PROBED"
            return receipt
        if code is not None and int(code) not in _RETRYABLE_HTTP and receipt.get("status") != "PROBED":
            return receipt
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            receipt["status"] = "POLL_TIMEOUT"
            receipt["error_class"] = "POLL_TIMEOUT"
            return receipt
        wait = min(delay, max_delay)
        retry_after = receipt.get("retry_after_seconds")
        if code is not None and int(code) in _RETRYABLE_HTTP and retry_after is not None:
            try:
                wait = max(0.1, min(float(retry_after), max_delay))
            except (TypeError, ValueError):
                pass
        sleep(min(wait, remaining))
        delay = min(delay * 2, max_delay)


# --------------------------------------------------------------------------- #
# contract comparison
# --------------------------------------------------------------------------- #

def compare_to_contract(receipt: Mapping[str, Any], expectations: Mapping[str, Any]) -> dict[str, Any]:
    """Compare a provider's own claims against what the shot contract asked for.

    ``NOT_PROVEN`` is returned whenever an expected fact was not readable
    remotely.  It is deliberately not folded into a pass: the media may well
    be fine, but this probe did not watch the media.
    """
    normalized = dict(receipt.get("normalized") or {})
    checks: dict[str, Any] = {}
    not_proven: list[str] = []
    drifted: list[str] = []

    if expectations.get("seconds") is not None:
        expected = float(expectations["seconds"])
        actual = normalized.get("duration_seconds")
        if actual is None:
            not_proven.append("duration_seconds")
            checks["duration"] = {"expected": expected, "actual": None, "verdict": "NOT_PROVEN", "tolerance_seconds": _DURATION_TOLERANCE}
        else:
            actual = float(actual)
            tolerance = max(_DURATION_TOLERANCE, 0.1 * expected)
            delta = round(actual - expected, 3)
            verdict = "MATCH" if abs(delta) <= tolerance else "DRIFT"
            checks["duration"] = {"expected": expected, "actual": actual, "delta_seconds": delta, "tolerance_seconds": tolerance, "verdict": verdict}
            if verdict == "DRIFT":
                drifted.append("duration_seconds")

    for key, field in (("width", "width"), ("height", "height")):
        if expectations.get(key) is None:
            continue
        expected = int(expectations[key])
        actual = normalized.get(field)
        if actual is None:
            not_proven.append(field)
            checks[key] = {"expected": expected, "actual": None, "verdict": "NOT_PROVEN"}
        else:
            actual = int(actual)
            verdict = "MATCH" if actual == expected else "DRIFT"
            checks[key] = {"expected": expected, "actual": actual, "verdict": verdict}
            if verdict == "DRIFT":
                drifted.append(field)

    if expectations.get("fps") is not None:
        expected = float(expectations["fps"])
        actual = normalized.get("fps")
        if actual is None:
            not_proven.append("fps")
            checks["fps"] = {"expected": expected, "actual": None, "verdict": "NOT_PROVEN"}
        else:
            verdict = "MATCH" if abs(float(actual) - expected) <= 0.01 else "DRIFT"
            checks["fps"] = {"expected": expected, "actual": actual, "verdict": verdict}
            if verdict == "DRIFT":
                drifted.append("fps")

    for question in REQUIRES_LOCAL_MEDIA:
        if question not in ("internal_cuts", "black_frames", "freeze_tail"):
            continue
        checks[f"requires_local_media:{question}"] = "NOT_PROVEN"

    verdict = "DRIFT_DETECTED" if drifted else ("NOT_PROVEN" if not_proven else "WITHIN_CONTRACT")
    return {
        "verdict": verdict,
        "approval_capable": verdict == "WITHIN_CONTRACT",
        "evidence_tier": receipt.get("evidence_tier"),
        "drifted_fields": drifted,
        "not_proven_fields": not_proven,
        "checks": checks,
        "note": "WITHIN_CONTRACT covers only facts this probe could read remotely; it is not a delivery or creative approval.",
    }


# --------------------------------------------------------------------------- #
# archive: don't re-ask, and notice drift over time
# --------------------------------------------------------------------------- #

def _archive_key(receipt: Mapping[str, Any]) -> str:
    provider = str(receipt.get("provider") or "")
    task_id = str((receipt.get("task_ref") or {}).get("value") or "")
    return f"{provider}::{task_id}"


def _drift_since(previous: Mapping[str, Any], current: Mapping[str, Any], watched: Sequence[str]) -> dict[str, Any]:
    before = dict(previous.get("normalized") or {})
    after = dict(current.get("normalized") or {})
    changed = {
        name: {"before": before.get(name), "after": after.get(name)}
        for name in watched
        if name in before and name in after and before.get(name) != after.get(name)
    }
    return {
        "watched_fields": list(watched),
        "changed_fields": changed,
        # A rotating signed URL is not a contract change; report it separately
        # so it cannot be mistaken for provider drift.
        "artifact_url_changed": before.get("artifact_url") != after.get("artifact_url"),
    }


def update_archive(path: Path, receipt: Mapping[str, Any], watched: Sequence[str]) -> dict[str, Any]:
    """Record this observation and report drift against the previous one."""
    archive: dict[str, Any] = {"schema": "vk_probe.archive.v1", "entries": {}}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, Mapping) and isinstance(loaded.get("entries"), Mapping):
                archive = dict(loaded)
                archive["entries"] = dict(loaded["entries"])
        except (OSError, ValueError):
            archive = {"schema": "vk_probe.archive.v1", "entries": {}}

    key = _archive_key(receipt)
    entries = dict(archive["entries"])
    previous = entries.get(key) if isinstance(entries.get(key), Mapping) else None
    report = {
        "archive_path": str(path),
        "archive_key": key,
        "first_probe": previous is None,
        "previous_observed_at": (previous or {}).get("last_observed_at"),
        "provider_contract_drift": _drift_since(previous, receipt, watched) if previous else None,
    }

    history = list((previous or {}).get("history") or [])
    history.append({"observed_at": receipt.get("inspected_at"), "normalized": dict(receipt.get("normalized") or {})})
    entries[key] = {
        "provider": receipt.get("provider"),
        "task_ref": receipt.get("task_ref"),
        "first_observed_at": (previous or {}).get("first_observed_at") or receipt.get("inspected_at"),
        "last_observed_at": receipt.get("inspected_at"),
        # The latest observation stays addressable at the top level so the next
        # run can diff against it without replaying ``history``.
        "normalized": dict(receipt.get("normalized") or {}),
        "history": history[-20:],
    }
    atomic_write_json(path, {"schema": "vk_probe.archive.v1", "entries": entries})
    return report


# --------------------------------------------------------------------------- #
# --print templates
# --------------------------------------------------------------------------- #

def render_template(template: str, receipt: Mapping[str, Any]) -> str:
    """Expand a yt-dlp style ``--print`` template against a receipt.

    Field names resolve against ``normalized`` first, then the envelope, so
    ``%(state)s`` and ``%(evidence_tier)s`` both work.  Unknown fields render
    as ``NA`` instead of raising, which keeps a template reusable when a
    descriptor stops reporting something.
    """
    normalized = dict(receipt.get("normalized") or {})

    def resolve(name: str) -> str:
        if name in normalized:
            value = normalized[name]
        elif "." in name and name.split(".", 1)[0] in receipt:
            container = receipt.get(name.split(".", 1)[0])
            value = container.get(name.split(".", 1)[1]) if isinstance(container, Mapping) else None
        else:
            value = receipt.get(name)
        if value is None:
            return "NA"
        if isinstance(value, (list, tuple)):
            return ",".join(str(item) for item in value) if value else "NA"
        if isinstance(value, Mapping):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)

    return _TEMPLATE_RE.sub(lambda match: resolve(match.group(1)), template)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _receipt_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_decision_record(
    receipt: Mapping[str, Any],
    *,
    receipt_path: Path,
    root: Path,
    record_id: str,
    episode_id: str,
    scope_ref: str,
) -> dict[str, Any]:
    """Turn a probe receipt into a Decision Record the existing ACE loop accepts.

    Why this shape
    --------------
    A tool that only writes its own JSON is an orphan.  The project already has
    a learning entry point — ``tools/validate_decision_record.py`` plus
    ``tools/emit_ace_result_bridge.py`` — and it already contains the exact
    guard this work needs: a ``PASS`` requires evidence whose kind is one of
    ``media_integrity`` / ``visual_review`` / ``subtitle_receipt``
    (``validate_decision_record.py:103``).  A remote-only probe can never
    supply those, so a ``NOT_PROVEN`` observation is structurally incapable of
    being promoted to success.  We reuse that guard rather than inventing a
    second one, and this function never emits ``PASS`` either.

    Verdict mapping:

    * within contract, nothing violated -> ``CONDITIONAL``.  Nothing is wrong,
      but remote-only evidence cannot approve anything, and CONDITIONAL is the
      honest state for that.
    * drift detected                     -> ``REWORK`` with a bounded scope.
    * not proven / unreachable           -> ``BLOCKED`` pending investigation.
    """
    root = root.resolve()
    relative = receipt_path.resolve().relative_to(root).as_posix()
    contract = dict(receipt.get("contract_check") or {})
    verdict = str(contract.get("verdict") or "NOT_PROVEN")
    normalized = dict(receipt.get("normalized") or {})
    task_id = str((receipt.get("task_ref") or {}).get("value") or "unknown")

    if verdict == "DRIFT_DETECTED":
        opinion_verdict, decision_verdict = "REWORK", "REWORK"
        repair_scope = [f"reconcile provider output for {task_id} against the shot contract"]
        expected_gain = "the next attempt carries a provider output that matches the contract, or the mismatch is recorded as known"
        reason = f"provider output drifted on: {', '.join(contract.get('drifted_fields') or []) or 'unspecified'}"
    elif verdict == "WITHIN_CONTRACT":
        opinion_verdict, decision_verdict = "SUPPORT", "CONDITIONAL"
        repair_scope = []
        expected_gain = ""
        reason = (
            "the provider's own claims matched the contract, but this is remote-only evidence: "
            "it watched no media, so internal cuts, black frames, freeze and frame continuity remain unproven"
        )
    else:
        opinion_verdict, decision_verdict = "UNKNOWN", "BLOCKED"
        repair_scope = []
        expected_gain = ""
        unproven = ", ".join(contract.get("not_proven_fields") or []) or "the provider did not answer"
        reason = f"NOT_PROVEN: {unproven}; a remote probe cannot approve a shot and must not be read as a pass"

    return {
        "record_id": record_id,
        "episode_id": episode_id,
        "scope_ref": scope_ref,
        "source_realm": "CONTROLLED_ORIGIN",
        "admission": {"status": "NOT_REQUIRED"},
        "lifecycle": "RESULT_RECORDED",
        "evidence": [
            {
                "evidence_id": "probe-receipt",
                # Deliberately not one of media_integrity / visual_review /
                # subtitle_receipt: that is what keeps PASS unreachable here.
                "kind": "provider_probe",
                "path": relative,
                "sha256": _receipt_sha256(receipt_path),
            }
        ],
        "opinions": [
            {
                "opinion_id": "provider-introspection",
                "role": "utility",
                "model": str(receipt.get("provider") or "unknown"),
                "verdict": opinion_verdict,
                "evidence_refs": ["probe-receipt"],
                "findings": [
                    f"task {task_id}: provider state {normalized.get('state', 'NA')}",
                    f"evidence_tier {receipt.get('evidence_tier')}; no media was downloaded by this probe",
                    f"contract verdict {verdict}",
                ],
                "uncertainties": [
                    f"requires local media: {', '.join(REQUIRES_LOCAL_MEDIA)}",
                ],
            },
            {
                "opinion_id": "provider-introspection-decider",
                "role": "final_decider",
                "model": str(receipt.get("provider") or "unknown"),
                "verdict": opinion_verdict,
                "evidence_refs": ["probe-receipt"],
                "findings": [reason],
                "uncertainties": [
                    "this record cannot produce a PASS by construction; approval still requires locally verified media",
                ],
            },
        ],
        "decision": {
            "verdict": decision_verdict,
            "decider_opinion_id": "provider-introspection-decider",
            "basis_evidence_refs": ["probe-receipt"],
            "reason": reason,
            "repair_scope": repair_scope,
            "expected_gain": expected_gain,
            "cost_class": "FREE_ZONE_RESEARCH_ONLY",
        },
        "result": {
            "status": "COMPLETED" if receipt.get("status") == "PROBED" else "FAILED",
            "observed_evidence_refs": ["probe-receipt"],
            "summary": reason,
        },
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _summarize(receipt: Mapping[str, Any]) -> str:
    normalized = dict(receipt.get("normalized") or {})
    lines = [
        f"provider   {receipt.get('provider')} ({receipt.get('capability')})",
        f"task       {(receipt.get('task_ref') or {}).get('value')}",
        f"status     {receipt.get('status')}",
        f"tier       {receipt.get('evidence_tier')}  <- no media was downloaded",
        f"state      {normalized.get('state', 'NA')}",
    ]
    if normalized.get("duration_seconds") is not None:
        lines.append(f"duration   {normalized['duration_seconds']}s")
    if normalized.get("width") is not None:
        lines.append(f"resolution {normalized.get('width')}x{normalized.get('height')}")
    for name in ("has_audio", "artifact_url", "error"):
        if normalized.get(name) is not None:
            text = str(normalized[name])
            lines.append(f"{name:<10} {text[:110]}")
    contract = receipt.get("contract_check") or {}
    if contract:
        lines.append(f"contract   {contract.get('verdict')}  approval_capable={contract.get('approval_capable')}")
        if contract.get("not_proven_fields"):
            lines.append(f"unproven   {', '.join(contract['not_proven_fields'])} (needs the local media)")
    if receipt.get("archive"):
        archive = receipt["archive"]
        if archive.get("provider_contract_drift"):
            changed = archive["provider_contract_drift"]["changed_fields"]
            lines.append(f"drift      {', '.join(changed) if changed else 'watched fields unchanged'}")
        lines.append(f"archive    first_probe={archive['first_probe']}")
    unmapped = receipt.get("unmapped_fields") or []
    if unmapped:
        lines.append(f"unmapped   {', '.join(unmapped)}  <- descriptor does not read these yet")
    return "\n".join(lines)


def _credential_for(descriptor: Mapping[str, Any]) -> str:
    """Read the credential from the environment only. Never a file or arg."""
    env_name = str(descriptor.get("credential_env") or "").strip()
    if not env_name:
        return ""
    value = os.environ.get(env_name, "")
    if not value.strip():
        raise SystemExit(f"probe blocked: environment variable {env_name} is empty (credentials are never read from files)")
    return value.strip()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vk_probe",
        description="Read-only provider task introspection. Never submits, never downloads, never approves.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect", help="inspect one provider task")
    inspect.add_argument("provider")
    inspect.add_argument("--task-id", required=True, help="the provider's own task/video id")
    inspect.add_argument("--expect-seconds", type=float, help="compare the provider's duration against the contract")
    inspect.add_argument("--expect-width", type=int)
    inspect.add_argument("--expect-height", type=int)
    inspect.add_argument("--expect-fps", type=float)
    inspect.add_argument("--timeout", type=float, default=0, help="poll until terminal instead of a single GET (0 = one GET)")
    inspect.add_argument("--poll-delay", type=float, default=2)
    inspect.add_argument("--max-delay", type=float, default=60)
    inspect.add_argument("--receipt", type=Path, help="write the vk_probe.receipt.v1 envelope here")
    inspect.add_argument("--decision-record", type=Path, help="write a Decision Record for the existing ACE loop (requires --receipt)")
    inspect.add_argument("--root", type=Path, default=ROOT, help="project root the decision record's evidence path is relative to")
    inspect.add_argument("--episode-id", default="provider-introspection")
    inspect.add_argument("--scope-ref", default="provider_introspection")
    inspect.add_argument("--archive", type=Path, help="persist observations and report drift over time")
    inspect.add_argument("--print", dest="template", default="", help='template, e.g. "%(state)s %(duration_seconds)s"')
    inspect.add_argument("--json", action="store_true", help="print the full envelope to stdout")

    sub.add_parser("providers", help="list descriptor providers")
    fields = sub.add_parser("fields", help="list the normalized fields a provider maps")
    fields.add_argument("provider")

    args = parser.parse_args(argv)

    if args.command == "providers":
        for name in available_providers():
            try:
                descriptor = load_descriptor(name)
            except ValueError as error:
                print(f"{name}\tUNREADABLE\t{error}")
                continue
            supported = descriptor.get("introspection_supported") is not False and bool(descriptor.get("endpoint"))
            gap = str(descriptor.get("introspection_gap") or "").strip()
            print(f"{name}\t{'INSPECTABLE' if supported else 'NO_TASK_ENDPOINT'}\t{descriptor.get('capability', '')}")
            if gap:
                print(f"    gap: {gap}")
        return 0

    if args.command == "fields":
        for name in declared_fields(args.provider):
            print(name)
        return 0

    descriptor = load_descriptor(args.provider)
    if descriptor.get("introspection_supported") is False:
        gap = str(descriptor.get("introspection_gap") or "").strip() or "this provider declares no task endpoint"
        raise SystemExit(f"probe blocked: {descriptor.get('provider')} has no task endpoint. {gap}")
    credential = _credential_for(descriptor)

    if args.timeout and args.timeout > 0:
        receipt = probe_until_terminal(
            descriptor,
            str(args.task_id),
            credential=credential,
            timeout=args.timeout,
            poll_delay=args.poll_delay,
            max_delay=args.max_delay,
        )
    else:
        receipt = probe_once(descriptor, str(args.task_id), credential=credential)

    expectations = {
        "seconds": args.expect_seconds,
        "width": args.expect_width,
        "height": args.expect_height,
        "fps": args.expect_fps,
    }
    if any(value is not None for value in expectations.values()):
        receipt["contract_check"] = compare_to_contract(receipt, expectations)

    if args.archive:
        watched = descriptor.get("drift_watched_fields") or []
        receipt["archive"] = update_archive(args.archive, receipt, watched)

    if args.template:
        print(render_template(args.template, receipt))
    elif args.json:
        print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(_summarize(receipt))

    if args.receipt:
        atomic_write_json(args.receipt, receipt)
        print(f"receipt written: {args.receipt}")

    if args.decision_record:
        if not args.receipt:
            raise SystemExit("--decision-record requires --receipt: the record's evidence must exist on disk to be hashed")
        record = build_decision_record(
            receipt,
            receipt_path=args.receipt,
            root=args.root,
            record_id=f"VK-PROBE-{args.provider}-{str((receipt.get('task_ref') or {}).get('value') or 'unknown')}"[:96],
            episode_id=args.episode_id,
            scope_ref=args.scope_ref,
        )
        atomic_write_json(args.decision_record, record)
        print(f"decision record written: {args.decision_record} (verdict {record['decision']['verdict']})")

    return 0 if receipt.get("status") in {"PROBED", "POLL_TIMEOUT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
