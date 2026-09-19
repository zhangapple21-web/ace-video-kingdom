"""Unified, fail-closed entry point for the Video Kingdom production workflow.

This module is deliberately small and provider-agnostic.  It does not submit
jobs.  It compiles an episode plan into the persistent ProductionControl state
machine, evaluates the asset/continuity gate, and can ingest already-produced
local receipts without re-submitting anything.  A later worker may consume the
``next_action`` field, but the control plane remains the single source of truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from .engine import ProductionControl, WorkflowError, sha256_file

try:
    from tools.medium_lock import validate_medium_lock
except ImportError:  # pragma: no cover - package used as a script outside repo root
    from medium_lock import validate_medium_lock  # type: ignore


PLACEHOLDER_BYTES = 4096
PLACEHOLDER_SHA256 = {
    # Common 1x1 transparent PNG used by local plan compilers.
    "d6e8c7b6b5b5b4ccf2d5d8f8f7d5d8f8f7d5d8f8f7d5d8f8f7d5d8f8f7d5d8f8",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"JSON_INPUT_INVALID:{path}:{exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"JSON_INPUT_MUST_BE_OBJECT:{path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve(root: Path, raw: str | Path) -> Path:
    candidate = Path(raw)
    return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()


def _all_assets(plan: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    assets = plan.get("assets")
    if not isinstance(assets, dict):
        return result
    for group, rows in assets.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("asset_id"):
                result.append({"group": group, **row})
    return result


def _asset_status(root: Path, row: dict[str, Any]) -> tuple[str, list[str]]:
    errors: list[str] = []
    path = _resolve(root, str(row.get("reference_path") or row.get("path") or ""))
    if not path.is_file():
        return "UNKNOWN", ["SOURCE_NOT_FOUND"]
    actual = sha256_file(path)
    expected = str(row.get("sha256") or "")
    if expected and actual.casefold() != expected.casefold():
        errors.append("SHA256_MISMATCH")
    if path.stat().st_size < PLACEHOLDER_BYTES or actual in PLACEHOLDER_SHA256:
        errors.append("PLACEHOLDER_OR_TOO_SMALL")
    if str(row.get("status", "")).upper() in {"PLACEHOLDER", "REJECTED", "UNKNOWN"}:
        errors.append("DECLARED_NON_PRODUCTION_STATUS")
    return ("PLACEHOLDER" if "PLACEHOLDER_OR_TOO_SMALL" in errors else "ACTIVE"), errors


def _continuity_evidence(root: Path, shot: dict[str, Any]) -> str | None:
    for key in ("continuity_evidence_path", "continuity_evidence", "evidence_path"):
        value = shot.get(key)
        if isinstance(value, str) and value.strip():
            return value
    bridge = shot.get("continuity_bridge")
    if isinstance(bridge, dict):
        for key in ("evidence_path", "path", "artifact_path"):
            value = bridge.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _plan_shot_ids(plan: dict[str, Any]) -> list[str]:
    shots = plan.get("shots") if isinstance(plan.get("shots"), list) else []
    result: list[str] = []
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            continue
        shot_id = str(shot.get("shot_id") or f"SHOT_{index + 1:03d}").strip()
        if not shot_id or shot_id in result:
            raise WorkflowError("PLAN_SHOT_IDS_INVALID")
        result.append(shot_id)
    if not result:
        raise WorkflowError("PLAN_SHOTS_REQUIRED")
    return result


def normalize_scope(plan: dict[str, Any], scope: dict[str, Any] | list[str] | None = None) -> dict[str, Any]:
    """Normalize and validate a staged contiguous shot prefix."""
    plan_ids = _plan_shot_ids(plan)
    if scope is None:
        shot_ids = list(plan_ids)
        active = shot_ids[0]
        requested_id = None
    elif isinstance(scope, list):
        shot_ids = [str(item).strip() for item in scope]
        active = shot_ids[0] if shot_ids else ""
        requested_id = None
    elif isinstance(scope, dict):
        if scope.get("kind") != "SHOT_SUBSET":
            raise WorkflowError("SCOPE_KIND_INVALID")
        raw_ids = scope.get("shot_ids")
        if not isinstance(raw_ids, list):
            raise WorkflowError("SCOPE_SHOT_IDS_REQUIRED")
        shot_ids = [str(item).strip() for item in raw_ids]
        active = str(scope.get("active_shot_id") or (shot_ids[0] if shot_ids else "")).strip()
        requested_id = scope.get("scope_id")
    else:
        raise WorkflowError("SCOPE_INVALID")
    if not shot_ids or any(not item for item in shot_ids) or len(set(shot_ids)) != len(shot_ids):
        raise WorkflowError("SCOPE_SHOT_IDS_NON_EMPTY_UNIQUE_REQUIRED")
    if any(item not in plan_ids for item in shot_ids):
        raise WorkflowError("SCOPE_SHOT_UNKNOWN")
    if shot_ids != plan_ids[:len(shot_ids)]:
        raise WorkflowError("SCOPE_MUST_BE_CONTIGUOUS_PREFIX")
    if active not in shot_ids:
        raise WorkflowError("SCOPE_ACTIVE_SHOT_INVALID")
    canonical = {"kind": "SHOT_SUBSET", "shot_ids": shot_ids, "active_shot_id": active}
    scope_id = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    if requested_id is not None and str(requested_id) != scope_id:
        raise WorkflowError("SCOPE_ID_MISMATCH")
    return {**canonical, "scope_id": scope_id}


def preflight_plan(plan_path: Path, *, mode: str = "PRODUCTION", scope: dict[str, Any] | list[str] | None = None) -> dict[str, Any]:
    """Validate production inputs before materializing a Run.

    A production run is an execution ledger, not a place to discover that the
    asset package is still a placeholder.  Keep this check side-effect free so
    callers can repair assets without creating a misleading DRAFT/blocked run.
    Sandbox callers may still use the historical exploratory bootstrap path.
    """
    plan_path = plan_path.resolve()
    plan = _read_json(plan_path)
    root = plan_path.parent
    normalized_scope = normalize_scope(plan, scope)
    scoped_ids = set(normalized_scope["shot_ids"])
    errors: list[dict[str, Any]] = []
    checked_assets: list[dict[str, Any]] = []

    if not _all_assets(plan):
        errors.append({"reason": "NO_ASSETS_DECLARED"})

    for row in _all_assets(plan):
        asset_id = str(row["asset_id"])
        raw_path = str(row.get("reference_path") or row.get("path") or "")
        status, asset_errors = _asset_status(root, row)
        path = _resolve(root, raw_path)
        actual_sha256 = sha256_file(path) if path.is_file() else None
        checked_assets.append({
            "asset_id": asset_id,
            "path": raw_path,
            "status": status,
            "sha256": actual_sha256,
            "bytes": path.stat().st_size if path.is_file() else None,
        })
        for reason in asset_errors:
            errors.append({"asset_id": asset_id, "reason": reason, "path": raw_path})
        if mode == "PRODUCTION" and not str(row.get("sha256") or "").strip():
            errors.append({"asset_id": asset_id, "reason": "SHA256_REQUIRED_IN_PRODUCTION", "path": raw_path})

    for detail in validate_medium_lock(plan):
        errors.append({"reason": "MEDIUM_LOCK", "detail": detail})

    shots = plan.get("shots") if isinstance(plan.get("shots"), list) else []
    continuity: list[dict[str, Any]] = []
    for index, shot in enumerate(shots[:-1]):
        if not isinstance(shot, dict) or not isinstance(shots[index + 1], dict):
            continue
        from_shot = str(shot.get("shot_id") or f"SHOT_{index + 1:03d}")
        to_shot = str(shots[index + 1].get("shot_id") or f"SHOT_{index + 2:03d}")
        if from_shot not in scoped_ids or to_shot not in scoped_ids:
            continue
        evidence_raw = _continuity_evidence(root, shot)
        row = {"from_shot": from_shot, "to_shot": to_shot, "evidence_path": evidence_raw}
        continuity.append(row)
        if not evidence_raw:
            errors.append({"edge_id": f"{from_shot}->{to_shot}", "reason": "CONTINUITY_EVIDENCE_MISSING"})
            continue
        evidence = _resolve(root, evidence_raw)
        if not evidence.is_file():
            errors.append({"edge_id": f"{from_shot}->{to_shot}", "reason": "CONTINUITY_EVIDENCE_MISSING", "path": evidence_raw})
            continue
        if mode == "PRODUCTION":
            try:
                payload = json.loads(evidence.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                payload = None
            if not isinstance(payload, dict):
                errors.append({"edge_id": f"{from_shot}->{to_shot}", "reason": "CONTINUITY_EVIDENCE_INVALID", "path": evidence_raw})
            else:
                if payload.get("status") not in {"PASS", "READY"}:
                    errors.append({"edge_id": f"{from_shot}->{to_shot}", "reason": "CONTINUITY_EVIDENCE_NOT_READY", "status": payload.get("status")})
                if str(payload.get("from_shot")) != from_shot or str(payload.get("to_shot")) != to_shot:
                    errors.append({"edge_id": f"{from_shot}->{to_shot}", "reason": "CONTINUITY_EDGE_MISMATCH"})

    return {
        "schema": "video_kingdom.production_preflight.v1",
        "status": "READY" if not errors else "BLOCKED",
        "mode": mode,
        "plan": str(plan_path),
        "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "scope": normalized_scope,
        "assets": checked_assets,
        "continuity": continuity,
        "errors": errors,
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def bootstrap(
    plan_path: Path,
    run_path: Path,
    *,
    mode: str = "PRODUCTION",
    run_id: str | None = None,
    request_id: str | None = None,
    executor_thread_id: str | None = None,
    scope: dict[str, Any] | list[str] | None = None,
) -> dict[str, Any]:
    """Create one control run from an immutable episode plan.

    The function registers every declared asset and every adjacent-shot
    continuity edge.  Missing continuity evidence is intentionally registered
    as a missing path so the asset gate becomes BLOCKED instead of silently
    treating a prose bridge as proof.
    """
    plan_path = plan_path.resolve()
    plan = _read_json(plan_path)
    if plan.get("production_integration") is not False:
        raise WorkflowError("PLAN_PRODUCTION_INTEGRATION_MUST_BE_FALSE")
    if run_path.exists():
        raise WorkflowError(f"RUN_ALREADY_EXISTS:{run_path}")
    normalized_scope = normalize_scope(plan, scope) if scope is not None else normalize_scope(plan)
    plan_shot_ids = _plan_shot_ids(plan)
    # Production must prove the asset package and continuity bridges before a
    # Run ledger exists.  Persist only a small sidecar receipt on failure; the
    # actual Run remains uncreated and therefore cannot be mistaken for work
    # that was admitted.
    if mode == "PRODUCTION":
        preflight = preflight_plan(plan_path, mode=mode, scope=normalized_scope)
        if preflight["status"] != "READY":
            receipt_path = run_path.with_suffix(run_path.suffix + ".preflight.json")
            _write_json(receipt_path, preflight)
            return {
                "status": "BLOCKED",
                "run": None,
                "plan": str(plan_path),
                "stage": "ASSETS_BLOCKED",
                "asset_gate": preflight,
                "preflight_receipt": str(receipt_path.resolve()),
                "next_action": "repair assets and continuity evidence before creating a production run",
            }
    root = plan_path.parent
    # A project/episode id is not a production-run identity.  Every bootstrap
    # receives a fresh run id and binds the immutable plan hash plus execution
    # context so an old ledger can never masquerade as this run.
    plan_hash = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    run = ProductionControl.create(
        run_path,
        run_id=run_id or f"run_{uuid.uuid4().hex}",
        mode=mode,
        root=root,
        episode_id=str(plan.get("project_id") or plan_path.stem),
        request_id=request_id or f"req_{uuid.uuid4().hex}",
        executor_thread_id=executor_thread_id,
        request_hash=plan_hash,
        scope=normalized_scope,
        plan_shot_ids=plan_shot_ids,
    )
    for row in _all_assets(plan):
        asset_id = str(row["asset_id"])
        raw_path = str(row.get("reference_path") or row.get("path") or "")
        status, _ = _asset_status(root, row)
        run.register_asset(asset_id, raw_path, required=True, status=status, expected_sha256=row.get("sha256"), role=str(row.get("group") or ""))

    shots = plan.get("shots") if isinstance(plan.get("shots"), list) else []
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            continue
        shot_id = str(shot.get("shot_id") or f"SHOT_{index + 1:03d}")
        next_shot = shots[index + 1] if index + 1 < len(shots) and isinstance(shots[index + 1], dict) else None
        if next_shot:
            edge_id = f"{shot_id}->{next_shot.get('shot_id', f'SHOT_{index + 2:03d}') }"
            evidence = _continuity_evidence(root, shot)
            # A missing path is intentional: it preserves the blocker in the
            # state machine and prevents a textual bridge from becoming proof.
            run.register_continuity(edge_id, from_shot=shot_id, to_shot=str(next_shot.get("shot_id")), evidence_path=evidence or f".control/missing_continuity/{edge_id}.json")

    gate = run.evaluate_asset_gate()
    return {
        "status": gate["status"],
        "run": str(run_path.resolve()),
        "plan": str(plan_path),
        "stage": run.snapshot()["stage"],
        "asset_gate": gate,
        "next_action": next_action(run.snapshot()),
    }


def lock_plan_shots(run_path: Path, plan_path: Path) -> dict[str, Any]:
    """Lock every shot only after the asset gate is READY."""
    run = ProductionControl(run_path)
    plan = _read_json(plan_path.resolve())
    if run.snapshot().get("asset_gate", {}).get("status") != "READY":
        raise WorkflowError("ASSET_GATE_NOT_READY")
    locked: list[str] = []
    for shot in plan.get("shots", []) if isinstance(plan.get("shots"), list) else []:
        if not isinstance(shot, dict):
            continue
        shot_id = str(shot.get("shot_id") or "")
        contract = shot.get("shot_contract") if isinstance(shot.get("shot_contract"), dict) else {}
        duration = shot.get("render", {}).get("seconds") if isinstance(shot.get("render"), dict) else None
        if isinstance(duration, (int, float)):
            contract = {**contract, "duration_seconds": {"min": float(duration), "max": float(duration)}}
        if "actions" not in contract and shot.get("action"):
            contract = {**contract, "actions": [shot["action"]]}
        if "primary_action" not in contract and shot.get("action"):
            contract = {**contract, "primary_action": shot["action"]}
        # Materialize the generic rhythm contract at the single shot-lock point.
        # Content remains explicit/pending for the role room to refine; the
        # provider gate will reject unresolved placeholders before submission.
        if not isinstance(shot.get("shot_rhythm"), dict):
            dialogue = shot.get("dialogue") or shot.get("script", {}).get("dialogue") if isinstance(shot.get("script"), dict) else shot.get("dialogue")
            shot["shot_rhythm"] = {
                "schema": "video_kingdom.shot_rhythm_contract.v1",
                "shot_purpose": shot.get("dramatic_function") or "PENDING_ROLE_ROOM",
                "scale": (shot.get("camera", {}) or {}).get("scale", "medium") if isinstance(shot.get("camera"), dict) else "medium",
                "transition_intent": "PENDING_ROLE_ROOM",
                "movement": (shot.get("camera", {}) or {}).get("movement", "static") if isinstance(shot.get("camera"), dict) else "static",
                "movement_motivation": "PENDING_ROLE_ROOM",
                "timing_basis": "AUDIO_DRIVEN" if dialogue else "ACTION_DRIVEN",
                "audio_anchor": "PENDING_AUDIO_RECEIPT" if dialogue else "NOT_APPLICABLE",
                "script_annotations": {
                    "action": shot.get("action") or "PENDING_ROLE_ROOM",
                    "dialogue": dialogue or "不适用",
                    "emotion": shot.get("emotion_change") or "PENDING_ROLE_ROOM",
                    "subtext": "PENDING_ROLE_ROOM",
                    "motivation": "PENDING_ROLE_ROOM",
                    "atmosphere": "PENDING_ROLE_ROOM",
                },
                "performance_beats": {
                    "speaker_hands_body": "PENDING_ROLE_ROOM",
                    "listener_reaction": "不适用" if not dialogue else "PENDING_ROLE_ROOM",
                    "pause_point": "PENDING_ROLE_ROOM",
                    "inner_voice_mouth_state": "不适用" if not shot.get("inner_voice") else "PENDING_ROLE_ROOM",
                    "cut_motivation": "PENDING_ROLE_ROOM",
                },
            }
        contract = {**contract, "shot_rhythm": shot["shot_rhythm"]}
        if not shot_id:
            raise WorkflowError("SHOT_ID_REQUIRED")
        run.lock_shot(shot_id, contract)
        locked.append(shot_id)
    return {"status": "SHOT_LOCKED", "locked_shots": locked, "next_action": next_action(run.snapshot())}


def ingest_execution(run_path: Path, project_dir: Path) -> dict[str, Any]:
    """Ingest local execution receipts; never submit or retry a provider job."""
    run = ProductionControl(run_path)
    project_dir = project_dir.resolve()
    manifest_path = project_dir / "manifest.json"
    if not manifest_path.is_file():
        raise WorkflowError(f"EXECUTION_MANIFEST_NOT_FOUND:{manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = manifest if isinstance(manifest, list) else [manifest]
    run_snapshot = run.snapshot()
    expected_run_id = str(run_snapshot.get("run_id") or "")
    execution = run_snapshot.get("execution") if isinstance(run_snapshot.get("execution"), dict) else {}
    expected_owner = str(execution.get("owner") or "").strip()
    expected_action_id = str(execution.get("action_id") or "").strip()
    manifest_run_id = manifest.get("run_id") if isinstance(manifest, dict) else None
    if run_snapshot.get("mode") == "PRODUCTION":
        if manifest_run_id is not None and str(manifest_run_id) != expected_run_id:
            raise WorkflowError("EXECUTION_RUN_ID_MISMATCH")
        # An UNKNOWN/FAILED receipt may arrive without a run_id; it remains
        # unresolved and blocked, which is safer than pretending identity was
        # proven. Successful execution rows must always bind to this run.
        if manifest_run_id is None and any(
            str(row.get("run_id") or "") != expected_run_id
            for row in rows
            if isinstance(row, dict) and str(row.get("status") or "UNKNOWN").upper() not in {"UNKNOWN", "FAILED"}
        ):
            raise WorkflowError("EXECUTION_RUN_ID_REQUIRED")
        if any(row.get("run_id") is not None and str(row.get("run_id")) != expected_run_id for row in rows if isinstance(row, dict)):
            raise WorkflowError("EXECUTION_RUN_ID_MISMATCH")
        successful_rows = [
            row for row in rows
            if isinstance(row, dict) and str(row.get("status") or "UNKNOWN").upper() not in {"UNKNOWN", "FAILED"}
        ]
        if successful_rows:
            if not expected_owner or not expected_action_id:
                raise WorkflowError("EXECUTION_BINDING_REQUIRED")
            manifest_action_id = str((manifest.get("action_id") if isinstance(manifest, dict) else "") or "").strip()
            manifest_owner = str(
                ((manifest.get("executor_owner") if isinstance(manifest, dict) else None)
                 or (manifest.get("owner") if isinstance(manifest, dict) else None)
                 or "")
            ).strip()
            if manifest_action_id and manifest_action_id != expected_action_id:
                raise WorkflowError("EXECUTION_ACTION_ID_MISMATCH")
            if manifest_owner and manifest_owner != expected_owner:
                raise WorkflowError("EXECUTION_OWNER_MISMATCH")
            for row in successful_rows:
                row_action_id = str(row.get("action_id") or manifest_action_id).strip()
                if row_action_id != expected_action_id:
                    raise WorkflowError("EXECUTION_ACTION_ID_REQUIRED" if not row_action_id else "EXECUTION_ACTION_ID_MISMATCH")
                row_owner = str(row.get("executor_owner") or row.get("owner") or manifest_owner).strip()
                if row_owner != expected_owner:
                    raise WorkflowError("EXECUTION_OWNER_REQUIRED" if not row_owner else "EXECUTION_OWNER_MISMATCH")
    ingested: list[str] = []
    seen_shots: set[str] = set()
    uncertain_shots: set[str] = set()
    manifest_sha256 = sha256_file(manifest_path)

    def same_ingested_take(take_id: str, shot_id: str, video_id: str, artifact: Path, request_hash: Any) -> bool:
        actual_hash = sha256_file(artifact)
        current = next((row for row in run.snapshot().get("takes", []) if row.get("take_id") == take_id), None)
        if not current:
            return False
        metadata = current.get("metadata") if isinstance(current.get("metadata"), dict) else {}
        return (
            current.get("shot_id") == shot_id
            and current.get("video_id") == video_id
            and current.get("artifact_sha256") == actual_hash
            and metadata.get("request_hash") == request_hash
            and metadata.get("manifest_sha256") == manifest_sha256
        )

    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "UNKNOWN").upper()
        if status in {"UNKNOWN", "FAILED"}:
            shot_id = str(row.get("shot_id") or "")
            if shot_id:
                run.record_execution_outcome(
                    shot_id=shot_id,
                    status=status,
                    manifest_path=manifest_path,
                    manifest_sha256=manifest_sha256,
                    video_id=str(row.get("video_id") or "") or None,
                    action_id=str(row.get("action_id") or "") or None,
                    detail=str(row.get("error") or row.get("detail") or "") or None,
                )
                uncertain_shots.add(shot_id)
            continue
        if status not in {"COMPLETED", "PASS", "READY"}:
            continue
        shot_id, video_id = str(row.get("shot_id") or ""), str(row.get("video_id") or "")
        if shot_id in seen_shots:
            raise WorkflowError(f"DUPLICATE_EXECUTION_RECEIPT:{shot_id}")
        seen_shots.add(shot_id)
        artifact = _resolve(project_dir, str(row.get("artifact_path") or row.get("output") or ""))
        if not shot_id or not video_id or not artifact.is_file():
            continue
        request_hash = row.get("request_hash")
        if request_hash is None and isinstance(row.get("record"), dict):
            request_hash = row["record"].get("request_hash")
        take_id = str(row.get("take_id") or f"{shot_id}_INGESTED")
        if same_ingested_take(take_id, shot_id, video_id, artifact, request_hash):
            ingested.append(shot_id)
            continue
        try:
            run.record_generation(shot_id, take_id, video_id=video_id, artifact_path=artifact, metadata={"ingested_from": str(manifest_path), "manifest_sha256": manifest_sha256, "record": row, "request_hash": request_hash, "run_id": expected_run_id})
        except WorkflowError as exc:
            if str(exc).startswith("TAKE_ALREADY_RECORDED") and same_ingested_take(take_id, shot_id, video_id, artifact, request_hash):
                ingested.append(shot_id)
                continue
            if str(exc).startswith("TAKE_ALREADY_RECORDED"):
                raise WorkflowError(f"EXECUTION_RECEIPT_CONFLICT:{shot_id}/{take_id}") from exc
            raise
        qc = row.get("qc") if isinstance(row.get("qc"), dict) else None
        if qc and set(qc) == {"picture", "motion", "camera", "continuity", "director"}:
            run.record_qc(take_id, qc, notes="ingested local execution receipt")
            if all(value == "PASS" for value in qc.values()):
                run.select_take(shot_id, take_id)
        ingested.append(shot_id)
    acceptance = project_dir / "acceptance_receipt.json"
    expected_shots = list(run.snapshot().get("shots", {}).keys())
    missing_shots = sorted(set(expected_shots) - set(ingested))
    if acceptance.is_file():
        receipt = _read_json(acceptance)
        if run_snapshot.get("mode") == "PRODUCTION" and str(receipt.get("run_id") or "") != expected_run_id:
            raise WorkflowError("ACCEPTANCE_RUN_ID_MISMATCH" if receipt.get("run_id") else "ACCEPTANCE_RUN_ID_REQUIRED")
        if run_snapshot.get("mode") == "PRODUCTION":
            receipt_action_id = str(receipt.get("action_id") or "").strip()
            if not expected_action_id:
                raise WorkflowError("ACCEPTANCE_EXECUTION_BINDING_REQUIRED")
            if receipt_action_id != expected_action_id:
                raise WorkflowError("ACCEPTANCE_ACTION_ID_MISMATCH" if receipt_action_id else "ACCEPTANCE_ACTION_ID_REQUIRED")
            receipt_owner = str(
                (receipt.get("executor_owner") or receipt.get("owner") or "")
            ).strip()
            if not expected_owner:
                raise WorkflowError("ACCEPTANCE_EXECUTION_OWNER_REQUIRED")
            if receipt_owner != expected_owner:
                raise WorkflowError("ACCEPTANCE_OWNER_MISMATCH" if receipt_owner else "ACCEPTANCE_OWNER_REQUIRED")
        output = receipt.get("output")
        if receipt.get("status") == "PASS" and output and not missing_shots:
            if run.snapshot().get("mode") == "PRODUCTION":
                lane_statuses = {
                    "pacing": (receipt.get("pacing") or {}).get("status"),
                    "continuity": (receipt.get("continuity") or {}).get("status"),
                    "subtitle": receipt.get("subtitle"),
                    "audio": receipt.get("audio"),
                    "creative": receipt.get("creative"),
                }
                if receipt.get("delivery_approved") is not True or any(value != "PASS" for value in lane_statuses.values()):
                    raise WorkflowError("ACCEPTANCE_LANES_NOT_READY")
                continuity_rows = (receipt.get("continuity") or {}).get("shots") or []
                reviews = {(row.get("shot_id"), row.get("status")) for row in ((receipt.get("continuity") or {}).get("review") or []) if isinstance(row, dict)}
                for row in continuity_rows:
                    if isinstance(row, dict) and row.get("status") == "REVIEW_REQUIRED" and (row.get("shot_id"), "PASS_REVIEWED_NO_INTERNAL_CUTS") not in reviews:
                        raise WorkflowError("ACCEPTANCE_CONTINUITY_REVIEW_REQUIRED")
            assembled = _resolve(project_dir, str(output))
            if assembled.is_file():
                expected_hash = receipt.get("artifact_sha256") or receipt.get("output_sha256")
                if expected_hash and sha256_file(assembled) != expected_hash:
                    raise WorkflowError("ACCEPTANCE_ARTIFACT_HASH_MISMATCH")
                run.record_assembly(assembled, ordered_shots=expected_shots, metadata={"ingested_from": str(acceptance), "acceptance": receipt, "acceptance_path": str(acceptance), "acceptance_sha256": sha256_file(acceptance), "run_id": expected_run_id})
                run.promote_delivery(assembled)
    snapshot = run.snapshot()
    status = "BLOCKED" if uncertain_shots else snapshot["stage"]
    return {"status": status, "ingested_shots": ingested, "uncertain_shots": sorted(uncertain_shots), "missing_shots": missing_shots, "next_action": next_action(snapshot), "run": str(run_path.resolve())}


def recover(run_path: Path) -> dict[str, Any]:
    """Read and validate a run after interruption without repeating actions."""
    run = ProductionControl(run_path)
    chain = run.verify_event_chain()
    if chain["status"] != "PASS":
        return {"status": "BLOCKED", "reason": "EVENT_CHAIN_INVALID", "chain": chain, "next_action": "repair evidence before any retry"}
    snapshot = run.snapshot()
    return {"status": snapshot.get("stage"), "chain": chain, "next_action": next_action(snapshot), "run": str(run_path.resolve())}


def next_action(snapshot: dict[str, Any]) -> str:
    stage = snapshot.get("stage")
    gate = snapshot.get("asset_gate", {}).get("status")
    if stage in {"DRAFT", "ASSETS_BLOCKED"} or gate != "READY":
        return "repair assets/continuity, then run asset-gate"
    if stage == "ASSETS_READY":
        return "lock-plan-shots"
    if stage == "SHOT_LOCKED":
        return "admit-generation per shot (external provider call remains separate)"
    if stage in {"GENERATION_ADMITTED", "GENERATED", "QC_BLOCKED"}:
        return "ingest/review takes and record five-layer QC"
    if stage == "QC_READY":
        return "select approved takes, then record assembly"
    if stage == "ASSEMBLED":
        return "promote delivery after final integrity and full-episode QC"
    if stage == "DELIVERY_READY":
        return "mark delivered only at the authorized destination"
    if stage == "DELIVERED":
        return "complete"
    return "inspect run state"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Unified fail-closed video production entry point")
    sub = parser.add_subparsers(dest="command", required=True)
    auto = sub.add_parser("auto", help="route a user demand through the current run state")
    auto.add_argument("--request", type=Path, help="JSON request containing goal/plan/run/project_dir/text")
    auto.add_argument("--text", help="short natural-language demand")
    auto.add_argument("--idea", help="story idea; used as demand text when no request file is supplied")
    auto.add_argument("--goal", choices=("PRODUCE", "RESUME", "STATUS", "AUDIT", "DELIVER"))
    auto.add_argument("--plan", type=Path)
    auto.add_argument("--run", type=Path)
    auto.add_argument("--project-dir", type=Path)
    auto.add_argument("--output-root", type=Path)
    auto.add_argument("--project-id")
    auto.add_argument("--target-seconds", type=int)
    auto.add_argument("--mode", choices=("PRODUCTION", "SANDBOX"), default="PRODUCTION")
    model_route = sub.add_parser("model-route", help="compile natural language into capabilities and an evidence-bound labor candidate")
    model_route.add_argument("--text", required=True, help="natural-language task; do not include a model name unless explicitly overriding")
    model_route.add_argument(
        "--scope",
        default="auto",
        help="autonomous capability scope (local/remote candidates); use current_control_plane to fail closed at the local production boundary",
    )
    model_route.add_argument("--model-override", help="explicit override; unavailable or unproven overrides fail closed")
    model_route.add_argument("--registry", type=Path)
    model_route.add_argument("--health-snapshot", type=Path, help="optional existing ACE Watchdog snapshot; read-only")
    boot = sub.add_parser("bootstrap")
    boot.add_argument("plan", type=Path)
    boot.add_argument("run", type=Path)
    boot.add_argument("--mode", choices=("PRODUCTION", "SANDBOX"), default="PRODUCTION")
    preflight = sub.add_parser("preflight")
    preflight.add_argument("plan", type=Path)
    preflight.add_argument("--mode", choices=("PRODUCTION", "SANDBOX"), default="PRODUCTION")
    lock = sub.add_parser("lock-plan-shots")
    lock.add_argument("run", type=Path)
    lock.add_argument("plan", type=Path)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("run", type=Path)
    ingest.add_argument("project_dir", type=Path)
    recover_cmd = sub.add_parser("recover")
    recover_cmd.add_argument("run", type=Path)
    owner = sub.add_parser("assign-owner")
    owner.add_argument("run", type=Path)
    owner.add_argument("owner")
    owner.add_argument("action_id")
    owner.add_argument("--executor-kind", default="external_provider")
    handoff = sub.add_parser("handoff")
    handoff.add_argument("run", type=Path)
    handoff.add_argument("from_owner")
    handoff.add_argument("to_owner")
    handoff.add_argument("action_id")
    handoff.add_argument("--reason", default="")
    args = parser.parse_args(argv)
    try:
        if args.command == "model-route":
            from .demand import load_provider_health_snapshot, route_model_demand
            result = route_model_demand(
                args.text,
                scope=args.scope,
                model_override=args.model_override,
                registry_path=args.registry,
                health_snapshot=(load_provider_health_snapshot(args.health_snapshot) if args.health_snapshot else None),
            )
        elif args.command == "auto":
            from .demand import route
            if args.request:
                result = route(args.request, root=Path.cwd())
            else:
                result = route({
                    "text": args.text or args.idea or "",
                    "idea": args.idea,
                    "goal": args.goal,
                    "plan": str(args.plan) if args.plan else None,
                    "run": str(args.run) if args.run else None,
                    "project_dir": str(args.project_dir) if args.project_dir else None,
                    "output_root": str(args.output_root) if args.output_root else None,
                    "project_id": args.project_id,
                    "target_seconds": args.target_seconds,
                    "mode": args.mode,
                }, root=Path.cwd())
        elif args.command == "preflight":
            result = preflight_plan(args.plan, mode=args.mode)
        elif args.command == "bootstrap":
            result = bootstrap(args.plan, args.run, mode=args.mode)
        elif args.command == "lock-plan-shots":
            result = lock_plan_shots(args.run, args.plan)
        elif args.command == "ingest":
            result = ingest_execution(args.run, args.project_dir)
        elif args.command == "assign-owner":
            result = ProductionControl(args.run).assign_execution_owner(owner=args.owner, action_id=args.action_id, executor_kind=args.executor_kind)
        elif args.command == "handoff":
            result = ProductionControl(args.run).handoff_execution(from_owner=args.from_owner, to_owner=args.to_owner, action_id=args.action_id, reason=args.reason)
        else:
            result = recover(args.run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") not in {"BLOCKED", "FAILED"} else 2
    except (WorkflowError, OSError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
