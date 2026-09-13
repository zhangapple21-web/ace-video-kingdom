"""Persistent task lifecycle with progress and loop guards."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping


STATES = (
    "CREATED", "DISCOVERING", "ROUTED", "READY", "EXECUTING", "VERIFYING",
    "PLANNED", "WAITING_CAPABILITY", "RUNNING", "WAITING_USER",
    "BLOCKED", "COMPLETED", "FAILED", "STALLED", "CANCELLED",
)
TERMINAL = {"COMPLETED", "FAILED", "STALLED", "CANCELLED"}
LIFECYCLE = {
    "CREATED": "CREATED", "DISCOVERING": "DISCOVERING", "ROUTED": "ROUTED",
    "READY": "READY", "PLANNED": "READY", "EXECUTING": "EXECUTING",
    "RUNNING": "EXECUTING", "VERIFYING": "VERIFYING", "COMPLETED": "COMPLETED",
    "FAILED": "FAILED", "STALLED": "STALLED", "CANCELLED": "CANCELLED",
    "BLOCKED": "BLOCKED", "WAITING_CAPABILITY": "BLOCKED", "WAITING_USER": "BLOCKED",
}


def _fingerprint(action: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(action), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(raw, path)
    finally:
        if os.path.exists(raw):
            os.unlink(raw)


def load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def append_event(path: str | Path, event: Mapping[str, Any]) -> dict[str, Any]:
    """Append an external event without resetting lifecycle state.

    User follow-ups, tool callbacks, and resume notifications are persisted in
    the same task record so a mid-turn message cannot make the executor forget
    its current step.  This operation is deliberately non-progressing: only a
    verified artifact/receipt or an explicit ``progress`` call advances state.
    """
    target = Path(path)
    data = load(target)
    if data.get("state") in TERMINAL:
        return data
    payload = dict(event)
    payload.setdefault("at", time.time())
    payload.setdefault("type", "external")
    data.setdefault("events", []).append(payload)
    data["updated_at"] = payload["at"]
    _save(target, data)
    return data


def create(
    path: str | Path,
    task_id: str,
    request: str,
    *,
    project_id: str = "ace-video-kingdom",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    target = Path(path)
    if target.exists():
        return load(target)
    now = time.time()
    data = {
        "schema": "ace.task-state.v1",
        "task_id": task_id,
        "project_id": project_id,
        "manifest_hash": None,
        "request": request,
        "task_class": None,
        "required_capability": None,
        "selected_route": None,
        "executable": None,
        "state": "CREATED",
        "lifecycle_state": "CREATED",
        "current_step": "discover_project",
        "next_action": "discover project manifest and capability registry",
        "expected_artifact": None,
        "actual_artifact": None,
        "receipt_id": None,
        "verification_result": None,
        "failure_reason": None,
        "blocked_reason": None,
        "last_progress": None,
        "last_progress_at": now,
        "created_at": now,
        "updated_at": now,
        "action_fingerprint": None,
        "no_progress_count": 0,
        "retry_count": 0,
        "artifact_ids": [],
        "receipt_ids": [],
        "events": [],
    }
    if metadata:
        data.update({key: value for key, value in metadata.items() if key in data})
    _save(target, data)
    return data


def progress(
    path: str | Path,
    *,
    state: str,
    current_step: str,
    next_action: str,
    action: Mapping[str, Any],
    progress_token: str | None = None,
    artifact_id: str | None = None,
    receipt_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if state not in STATES:
        raise ValueError(f"TASK_STATE_INVALID:{state}")
    target = Path(path)
    data = load(target)
    if data.get("state") in TERMINAL:
        return data
    previous_state = data.get("state")
    fingerprint = _fingerprint(action)
    changed = bool(progress_token or artifact_id or receipt_id) and (
        progress_token != data.get("last_progress") or artifact_id or receipt_id
    )
    state_changed = state != previous_state
    if fingerprint == data.get("action_fingerprint") and not changed and not state_changed:
        data["no_progress_count"] = int(data.get("no_progress_count", 0)) + 1
    else:
        data["no_progress_count"] = 0
    data["action_fingerprint"] = fingerprint
    data["current_step"] = current_step
    data["next_action"] = next_action
    data["state"] = state
    data["lifecycle_state"] = LIFECYCLE[state]
    data["last_progress"] = progress_token or data.get("last_progress")
    data["last_progress_at"] = time.time()
    data["updated_at"] = data["last_progress_at"]
    if receipt_id:
        data["receipt_id"] = receipt_id
    if metadata:
        for key, value in metadata.items():
            if key in data:
                data[key] = value
    if artifact_id and artifact_id not in data["artifact_ids"]:
        data["artifact_ids"].append(artifact_id)
    if receipt_id and receipt_id not in data["receipt_ids"]:
        data["receipt_ids"].append(receipt_id)
    data["events"].append({"at": data["last_progress_at"], "state": state, "step": current_step, "fingerprint": fingerprint, "progress": changed})
    # Two consecutive identical fingerprints are the minimum stall signal:
    # the first occurrence is the prior action, the second is the repeat.
    if data["no_progress_count"] >= 1:
        data["state"] = "STALLED"
        data["lifecycle_state"] = "STALLED"
        data["next_action"] = "inspect last action fingerprint and select a new executable or request user input"
    _save(target, data)
    return data


def complete(path: str | Path, *, artifact_id: str, receipt_id: str, verification: str) -> dict[str, Any]:
    if str(verification).upper() != "PASS":
        raise ValueError("TASK_COMPLETION_REQUIRES_VERIFICATION_PASS")
    return progress(
        path,
        state="COMPLETED",
        current_step="verify",
        next_action="none",
        action={"artifact_id": artifact_id, "receipt_id": receipt_id},
        progress_token=receipt_id,
        artifact_id=artifact_id,
        receipt_id=receipt_id,
        metadata={"verification_result": "PASS", "actual_artifact": artifact_id},
    )
