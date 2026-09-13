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
    projection = project_messages(context_messages or [])
    if route is None:
        state = progress(
            state_file,
            state="WAITING_USER",
            current_step="classify_media_intent",
            next_action="provide an explicit image/video generation request",
            action={"step": "classify_media_intent", "request": request},
        )
        return {"status": "WAITING_USER", "route": None, "state": state}

    route_project = route.get("project") or project
    projection_meta = {key: projection.get(key) for key in ("schema", "dropped_messages", "images", "image_bytes", "image_cap", "aggregate_cap", "within_budget", "protected_conclusions")}
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
    for selected_route in selected:
        action = {"step": "execute", "capability": selected_route["capability"], "model": selected_route["model"], "route_fingerprint": route["route_fingerprint"]}
        progress(state_file, state="READY", current_step="execute_media_route", next_action=f"execute {selected_route['capability']}", action=action, metadata={**route_metadata, "expected_artifact": str(output.resolve())})
        try:
            progress(state_file, state="EXECUTING", current_step="execute_media_route", next_action=f"verify {selected_route['capability']} artifact", action=action, metadata=route_metadata)
            artifact_path = Path(run(selected_route, request, output))
            if not artifact_path.is_file() or artifact_path.stat().st_size == 0:
                raise RuntimeError(f"ARTIFACT_INVALID:{artifact_path}")
        except Exception as exc:
            receipt_id = f"failed-{route['route_fingerprint']}"
            receipt = {"schema": "ace.media.receipt.v1", "receipt_id": receipt_id, "status": "FAILED", "task_id": task_id, "project_id": route_project.get("project_id", project.get("project_id")), "manifest_hash": route_metadata["manifest_hash"], "capability": selected_route["capability"], "route": route, "model": selected_route["model"], "provider": selected_route["provider"], "verification": "FAIL", "failure_reason": str(exc), "created_at": time.time(), "projection": projection_meta}
            receipt_path = output / f"{receipt_id}.json"
            _atomic_json(receipt_path, receipt)
            state = progress(state_file, state="FAILED", current_step="execute_media_route", next_action="inspect failed receipt and retry with the same task id", action=action, progress_token=receipt_id, receipt_id=receipt_id, metadata={**route_metadata, "failure_reason": str(exc), "verification_result": "FAIL"})
            return {"status": "FAILED", "route": route, "receipt": receipt, "receipt_path": str(receipt_path), "state": state}
        artifact_id = hashlib.sha256(str(artifact_path.resolve()).encode("utf-8")).hexdigest()[:24]
        artifacts.append({"artifact_id": artifact_id, "path": str(artifact_path.resolve()), "sha256": _sha256(artifact_path), "bytes": artifact_path.stat().st_size, "capability": selected_route["capability"]})
        progress(state_file, state="VERIFYING", current_step="verify_artifact", next_action="write media receipt", action=action, progress_token=artifact_id, artifact_id=artifact_id, metadata={**route_metadata, "actual_artifact": artifact_id})

    receipt_id = f"receipt-{route['route_fingerprint']}"
    receipt = {"schema": "ace.media.receipt.v1", "receipt_id": receipt_id, "status": "SUCCEEDED", "verification": "PASS", "task_id": task_id, "project_id": route_project.get("project_id", project.get("project_id")), "manifest_hash": route_metadata["manifest_hash"], "task_class": route.get("task_class"), "capability": route.get("required_capabilities"), "route": route, "model": [item.get("model") for item in selected], "provider": [item.get("provider") for item in selected], "artifacts": artifacts, "mode": "dry-run" if runner is None else "provider", "created_at": time.time(), "projection": projection_meta}
    receipt_path = output / f"{receipt_id}.json"
    _atomic_json(receipt_path, receipt)
    aggregate_artifact = "aggregate-" + hashlib.sha256(json.dumps(artifacts, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    state = complete(state_file, artifact_id=aggregate_artifact, receipt_id=receipt_id, verification="PASS")
    return {"status": "COMPLETED", "route": route, "receipt": receipt, "receipt_path": str(receipt_path), "state": state}
