"""The single, model-free Provider Admission boundary for Video Kingdom.

This module is deliberately small and side-effect free except for writing an
admission receipt requested by a caller.  It does not know how to call a
Provider.  A caller must first build one canonical request, obtain an
``ADMITTED`` receipt, and then assert that receipt immediately before POST.

The same boundary is used by the Shot Core runner and by legacy/research
adapters.  A legacy adapter may pass ``scope=legacy`` or ``scope=research``;
that changes the receipt label only. Media requests still require a signed
medium lock regardless of scope.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from tools.medium_lock import validate_medium_lock
except ImportError:  # pragma: no cover
    from medium_lock import validate_medium_lock  # type: ignore

CANONICAL_REQUEST_SCHEMA = "video_kingdom.canonical_generation_request.v1"
ADMISSION_RECEIPT_SCHEMA = "video_kingdom.provider_admission_receipt.v1"


class AdmissionError(ValueError):
    """Raised when a Provider call has no valid admission receipt."""


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _first(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return default


def build_canonical_generation_request(
    shot: dict[str, Any],
    payload: dict[str, Any],
    *,
    provider: str,
    endpoint: str,
    payload_schema: str,
    model: str | None = None,
    scope: str = "production",
    request_kind: str = "shot",
) -> dict[str, Any]:
    """Project any runner's payload into one stable request shape.

    The projection intentionally keeps the source contract fields separate
    from provider-specific payload fields.  Provider adapters are therefore
    allowed to translate the request, but not to invent a second semantic
    request.
    """
    contract = shot.get("contract") if isinstance(shot.get("contract"), dict) else {}
    intent = shot.get("intent") if isinstance(shot.get("intent"), dict) else {}
    state = shot.get("state") if isinstance(shot.get("state"), dict) else {}
    audio = shot.get("audio") if isinstance(shot.get("audio"), dict) else {}
    render = shot.get("render") if isinstance(shot.get("render"), dict) else {}
    shot_contract = shot.get("shot_contract") if isinstance(shot.get("shot_contract"), dict) else {}
    refs = shot.get("asset_refs")
    if not isinstance(refs, list):
        refs = shot.get("reference_assets") if isinstance(shot.get("reference_assets"), list) else []
    visible = shot.get("visible_entities")
    if not isinstance(visible, list):
        visible = list(shot.get("visible_character_ids") or []) + list(shot.get("visible_prop_ids") or [])
        if not visible and isinstance(shot_contract.get("allowed_characters"), list):
            visible = list(shot_contract["allowed_characters"])
        if not visible and isinstance(shot.get("allowed_characters"), list):
            visible = list(shot["allowed_characters"])
        if not visible and isinstance(shot.get("generation_request"), dict):
            allowed = shot["generation_request"].get("allowed_characters")
            if isinstance(allowed, list):
                visible = list(allowed)
    action = _first(
        shot,
        "action",
        "primary_visual_event",
        default=_first(intent, "primary_visual_event", default=_first(shot_contract, "primary_visual_event", default="")),
    )
    duration = _first(shot, "duration", default=_first(contract, "render_seconds", default=_first(render, "seconds")))
    camera = _first(shot, "camera", default=_first(contract, "camera", default={}))
    if not isinstance(camera, dict):
        camera = {}
    first_frame = _first(shot, "first_frame", default=_first(contract, "first_frame_ref", default=payload.get("first_frame")))
    last_frame = _first(shot, "last_frame", default=_first(contract, "last_frame_ref", default=payload.get("last_frame")))
    audio_contract = _first(shot, "audio_contract", default=audio)
    if not isinstance(audio_contract, dict):
        audio_contract = {"value": audio_contract}
    generation_parameters = {
        key: value for key, value in payload.items()
        if key not in {"prompt", "negative_prompt", "model"}
    }
    request = {
        "schema": CANONICAL_REQUEST_SCHEMA,
        "request_kind": request_kind,
        "scope": scope,
        "episode_id": shot.get("episode_id") or shot.get("project_id"),
        "shot_id": shot.get("shot_id"),
        "provider": provider,
        "endpoint": endpoint,
        "payload_schema": payload_schema,
        "model": model or payload.get("model"),
        # The canonical request records the exact provider-facing prompt.  The
        # source Shot/episode prompt remains available under source_contract;
        # adapters may compile it into a richer provider prompt, but there is
        # still only one hash-bound request for the resulting POST.
        "prompt": str(_first(payload, "prompt", default=_first(shot, "prompt", default=""))),
        "negative_prompt": str(_first(payload, "negative_prompt", default=_first(shot, "negative_prompt", default=""))),
        "reference_assets": refs,
        "first_frame": first_frame,
        "last_frame": last_frame,
        "visible_entities": visible,
        "camera": camera,
        "action": action,
        "duration": duration,
        "audio_contract": audio_contract,
        "generation_parameters": generation_parameters,
        "provider_payload": deepcopy(payload),
        "contract_fingerprint": shot.get("contract_fingerprint"),
        "source_contract": shot_contract or contract,
        "state": state,
        "medium_lock": shot.get("medium_lock"),
    }
    return request


def model_free_preflight(request: dict[str, Any], *, contract_status: str = "CONTRACT_VALID") -> dict[str, Any]:
    """Validate semantic completeness without inspecting model capability."""
    errors: list[str] = []
    if not isinstance(request, dict):
        return {"status": "BLOCKED", "errors": ["canonical_request_must_be_object"], "warnings": []}
    if request.get("request_kind") in {"asset", "shot"}:
        medium_errors = validate_medium_lock({
            "medium_lock": request.get("medium_lock"),
            "shots": [{"shot_id": request.get("shot_id"), "prompt": request.get("prompt", "")}],
        })
        errors.extend(f"medium_lock:{error}" for error in medium_errors)
    required = ("provider", "endpoint", "payload_schema", "prompt", "action", "audio_contract", "generation_parameters")
    for field in required:
        value = request.get(field)
        if value in (None, "", []):
            errors.append(f"missing:{field}")
    if not request.get("shot_id"):
        errors.append("missing:shot_id")
    if request.get("scope") == "production" and contract_status != "CONTRACT_VALID":
        errors.append(f"shot_contract:{contract_status}")
    if not isinstance(request.get("reference_assets"), list):
        errors.append("reference_assets_must_be_array")
    if not isinstance(request.get("visible_entities"), list):
        errors.append("visible_entities_must_be_array")
    camera = request.get("camera")
    if not isinstance(camera, dict) or not camera:
        errors.append("missing:camera")
    # Video shots require a positive duration; asset/research chores may use
    # ``NOT_APPLICABLE`` explicitly rather than smuggling in an estimate.
    if request.get("request_kind") == "shot":
        if not isinstance(request.get("source_contract"), dict) or not request.get("source_contract"):
            errors.append("missing:source_contract")
        try:
            if float(request.get("duration")) <= 0:
                errors.append("duration_must_be_positive")
        except (TypeError, ValueError):
            errors.append("duration_must_be_positive")
    elif request.get("duration") in (None, "") and request.get("audio_contract", {}).get("status") != "NOT_APPLICABLE":
        errors.append("non_shot_duration_must_be_explicitly_not_applicable")

    # Agnes' video endpoints accept reference images only as public URL
    # strings.  A local path, metadata object, data URI, or asset:// token can
    # be valid *local evidence* but is not a Provider-compatible reference.
    # Catch this before admission so the ledger cannot authorize a request
    # that is guaranteed to fail at the transport boundary.
    if str(request.get("provider", "")).lower() == "agnes":
        provider_payload = request.get("provider_payload")
        if isinstance(provider_payload, dict):
            ref_values: list[Any] = []
            for key in ("image", "images", "first_frame", "last_frame"):
                value = provider_payload.get(key)
                if value is None:
                    continue
                ref_values.extend(value if isinstance(value, list) else [value])
            for index, value in enumerate(ref_values):
                if not isinstance(value, str):
                    errors.append(f"agnes_reference_requires_public_url:{index}")
                    continue
                parsed = urlparse(value)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    errors.append(f"agnes_reference_requires_public_url:{index}")
    return {"status": "CONTRACT_VALID" if not errors else "BLOCKED", "errors": errors, "warnings": []}


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def admit_provider_request(
    request: dict[str, Any],
    *,
    contract_status: str = "CONTRACT_VALID",
    contract_errors: list[str] | None = None,
    receipt_path: Path | None = None,
    existing_request_hash: str | None = None,
) -> dict[str, Any]:
    """Create and optionally persist the one receipt that authorizes a POST."""
    check = model_free_preflight(request, contract_status=contract_status)
    errors = list(check["errors"])
    errors.extend(str(item) for item in (contract_errors or []))
    request_hash = canonical_hash(request)
    if existing_request_hash and existing_request_hash != request_hash:
        errors.append("canonical_request_conflict")
    status = "ADMITTED" if not errors else "REJECTED"
    receipt = {
        "schema": ADMISSION_RECEIPT_SCHEMA,
        "status": status,
        "provider_post_allowed": status == "ADMITTED",
        "request_hash": request_hash,
        "canonical_request": request,
        "preflight": {"status": check["status"], "errors": errors, "warnings": check["warnings"]},
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if receipt_path is not None:
        _write_json_atomic(receipt_path, receipt)
    return receipt


def assert_admission(receipt: dict[str, Any], request_hash: str, *, provider_payload: dict[str, Any] | None = None) -> None:
    """Fail closed immediately before a Provider POST."""
    if not isinstance(receipt, dict) or receipt.get("status") != "ADMITTED" or not receipt.get("provider_post_allowed"):
        raise AdmissionError("provider admission receipt is missing or rejected")
    canonical_request = receipt.get("canonical_request")
    if not isinstance(canonical_request, dict):
        raise AdmissionError("provider admission canonical request is missing")
    if canonical_hash(canonical_request) != receipt.get("request_hash"):
        raise AdmissionError("provider admission canonical request hash is invalid")
    preflight = receipt.get("preflight")
    if not isinstance(preflight, dict) or preflight.get("status") != "CONTRACT_VALID" or preflight.get("errors"):
        raise AdmissionError("provider admission preflight is not CONTRACT_VALID")
    if receipt.get("request_hash") != request_hash:
        raise AdmissionError("provider admission request_hash mismatch")
    if provider_payload is not None and canonical_hash(provider_payload) != canonical_hash(canonical_request.get("provider_payload")):
        raise AdmissionError("provider admission provider payload mismatch")


def delivery_gate(statuses: dict[str, Any]) -> dict[str, Any]:
    """Compute delivery approval with REVIEW/UNKNOWN taking precedence."""
    normalized = {str(key): str(value or "UNKNOWN").upper() for key, value in statuses.items()}
    blocking = {key: value for key, value in normalized.items() if value in {"REVIEW_REQUIRED", "UNKNOWN", "FAIL", "FAILED", "REWORK_REQUIRED", "BLOCKED", "NOT_PROVEN"}}
    # ``all([])`` is true, but an empty/legacy receipt is not evidence of
    # delivery.  Keep the final gate fail-closed when no lanes are present.
    approved = bool(normalized) and not blocking and all(value == "PASS" for value in normalized.values())
    return {
        "status": "PASS" if approved else ("REVIEW_REQUIRED" if any(value in {"REVIEW_REQUIRED", "UNKNOWN", "NOT_PROVEN"} for value in normalized.values()) else "BLOCKED"),
        "delivery_approved": approved,
        "statuses": normalized,
        "blocking": blocking,
    }
