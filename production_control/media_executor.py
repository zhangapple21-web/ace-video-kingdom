"""Deterministic media execution bridge with receipts and task checkpoints."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from .media_routing import route_media_demand
from .project import discover_project
from .image_assets import AssetStore
from .projection import project_messages
from .task_state import TERMINAL, complete, create, load, progress


Runner = Callable[[Mapping[str, Any], str, Path], str | Path]


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(raw, path)
    finally:
        if os.path.exists(raw):
            os.unlink(raw)


def _dry_run_runner(route: Mapping[str, Any], request: str, output_dir: Path) -> Path:
    """Create a deterministic local artifact without contacting a provider."""
    output_dir.mkdir(parents=True, exist_ok=True)
    capability = str(route["capability"])
    artifact = output_dir / (capability.replace(".", "_") + ".dry-run.txt")
    artifact.write_text(
        f"DRY_RUN\ncapability={capability}\nprovider={route['provider']}\nmodel={route['model']}\nrequest={request}\n",
        encoding="utf-8",
    )
    return artifact


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _execution_candidates(selected_route: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return the primary route plus only evidence-bound image fallbacks."""
    primary = dict(selected_route)
    candidates: list[dict[str, Any]] = []
    if primary.get("primary_ready", True):
        candidates.append(primary)
    if primary.get("capability") != "image.generate":
        return candidates or [primary]
    for fallback in primary.get("degraded_fallbacks") or []:
        if not isinstance(fallback, Mapping):
            continue
        if fallback.get("status") != "PROBE_PASS" or not fallback.get("credential_ready"):
            continue
        candidate = dict(primary)
        candidate.update({
            "model": fallback.get("model"),
            "credential_env": fallback.get("credential_env"),
            "fallback_from": primary.get("model"),
            "degraded": True,
        })
        candidates.append(candidate)
    return candidates or [primary]


def execute_media_task(
    state_path: str | Path,
    task_id: str,
    request: str,
    *,
    output_dir: str | Path,
    env: Mapping[str, str] | None = None,
    runner: Runner | None = None,
    dry_run: bool = False,
    context_messages: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Route, execute, verify, and close a media task.

    Real provider execution is injected through ``runner`` so tests and offline
    replays never contact a provider. A blocked route is persisted as a receipt
    and leaves the task in ``WAITING_CAPABILITY`` with an actionable next step.
    """
    state_file = Path(state_path)
    output = Path(output_dir)
    try:
        project = discover_project()
    except (FileNotFoundError, ValueError):
        project = {"project_id": "ace-video-kingdom", "manifest_sha256": None, "root": None}
    create(
        state_file,
        task_id,
        request,
        project_id=project.get("project_id", "ace-video-kingdom"),
        metadata={"manifest_hash": project.get("manifest_sha256")},
    )
    existing = load(state_file)
    if existing.get("state") in TERMINAL:
        return {"status": existing["state"], "route": None, "state": existing, "idempotent": True}
    route = route_media_demand(request, env=env)
    route_project = (route.get("project") if isinstance(route, dict) else None) or project
    # Keep transport assets in the canonical project, outside Codex history.
    # The provider runner receives only the projected metadata/references.
    project_root = route_project.get("root") if isinstance(route_project, dict) else None
    asset_store = AssetStore(Path(project_root) / "assets" / "cache" / "transport") if project_root else AssetStore()
    projection = project_messages(context_messages or [], asset_store=asset_store)
    if route is None:
        state = progress(
            state_file,
            state="WAITING_USER",
            current_step="classify_media_intent",
            next_action="provide an explicit image/video generation request",
            action={"step": "classify_media_intent", "request": request},
        )
        return {"status": "WAITING_USER", "route": None, "state": state}

    projection_meta = {key: projection.get(key) for key in ("schema", "dropped_messages", "history_cap", "images", "inline_images", "image_bytes", "image_cap", "aggregate_cap", "within_budget", "protected_conclusions", "unique_asset_ids", "visuals_deferred", "model_boundary")}
    route_metadata = {
        "task_class": route.get("task_class"),
        "required_capability": (route.get("required_capabilities") or [None])[0],
        "selected_route": route.get("selected_routes"),
        "executable": ((route.get("selected_routes") or [{}])[0]).get("executable"),
        "manifest_hash": route_project.get("manifest_sha256") if isinstance(route_project, dict) else project.get("manifest_sha256"),
        "projection": projection_meta,
    }

    if route["status"] != "ROUTED":
        receipt_id = f"blocked-{route.get('route_fingerprint', 'unrouted')}"
        receipt = {
            "schema": "ace.media.receipt.v1",
            "receipt_id": receipt_id,
            "status": "BLOCKED",
            "task_id": task_id,
            "project_id": route_project.get("project_id", project.get("project_id")),
            "manifest_hash": route_metadata["manifest_hash"],
            "task_class": route.get("task_class"),
            "capability": route.get("required_capabilities"),
            "route": route,
            "model": [item.get("model") for item in route.get("selected_routes", [])],
            "provider": [item.get("provider") for item in route.get("selected_routes", [])],
            "verification": "NOT_RUN",
            "created_at": time.time(),
            "projection": projection_meta,
        }
        receipt_path = output / f"{receipt_id}.json"
        _atomic_json(receipt_path, receipt)
        state = progress(
            state_file,
            state="WAITING_CAPABILITY",
            current_step="route_media_demand",
            next_action=route.get("next_action", "resolve route blockers"),
            action={"step": "route_media_demand", "route_fingerprint": route.get("route_fingerprint")},
            progress_token=receipt_id,
            receipt_id=receipt_id,
            metadata={**route_metadata, "blocked_reason": ";".join(route.get("selected_routes", [{}])[0].get("reasons", [])) or route.get("reason")},
        )
        return {"status": "BLOCKED", "route": route, "receipt": receipt, "receipt_path": str(receipt_path), "state": state}

    selected = route["selected_routes"]
    run = runner or _dry_run_runner
    if runner is None and not dry_run:
        receipt_id = f"blocked-no-executor-{route['route_fingerprint']}"
        receipt = {"schema": "ace.media.receipt.v1", "receipt_id": receipt_id, "status": "BLOCKED", "reason": "EXECUTOR_NOT_CONFIGURED", "task_id": task_id, "project_id": route_project.get("project_id", project.get("project_id")), "manifest_hash": route_metadata["manifest_hash"], "capability": route.get("required_capabilities"), "route": route, "verification": "NOT_RUN", "created_at": time.time(), "projection": projection_meta}
        receipt_path = output / f"{receipt_id}.json"
        _atomic_json(receipt_path, receipt)
        state = progress(state_file, state="WAITING_CAPABILITY", current_step="execute_media_route", next_action="bind a provider executor", action={"step": "execute_media_route", "route_fingerprint": route["route_fingerprint"]}, progress_token=receipt_id, receipt_id=receipt_id, metadata={**route_metadata, "blocked_reason": "EXECUTOR_NOT_CONFIGURED"})
        return {"status": "BLOCKED", "route": route, "receipt": receipt, "receipt_path": str(receipt_path), "state": state}

    artifacts: list[dict[str, Any]] = []
    resolved_routes: list[dict[str, Any]] = []
    fallback_events: list[dict[str, Any]] = []
    for selected_route in selected:
        attempts: list[dict[str, Any]] = []
        artifact_path: Path | None = None
        chosen_route: dict[str, Any] | None = None
        last_error: Exception | None = None
        candidates = _execution_candidates(selected_route)
        for candidate in candidates:
            action = {"step": "execute", "capability": candidate["capability"], "model": candidate["model"], "route_fingerprint": route["route_fingerprint"], "degraded": bool(candidate.get("degraded")), "fallback_from": candidate.get("fallback_from")}
            progress(state_file, state="READY", current_step="execute_media_route", next_action=f"execute {candidate['capability']} with {candidate['model']}", action=action, metadata={**route_metadata, "expected_artifact": str(output.resolve())})
            try:
                output.mkdir(parents=True, exist_ok=True)
                progress(state_file, state="EXECUTING", current_step="execute_media_route", next_action=f"verify {candidate['capability']} artifact", action=action, metadata=route_metadata)
                candidate_artifact = Path(run(candidate, request, output))
                if not candidate_artifact.is_file() or candidate_artifact.stat().st_size == 0:
                    raise RuntimeError(f"ARTIFACT_INVALID:{candidate_artifact}")
                artifact_path = candidate_artifact
                chosen_route = candidate
                break
            except Exception as exc:
                last_error = exc
                attempts.append({"model": candidate.get("model"), "status": "FAILED", "error": str(exc), "degraded": bool(candidate.get("degraded"))})
        if artifact_path is None or chosen_route is None:
            receipt_id = f"failed-{route['route_fingerprint']}"
            receipt = {"schema": "ace.media.receipt.v1", "receipt_id": receipt_id, "status": "FAILED", "task_id": task_id, "project_id": route_project.get("project_id", project.get("project_id")), "manifest_hash": route_metadata["manifest_hash"], "capability": selected_route["capability"], "route": route, "model": selected_route["model"], "provider": selected_route["provider"], "verification": "FAIL", "failure_reason": str(last_error), "fallback_attempts": attempts, "degraded": any(item.get("degraded") for item in attempts), "created_at": time.time(), "projection": projection_meta}
            receipt_path = output / f"{receipt_id}.json"
            _atomic_json(receipt_path, receipt)
            state = progress(state_file, state="FAILED", current_step="execute_media_route", next_action="inspect failed receipt and retry with the same task id", action={"step": "execute", "capability": selected_route["capability"], "model": selected_route["model"], "route_fingerprint": route["route_fingerprint"]}, progress_token=receipt_id, receipt_id=receipt_id, metadata={**route_metadata, "failure_reason": str(last_error), "fallback_attempts": attempts, "verification_result": "FAIL"})
            return {"status": "FAILED", "route": route, "receipt": receipt, "receipt_path": str(receipt_path), "state": state}
        if chosen_route.get("degraded"):
            fallback_events.append({"capability": chosen_route["capability"], "from_model": chosen_route.get("fallback_from"), "to_model": chosen_route["model"], "attempts": attempts, "status": "FALLBACK_USED"})
        artifact_id = hashlib.sha256(str(artifact_path.resolve()).encode("utf-8")).hexdigest()[:24]
        artifacts.append({"artifact_id": artifact_id, "path": str(artifact_path.resolve()), "sha256": _sha256(artifact_path), "bytes": artifact_path.stat().st_size, "capability": chosen_route["capability"], "model": chosen_route["model"], "attempts": attempts})
        resolved_routes.append(chosen_route)
        progress(state_file, state="VERIFYING", current_step="verify_artifact", next_action="write media receipt", action={"step": "verify_artifact", "capability": chosen_route["capability"], "model": chosen_route["model"], "route_fingerprint": route["route_fingerprint"]}, progress_token=artifact_id, artifact_id=artifact_id, metadata={**route_metadata, "actual_artifact": artifact_id})

    receipt_id = f"receipt-{route['route_fingerprint']}"
    receipt = {"schema": "ace.media.receipt.v1", "receipt_id": receipt_id, "status": "SUCCEEDED", "verification": "PASS", "task_id": task_id, "project_id": route_project.get("project_id", project.get("project_id")), "manifest_hash": route_metadata["manifest_hash"], "task_class": route.get("task_class"), "capability": route.get("required_capabilities"), "route": route, "model": [item.get("model") for item in resolved_routes], "provider": [item.get("provider") for item in resolved_routes], "artifacts": artifacts, "fallback_used": bool(fallback_events), "degraded": bool(fallback_events), "fallback_events": fallback_events, "mode": "dry-run" if runner is None else "provider", "created_at": time.time(), "projection": projection_meta}
    receipt_path = output / f"{receipt_id}.json"
    _atomic_json(receipt_path, receipt)
    aggregate_artifact = "aggregate-" + hashlib.sha256(json.dumps(artifacts, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    state = complete(state_file, artifact_id=aggregate_artifact, receipt_id=receipt_id, verification="PASS")
    return {"status": "COMPLETED", "route": route, "receipt": receipt, "receipt_path": str(receipt_path), "state": state}
