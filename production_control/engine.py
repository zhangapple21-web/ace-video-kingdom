from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    from tools.validate_continuity_bridge import validate_bridge
except ImportError:  # pragma: no cover - package used as a script outside repo root
    from validate_continuity_bridge import validate_bridge  # type: ignore


SCHEMA = "video_kingdom.production_control_run.v1"
_CLOSURE_SCHEMA = "video_kingdom.closure_manifest.v1"
_FRAME_READY_CONTINUITY_STATUSES = {"READY", "PASS", "VERIFIED"}
TERMINAL_STAGES = {
    "DELIVERED",
    "DELIVERED_CLOSED",
    "FAILED",
    "BLOCKED",
    "PAUSED",
    "ARCHIVED",
}
STAGE_ORDER = {
    "DRAFT": 0,
    "ASSETS_BLOCKED": 1,
    "ASSETS_READY": 2,
    "SHOT_LOCKED": 3,
    "GENERATION_ADMITTED": 4,
    "GENERATED": 5,
    "QC_BLOCKED": 6,
    "QC_READY": 7,
    "ASSEMBLED": 8,
    "DELIVERY_READY": 9,
    "DELIVERED": 10,
    "PAUSED": 97,
    "BLOCKED": 98,
    "FAILED": 99,
    "ARCHIVED": 100,
    "DELIVERED_CLOSED": 101,
}
CLOSURE_OUTCOMES = {"DELIVERED_CLOSED", "BLOCKED", "PAUSED", "ARCHIVED"}
QC_LAYERS = ("picture", "motion", "camera", "continuity", "director")
MIN_PRODUCTION_ASSET_BYTES = 4096
STALE_LOCK_SECONDS = 60.0


class WorkflowError(RuntimeError):
    """Raised when a fail-closed workflow invariant is violated."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _state_digest(payload: dict[str, Any]) -> str:
    """Hash mutable state independently of the event log.

    The event chain proves ordering and provenance; this second digest proves
    that the current materialized state was not edited behind the chain.
    """
    body = dict(payload)
    body.pop("events", None)
    body.pop("state_hash", None)
    return _hash_bytes(_canonical(body).encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contained_path(root: Path, value: str | Path) -> Path:
    """Resolve a workflow path and reject workspace/symlink escapes."""
    root = root.resolve()
    candidate = (value if Path(value).is_absolute() else root / value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise WorkflowError(f"PATH_ESCAPE:{value}") from exc
    return candidate


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _pre_provider_continuity_ready(evidence: dict[str, Any]) -> bool:
    """True when a registered bridge may admit generation without frame proof.

    Frame-ready statuses remain valid. A structurally complete
    ``PENDING_FRAME_PROOF`` prose bridge is also allowed so the next locked
    shot can be admitted before either take exists. A READY file without
    verified frames is still blocked by ``validate_bridge``.
    """
    status = evidence.get("status")
    if status in _FRAME_READY_CONTINUITY_STATUSES:
        return True
    if status != "PENDING_FRAME_PROOF":
        return False
    return validate_bridge(evidence).get("status") == "PASS"


@contextmanager
def _lock(path: Path, timeout: float = 8.0) -> Iterator[None]:
    """Small cross-process lock; no third-party runtime required."""
    lock_path = path.with_name(path.name + ".lock")
    deadline = time.monotonic() + timeout
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            # A crashed worker can leave the marker behind.  Reclaim only a
            # sufficiently old marker whose recorded PID is no longer alive;
            # malformed or recent markers remain fail-closed.
            try:
                age = time.time() - lock_path.stat().st_mtime
                raw_pid = lock_path.read_text(encoding="ascii", errors="ignore").strip()
                pid = int(raw_pid)
                try:
                    os.kill(pid, 0)
                    alive = True
                except PermissionError:
                    alive = True
                except OSError:
                    alive = False
                if age > STALE_LOCK_SECONDS and not alive:
                    lock_path.unlink(missing_ok=True)
                    continue
            except (OSError, ValueError):
                pass
            if time.monotonic() >= deadline:
                raise WorkflowError(f"LOCK_TIMEOUT:{path}")
            time.sleep(0.05)
    try:
        os.write(fd, str(os.getpid()).encode("ascii", "ignore"))
        os.close(fd)
        fd = None
        yield
    finally:
        if fd is not None:
            os.close(fd)
        lock_path.unlink(missing_ok=True)


def _probe_media(path: Path) -> dict[str, Any] | None:
    """Return ffprobe metadata when available; None means UNKNOWN."""
    ffprobe = os.environ.get("FFPROBE_BIN") or shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration:stream=width,height,r_frame_rate", "-of", "json", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(proc.stdout)
        streams = payload.get("streams") or []
        video = next((s for s in streams if s.get("width") and s.get("height")), {})
        rate = video.get("r_frame_rate")
        fps = None
        if isinstance(rate, str) and "/" in rate:
            numerator, denominator = rate.split("/", 1)
            if float(denominator):
                fps = round(float(numerator) / float(denominator), 3)
        return {
            "duration_seconds": float((payload.get("format") or {}).get("duration")) if (payload.get("format") or {}).get("duration") else None,
            "width": video.get("width"),
            "height": video.get("height"),
            "fps": fps,
        }
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return None


def _extract_frames(artifact: Path, output_dir: Path) -> dict[str, Any]:
    """Extract real first/last frames; failure is intentionally fatal."""
    ffmpeg = os.environ.get("FFMPEG_BIN") or shutil.which("ffmpeg")
    if not ffmpeg:
        raise WorkflowError("FRAME_EXTRACTION_TOOL_NOT_FOUND")
    output_dir.mkdir(parents=True, exist_ok=True)
    first = output_dir / "first.png"
    last = output_dir / "last.png"
    commands = (
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(artifact), "-vf", "select=eq(n\\,0)", "-frames:v", "1", str(first)],
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-sseof", "-0.1", "-i", str(artifact), "-frames:v", "1", str(last)],
    )
    try:
        for command in commands:
            subprocess.run(command, check=True, capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorkflowError("FRAME_EXTRACTION_FAILED") from exc
    if not first.is_file() or not last.is_file() or not first.stat().st_size or not last.stat().st_size:
        raise WorkflowError("FRAME_EXTRACTION_INCOMPLETE")
    try:
        version = subprocess.run([ffmpeg, "-version"], check=True, capture_output=True, text=True).stdout.splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        version = str(ffmpeg)
    return {
        "tool": "ffmpeg",
        "tool_path": str(ffmpeg),
        "tool_version": version,
        "first_frame": {"path": str(first), "sha256": sha256_file(first)},
        "last_frame": {"path": str(last), "sha256": sha256_file(last)},
    }


class ProductionControl:
    """Persistent production state machine with append-only evidence events."""

    def __init__(self, run_path: Path, *, root: Path | None = None):
        self.run_path = run_path.resolve()
        self.root = (root or self.run_path.parent).resolve()

    @classmethod
    def create(
        cls,
        run_path: Path,
        *,
        run_id: str | None = None,
        mode: str = "PRODUCTION",
        root: Path | None = None,
        episode_id: str | None = None,
        request_id: str | None = None,
        executor_thread_id: str | None = None,
        request_hash: str | None = None,
        scope: dict[str, Any] | None = None,
        plan_shot_ids: list[str] | None = None,
        scope_explicit: bool | None = None,
        project_id: str | None = None,
        script_hash: str | None = None,
        contract_hash: str | None = None,
    ) -> "ProductionControl":
        if mode not in {"PRODUCTION", "SANDBOX"}:
            raise WorkflowError(f"INVALID_MODE:{mode}")
        run_path = run_path.resolve()
        run_path.parent.mkdir(parents=True, exist_ok=True)
        if run_path.exists():
            raise WorkflowError(f"RUN_ALREADY_EXISTS:{run_path}")
        run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        root = (root or run_path.parent).resolve()
        payload = {
            "schema": SCHEMA,
            "run_id": run_id,
            "episode_id": episode_id,
            "request_id": request_id,
            "executor_thread_id": executor_thread_id,
            "request_hash": request_hash,
            "identity": {
                "project_id": str(project_id).strip() if project_id else None,
                "script_hash": str(script_hash).strip() if script_hash else None,
                "contract_hash": str(contract_hash).strip() if contract_hash else None,
            },
            "mode": mode,
            "root": str(root),
            "scope": scope,
            "scope_explicit": bool(scope_explicit),
            "plan_shot_ids": list(plan_shot_ids or []),
            "total_plan_shots": len(plan_shot_ids or []),
            "revision": 0,
            "stage": "DRAFT",
            "assets": {},
            "continuity": {},
            "shots": {},
            "generation_admissions": [],
            "execution_outcomes": [],
            "execution": {
                "owner": None,
                "action_id": None,
                "executor_kind": None,
                "handoff_seq": 0,
            },
            "takes": [],
            "qc": {},
            "assembly": None,
            "delivery": None,
            "closure": None,
            "events": [],
        }
        if isinstance(scope, dict):
            event_body = {
                "event": "SCOPE_BOUND",
                "revision": 1,
                "at": _utc_now(),
                "data": {
                    "scope": dict(scope),
                    "plan_shot_ids": list(plan_shot_ids or []),
                },
                "prev_event_hash": "GENESIS",
            }
            event_body["event_hash"] = _hash_bytes(
                _canonical(event_body).encode("utf-8")
            )
            payload["events"].append(event_body)
            payload["revision"] = 1
        payload["state_hash"] = _state_digest(payload)
        cls(run_path)._write(payload)
        return cls(run_path)

    def snapshot(self) -> dict[str, Any]:
        return self._load()

    def verify_event_chain(self) -> dict[str, Any]:
        """Recompute the append-only event hash chain without mutating state."""
        payload = self._load()
        previous = "GENESIS"
        errors: list[dict[str, Any]] = []
        for index, event in enumerate(payload.get("events", [])):
            if event.get("revision") != index + 1:
                errors.append({"index": index, "reason": "EVENT_REVISION_MISMATCH"})
            if event.get("prev_event_hash") != previous:
                errors.append({"index": index, "reason": "PREV_HASH_MISMATCH"})
            body = dict(event)
            recorded = body.pop("event_hash", None)
            actual = _hash_bytes(_canonical(body).encode("utf-8"))
            if recorded != actual:
                errors.append({"index": index, "reason": "EVENT_HASH_MISMATCH", "expected": recorded, "actual": actual})
            previous = recorded or ""
        recorded_state_hash = payload.get("state_hash")
        actual_state_hash = _state_digest(payload)
        if not recorded_state_hash:
            errors.append({"reason": "STATE_HASH_MISSING"})
        elif recorded_state_hash != actual_state_hash:
            errors.append({"reason": "STATE_HASH_MISMATCH", "expected": recorded_state_hash, "actual": actual_state_hash})
        return {"status": "PASS" if not errors else "FAIL", "event_count": len(payload.get("events", [])), "errors": errors}

    def _load(self) -> dict[str, Any]:
        if not self.run_path.is_file():
            raise WorkflowError(f"RUN_NOT_FOUND:{self.run_path}")
        try:
            payload = json.loads(self.run_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"RUN_CORRUPT:{self.run_path}:{exc}") from exc
        if payload.get("schema") != SCHEMA:
            raise WorkflowError("SCHEMA_MISMATCH")
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        temp = self.run_path.with_name(self.run_path.name + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, self.run_path)

    def _root(self, payload: dict[str, Any]) -> Path:
        return Path(str(payload.get("root") or self.root)).resolve()

    def _mutate(self, event: str, data: dict[str, Any], fn) -> dict[str, Any]:
        with _lock(self.run_path):
            integrity = self.verify_event_chain()
            if integrity["status"] != "PASS":
                raise WorkflowError("RUN_INTEGRITY_INVALID")
            payload = self._load()
            if payload.get("closure") is not None:
                raise WorkflowError("RUN_ALREADY_CLOSED")
            # A delivered run is still allowed one and only one explicit
            # close event.  All other mutations remain blocked at terminal
            # stages.  This keeps delivery and closure separate without
            # opening a post-delivery editing path.
            if payload.get("stage") in TERMINAL_STAGES and event != "RUN_CLOSED":
                raise WorkflowError(f"TERMINAL_STAGE:{payload['stage']}")
            before = payload.get("revision", 0)
            result = fn(payload)
            event_body = {"event": event, "revision": before + 1, "at": _utc_now(), "data": data}
            prior_hash = payload["events"][-1].get("event_hash") if payload.get("events") else "GENESIS"
            event_body["prev_event_hash"] = prior_hash
            event_body["event_hash"] = _hash_bytes(_canonical(event_body).encode("utf-8"))
            payload["events"].append(event_body)
            payload["revision"] = before + 1
            payload["state_hash"] = _state_digest(payload)
            self._write(payload)
            return result if result is not None else payload

    @staticmethod
    def _advance(payload: dict[str, Any], stage: str) -> None:
        current = payload["stage"]
        if current == "DELIVERED" and stage == "DELIVERED_CLOSED":
            payload["stage"] = stage
            return
        if current in TERMINAL_STAGES and current != stage:
            raise WorkflowError(f"TERMINAL_STAGE:{current}")
        if STAGE_ORDER[stage] < STAGE_ORDER[current]:
            raise WorkflowError(f"NON_MONOTONIC_STAGE:{current}->{stage}")
        payload["stage"] = stage

    def register_asset(self, asset_id: str, path: str | Path, *, required: bool = True, status: str = "ACTIVE", expected_sha256: str | None = None, role: str = "") -> dict[str, Any]:
        if not str(asset_id).strip():
            raise WorkflowError("ASSET_ID_REQUIRED")
        path = Path(path)
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            existing = payload["assets"].get(asset_id)
            record = {"asset_id": asset_id, "path": str(path), "required": required, "status": status, "role": role, "expected_sha256": expected_sha256}
            if existing and existing != record:
                raise WorkflowError(f"ASSET_CONFLICT:{asset_id}")
            payload["assets"][asset_id] = record
            return record
        return self._mutate("ASSET_REGISTERED", {"asset_id": asset_id, "path": str(path)}, apply)

    def register_continuity(self, edge_id: str, *, from_shot: str, to_shot: str, evidence_path: str | Path, expected_sha256: str | None = None) -> dict[str, Any]:
        if not str(edge_id).strip() or not str(from_shot).strip() or not str(to_shot).strip():
            raise WorkflowError("CONTINUITY_FIELDS_REQUIRED")
        evidence_path = Path(evidence_path)
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            record = {"edge_id": edge_id, "from_shot": from_shot, "to_shot": to_shot, "evidence_path": str(evidence_path), "expected_sha256": expected_sha256}
            existing = payload["continuity"].get(edge_id)
            if existing and existing != record:
                raise WorkflowError(f"CONTINUITY_CONFLICT:{edge_id}")
            payload["continuity"][edge_id] = record
            return record
        return self._mutate("CONTINUITY_REGISTERED", {"edge_id": edge_id}, apply)

    def bind_asset_gate_receipt(self, receipt_path: str | Path) -> dict[str, Any]:
        """Bind an upstream validator receipt without trusting it blindly.

        The receipt is evidence provenance only.  Local path/hash/continuity
        checks still run in :meth:`evaluate_asset_gate`; a stale or non-READY
        upstream receipt keeps the run blocked.
        """
        receipt_path = Path(receipt_path)
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            root = self._root(payload)
            candidate = _contained_path(root, receipt_path)
            if not candidate.is_file():
                raise WorkflowError(f"RECEIPT_NOT_FOUND:{receipt_path}")
            try:
                receipt = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise WorkflowError(f"RECEIPT_INVALID:{receipt_path}:{exc}") from exc
            status = receipt.get("status")
            if status not in {"READY", "CONDITIONAL", "BLOCKED"}:
                raise WorkflowError(f"RECEIPT_STATUS_UNKNOWN:{status}")
            payload["upstream_asset_gate_receipt"] = {"path": str(receipt_path), "sha256": sha256_file(candidate), "status": status, "schema": receipt.get("schema"), "bound_at": _utc_now()}
            return payload["upstream_asset_gate_receipt"]
        return self._mutate("UPSTREAM_ASSET_GATE_BOUND", {"receipt_path": str(receipt_path)}, apply)

    def _evaluate_asset_gate_payload(self, payload: dict[str, Any], *, mutate_stage: bool = True) -> dict[str, Any]:
            errors: list[dict[str, Any]] = []
            checked: list[dict[str, Any]] = []
            root = self._root(payload)
            for asset_id, asset in sorted(payload["assets"].items()):
                if not asset.get("required"):
                    continue
                if asset.get("status") in {"PLACEHOLDER", "REJECTED", "UNKNOWN"}:
                    errors.append({"asset_id": asset_id, "reason": "INVALID_ASSET_STATUS", "status": asset.get("status")})
                    continue
                path = Path(str(asset.get("path")))
                try:
                    candidate = _contained_path(root, path)
                except WorkflowError:
                    candidate = None
                try:
                    if candidate is None:
                        raise ValueError
                    candidate.relative_to(root.resolve())
                except ValueError:
                    errors.append({"asset_id": asset_id, "reason": "PATH_ESCAPE", "path": str(path)})
                    continue
                if not candidate.is_file():
                    errors.append({"asset_id": asset_id, "reason": "SOURCE_NOT_FOUND", "path": str(path)})
                    continue
                actual = sha256_file(candidate)
                expected = asset.get("expected_sha256")
                checked.append({"asset_id": asset_id, "path": str(path), "sha256": actual})
                if payload.get("mode") == "PRODUCTION" and not expected:
                    errors.append({"asset_id": asset_id, "reason": "SHA256_REQUIRED_IN_PRODUCTION"})
                if expected and actual.casefold() != expected.casefold():
                    errors.append({"asset_id": asset_id, "reason": "SHA256_MISMATCH", "expected": expected, "actual": actual})
                if payload.get("mode") == "PRODUCTION" and candidate.stat().st_size < MIN_PRODUCTION_ASSET_BYTES:
                    errors.append({"asset_id": asset_id, "reason": "PLACEHOLDER_OR_TOO_SMALL", "bytes": candidate.stat().st_size})
            for edge_id, edge in sorted(payload["continuity"].items()):
                evidence = Path(str(edge["evidence_path"]))
                try:
                    candidate = _contained_path(root, evidence)
                except WorkflowError:
                    candidate = None
                try:
                    if candidate is None:
                        raise ValueError
                    candidate.relative_to(root.resolve())
                except ValueError:
                    errors.append({"edge_id": edge_id, "reason": "PATH_ESCAPE", "path": str(evidence)})
                    continue
                if not candidate.is_file():
                    errors.append({"edge_id": edge_id, "reason": "CONTINUITY_EVIDENCE_MISSING", "path": str(evidence)})
                    continue
                actual = sha256_file(candidate)
                if edge.get("expected_sha256") and edge["expected_sha256"] != actual:
                    errors.append({"edge_id": edge_id, "reason": "CONTINUITY_SHA256_MISMATCH", "expected": edge["expected_sha256"], "actual": actual})
                if payload.get("mode") == "PRODUCTION":
                    try:
                        evidence_payload = json.loads(candidate.read_text(encoding="utf-8"))
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                        evidence_payload = None
                    if not isinstance(evidence_payload, dict):
                        errors.append({"edge_id": edge_id, "reason": "CONTINUITY_EVIDENCE_INVALID"})
                    else:
                        if not _pre_provider_continuity_ready(evidence_payload):
                            errors.append({"edge_id": edge_id, "reason": "CONTINUITY_EVIDENCE_NOT_READY", "status": evidence_payload.get("status")})
                        if str(evidence_payload.get("from_shot")) != str(edge.get("from_shot")) or str(evidence_payload.get("to_shot")) != str(edge.get("to_shot")):
                            errors.append({"edge_id": edge_id, "reason": "CONTINUITY_EDGE_MISMATCH"})
            # Production runs with multiple locked shots must have an
            # evidence-backed bridge for every adjacent pair. Sandbox runs
            # may explore incomplete continuity, but that state can never
            # become a production admission.
            shot_ids = list(payload.get("shots", {}))
            if payload.get("mode") == "PRODUCTION" and len(shot_ids) > 1:
                edges = {(str(edge.get("from_shot")), str(edge.get("to_shot"))) for edge in payload["continuity"].values()}
                for from_shot, to_shot in zip(shot_ids, shot_ids[1:]):
                    if (from_shot, to_shot) not in edges:
                        errors.append({"edge_id": f"{from_shot}->{to_shot}", "reason": "CONTINUITY_EDGE_MISSING"})
                for edge_id, edge in payload["continuity"].items():
                    if str(edge.get("from_shot")) not in shot_ids or str(edge.get("to_shot")) not in shot_ids:
                        errors.append({"edge_id": edge_id, "reason": "CONTINUITY_SHOT_UNKNOWN"})
            upstream = payload.get("upstream_asset_gate_receipt")
            if upstream:
                upstream_path = Path(str(upstream.get("path") or ""))
                try:
                    upstream_candidate = _contained_path(root, upstream_path)
                except WorkflowError:
                    upstream_candidate = None
                if upstream_candidate is None or not upstream_candidate.is_file():
                    errors.append({"reason": "UPSTREAM_ASSET_GATE_RECEIPT_MISSING"})
                else:
                    actual_receipt_hash = sha256_file(upstream_candidate)
                    if actual_receipt_hash != upstream.get("sha256"):
                        errors.append({"reason": "UPSTREAM_ASSET_GATE_RECEIPT_DRIFT"})
                    try:
                        current_receipt = json.loads(upstream_candidate.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        current_receipt = {}
                    if current_receipt.get("status") != "READY":
                        errors.append({"reason": "UPSTREAM_ASSET_GATE_NOT_READY", "status": current_receipt.get("status")})
            status = "READY" if not errors and payload["assets"] else "BLOCKED"
            receipt = {"status": status, "checked": checked, "errors": errors, "evaluated_at": _utc_now()}
            if mutate_stage:
                payload["asset_gate"] = receipt
            if mutate_stage and status == "BLOCKED":
                # An asset regression invalidates all downstream work, but the
                # evidence is retained.  This is the only intentional stage
                # reset in the state machine and is always fail-closed.
                payload["stage"] = "ASSETS_BLOCKED"
                for admission in payload["generation_admissions"]:
                    admission["invalidated"] = True
                for shot in payload["shots"].values():
                    shot["stale"] = True
                    shot["selected_take_id"] = None
                for take in payload["takes"]:
                    take["stale"] = True
                    take["selected"] = False
            elif mutate_stage and payload["stage"] in {"DRAFT", "ASSETS_BLOCKED"}:
                self._advance(payload, "ASSETS_READY")
            return receipt

    def evaluate_asset_gate(self, *, persist: bool = True) -> dict[str, Any]:
        payload = self._load()
        if not persist or payload.get("stage") in TERMINAL_STAGES:
            return self._evaluate_asset_gate_payload(payload, mutate_stage=False)
        return self._mutate("ASSET_GATE_EVALUATED", {}, lambda current: self._evaluate_asset_gate_payload(current, mutate_stage=True))

    def bind_scope(self, scope: dict[str, Any], *, plan_shot_ids: list[str] | None = None) -> dict[str, Any]:
        if not isinstance(scope, dict) or scope.get("kind") != "SHOT_SUBSET":
            raise WorkflowError("SCOPE_INVALID")
        shot_ids = scope.get("shot_ids")
        if not isinstance(shot_ids, list) or not shot_ids or len(set(shot_ids)) != len(shot_ids):
            raise WorkflowError("SCOPE_SHOT_IDS_NON_EMPTY_UNIQUE_REQUIRED")
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            expected = list(plan_shot_ids or payload.get("plan_shot_ids") or [])
            if expected and shot_ids != expected[:len(shot_ids)]:
                raise WorkflowError("SCOPE_MUST_BE_CONTIGUOUS_PREFIX")
            if any(str(item) not in expected for item in shot_ids) if expected else False:
                raise WorkflowError("SCOPE_SHOT_UNKNOWN")
            existing = payload.get("scope")
            if existing and existing != scope:
                raise WorkflowError("SCOPE_RUN_MISMATCH")
            payload["scope"] = dict(scope)
            if plan_shot_ids is not None:
                payload["plan_shot_ids"] = list(plan_shot_ids)
                payload["total_plan_shots"] = len(plan_shot_ids)
            return dict(payload["scope"])
        return self._mutate("SCOPE_BOUND", {"scope": scope, "plan_shot_ids": plan_shot_ids or []}, apply)

    def _scoped_shots(self, payload: dict[str, Any]) -> list[str] | None:
        scope = payload.get("scope")
        if not isinstance(scope, dict):
            return None
        ids = scope.get("shot_ids")
        return [str(item) for item in ids] if isinstance(ids, list) else None

    def _require_active_shot(self, payload: dict[str, Any], shot_id: str) -> None:
        scoped = self._scoped_shots(payload)
        if (
            scoped is None
            or payload.get("mode") != "PRODUCTION"
            or not payload.get("scope_explicit", False)
        ):
            return
        if shot_id not in scoped:
            raise WorkflowError(f"SHOT_OUTSIDE_SCOPE:{shot_id}")
        if shot_id != payload.get("scope", {}).get("active_shot_id"):
            raise WorkflowError(f"SHOT_NOT_ACTIVE:{shot_id}")

    @staticmethod
    def _take_frame_proof(
        payload: dict[str, Any],
        take: dict[str, Any],
        *,
        frame: str | None = None,
        require_verified: bool = True,
    ) -> dict[str, Any]:
        if payload.get("mode") != "PRODUCTION":
            return {}
        if require_verified and take.get("frame_proof_status") != "VERIFIED":
            raise WorkflowError(f"FRAME_PROOF_NOT_VERIFIED:{take.get('take_id')}")
        proof = take.get("frame_proof")
        if not isinstance(proof, dict):
            raise WorkflowError(f"FRAME_PROOF_MISSING:{take.get('take_id')}")
        keys = (frame,) if frame else ("first_frame", "last_frame")
        result: dict[str, Any] = {}
        for key in keys:
            row = proof.get(key)
            if not isinstance(row, dict) or not row.get("path") or not row.get("sha256"):
                raise WorkflowError(f"FRAME_PROOF_MISSING:{take.get('take_id')}:{key}")
            candidate = _contained_path(Path(str(payload.get("root") or "")), str(row["path"]))
            if not candidate.is_file() or sha256_file(candidate) != row.get("sha256"):
                raise WorkflowError(f"FRAME_PROOF_DRIFT:{take.get('take_id')}:{key}")
            if proof.get("artifact_sha256") != take.get("artifact_sha256"):
                raise WorkflowError(f"FRAME_PROOF_LINEAGE_MISMATCH:{take.get('take_id')}")
            if proof.get("generation_id") != take.get("generation_id"):
                raise WorkflowError(f"FRAME_PROOF_LINEAGE_MISMATCH:{take.get('take_id')}")
            if proof.get("admission_request_hash") != take.get("admission_request_hash"):
                raise WorkflowError(f"FRAME_PROOF_LINEAGE_MISMATCH:{take.get('take_id')}")
            result[key] = {"path": str(row["path"]), "sha256": str(row["sha256"])}
        return result

    def _find_take(self, payload: dict[str, Any], take_id: str, shot_id: str | None = None) -> dict[str, Any] | None:
        return next(
            (
                row for row in payload.get("takes", [])
                if row.get("take_id") == take_id
                and (shot_id is None or row.get("shot_id") == shot_id)
            ),
            None,
        )

    def _continuity_file_ready(
        self,
        payload: dict[str, Any],
        edge: dict[str, Any],
        *,
        allow_pending_structure: bool = False,
    ) -> None:
        candidate = _contained_path(self._root(payload), Path(str(edge.get("evidence_path") or "")))
        if not candidate.is_file():
            raise WorkflowError(f"CONTINUITY_EVIDENCE_REQUIRED:{edge.get('from_shot')}->{edge.get('to_shot')}")
        try:
            evidence = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"CONTINUITY_EVIDENCE_INVALID:{edge.get('from_shot')}->{edge.get('to_shot')}") from exc
        if not isinstance(evidence, dict):
            raise WorkflowError(f"CONTINUITY_EVIDENCE_NOT_READY:{edge.get('from_shot')}->{edge.get('to_shot')}")
        ready = (
            _pre_provider_continuity_ready(evidence)
            if allow_pending_structure
            else evidence.get("status") in _FRAME_READY_CONTINUITY_STATUSES
        )
        if not ready:
            raise WorkflowError(f"CONTINUITY_EVIDENCE_NOT_READY:{edge.get('from_shot')}->{edge.get('to_shot')}")
        if str(evidence.get("from_shot")) != str(edge.get("from_shot")) or str(evidence.get("to_shot")) != str(edge.get("to_shot")):
            raise WorkflowError(f"CONTINUITY_EDGE_MISMATCH:{edge.get('edge_id')}")

    def update_continuity_evidence(
        self,
        edge_id: str,
        *,
        previous_take_id: str,
        current_take_id: str,
    ) -> dict[str, Any]:
        """Bind real adjacent take frames to an already verified bridge.

        This method only records evidence that already exists. It never promotes
        a prose bridge by itself and never creates a frame proof.
        """
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            edge = payload.get("continuity", {}).get(edge_id)
            if not isinstance(edge, dict):
                raise WorkflowError(f"CONTINUITY_EDGE_NOT_FOUND:{edge_id}")
            self._continuity_file_ready(payload, edge)
            previous = self._find_take(payload, previous_take_id, str(edge.get("from_shot")))
            current = self._find_take(payload, current_take_id, str(edge.get("to_shot")))
            if not previous or not current:
                raise WorkflowError(f"CONTINUITY_TAKES_REQUIRED:{edge_id}")
            if not previous.get("selected") or previous.get("stale") or current.get("stale"):
                raise WorkflowError(f"CONTINUITY_SELECTED_TAKES_REQUIRED:{edge_id}")
            previous_proof = self._take_frame_proof(payload, previous, frame="last_frame", require_verified=False)
            current_proof = self._take_frame_proof(payload, current, frame="first_frame", require_verified=False)
            previous_request_hash = previous.get("admission_request_hash")
            current_request_hash = current.get("admission_request_hash")
            if not previous_request_hash or not current_request_hash:
                raise WorkflowError(f"CONTINUITY_REQUEST_HASH_REQUIRED:{edge_id}")
            current_admission = next(
                (
                    row for row in reversed(payload.get("generation_admissions", []))
                    if row.get("shot_id") == current.get("shot_id")
                    and not row.get("invalidated")
                    and row.get("request_hash") == current_request_hash
                ),
                None,
            )
            if not current_admission:
                raise WorkflowError(f"CONTINUITY_CURRENT_REQUEST_HASH_MISMATCH:{edge_id}")
            if edge.get("request_hash") and edge.get("request_hash") != previous_request_hash:
                raise WorkflowError(f"CONTINUITY_REQUEST_HASH_MISMATCH:{edge_id}")
            if edge.get("current_request_hash") and edge.get("current_request_hash") != current_request_hash:
                raise WorkflowError(f"CONTINUITY_CURRENT_REQUEST_HASH_MISMATCH:{edge_id}")
            previous["frame_proof_status"] = "VERIFIED"
            current["frame_proof_status"] = "VERIFIED"
            edge.update({
                "previous_take_id": previous_take_id,
                "previous_last_frame": previous_proof["last_frame"],
                "current_take_id": current_take_id,
                "current_first_frame": current_proof["first_frame"],
                "request_hash": previous_request_hash,
                "current_request_hash": current_request_hash,
                "frame_proof_status": "VERIFIED",
                "status": "READY",
                "verified_at": _utc_now(),
            })
            return dict(edge)
        return self._mutate("CONTINUITY_EVIDENCE_VERIFIED", {"edge_id": edge_id, "previous_take_id": previous_take_id, "current_take_id": current_take_id}, apply)

    def verify_frame_proof(self, take_id: str) -> dict[str, Any]:
        """Explicitly promote extracted frame evidence after lineage checks."""
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            take = self._find_take(payload, take_id)
            if not take or take.get("stale"):
                raise WorkflowError(f"TAKE_NOT_FOUND:{take_id}")
            self._take_frame_proof(payload, take, require_verified=False)
            take["frame_proof_status"] = "VERIFIED"
            take["frame_proof_verified_at"] = _utc_now()
            return dict(take)
        return self._mutate("FRAME_PROOF_VERIFIED", {"take_id": take_id}, apply)

    def expand_scope(self, next_shot_id: str) -> dict[str, Any]:
        next_shot_id = str(next_shot_id).strip()
        if not next_shot_id:
            raise WorkflowError("SCOPE_SHOT_REQUIRED")
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            scope = payload.get("scope")
            plan_ids = list(payload.get("plan_shot_ids") or [])
            if payload.get("mode") != "PRODUCTION" or not isinstance(scope, dict) or not plan_ids:
                raise WorkflowError("SCOPED_PRODUCTION_RUN_REQUIRED")
            current_ids = list(scope.get("shot_ids") or [])
            if not current_ids or current_ids != plan_ids[:len(current_ids)]:
                raise WorkflowError("SCOPE_INVALID")
            if len(current_ids) >= len(plan_ids) or next_shot_id != plan_ids[len(current_ids)]:
                raise WorkflowError("SCOPE_MUST_EXPAND_BY_NEXT_PLAN_SHOT")
            active_shot_id = str(scope.get("active_shot_id") or "")
            if active_shot_id != current_ids[-1]:
                raise WorkflowError("SCOPE_EXPANSION_REQUIRES_ACTIVE_SCOPE_TAIL")
            active_state = payload.get("shots", {}).get(active_shot_id, {})
            selected_take_id = active_state.get("selected_take_id")
            selected_take = (
                self._find_take(payload, str(selected_take_id), active_shot_id)
                if selected_take_id
                else None
            )
            if not selected_take or selected_take.get("stale"):
                raise WorkflowError(f"ACTIVE_SHOT_GENERATION_NOT_READY:{active_shot_id}")
            if payload.get("qc", {}).get(selected_take_id, {}).get("status") != "PASS":
                raise WorkflowError(f"ACTIVE_SHOT_QC_NOT_READY:{active_shot_id}")
            updated = dict(scope)
            updated["shot_ids"] = current_ids + [next_shot_id]
            canonical = {"kind": "SHOT_SUBSET", "shot_ids": updated["shot_ids"], "active_shot_id": updated.get("active_shot_id")}
            updated["scope_id"] = _hash_bytes(_canonical(canonical).encode("utf-8"))[:16]
            payload["scope"] = updated
            return dict(updated)
        return self._mutate("SCOPE_EXPANDED", {"next_shot_id": next_shot_id}, apply)

    def advance_active_shot(self, next_shot_id: str) -> dict[str, Any]:
        next_shot_id = str(next_shot_id).strip()
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            scope = payload.get("scope")
            scoped = self._scoped_shots(payload)
            if payload.get("mode") != "PRODUCTION" or not isinstance(scope, dict) or not scoped:
                raise WorkflowError("SCOPED_PRODUCTION_RUN_REQUIRED")
            current = str(scope.get("active_shot_id") or "")
            if current not in scoped or next_shot_id not in scoped:
                raise WorkflowError("ACTIVE_SHOT_SCOPE_INVALID")
            current_index = scoped.index(current)
            next_index = current_index + 1
            if next_index >= len(scoped) or next_shot_id != scoped[next_index]:
                raise WorkflowError("ACTIVE_SHOT_MUST_ADVANCE_TO_NEXT")
            selected_id = payload.get("shots", {}).get(current, {}).get("selected_take_id")
            selected = self._find_take(payload, str(selected_id), current) if selected_id else None
            if not selected or selected.get("stale") or payload.get("qc", {}).get(selected_id, {}).get("status") != "PASS":
                raise WorkflowError(f"ACTIVE_SHOT_QC_NOT_READY:{current}")
            scope["active_shot_id"] = next_shot_id
            return {"active_shot_id": next_shot_id, "scope": dict(scope)}
        return self._mutate("ACTIVE_SHOT_ADVANCED", {"next_shot_id": next_shot_id}, apply)

    def lock_shot(self, shot_id: str, contract: dict[str, Any]) -> dict[str, Any]:
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            scoped = self._scoped_shots(payload)
            if scoped is not None and shot_id not in scoped:
                raise WorkflowError(f"SHOT_OUTSIDE_SCOPE:{shot_id}")
            if payload.get("asset_gate", {}).get("status") != "READY":
                raise WorkflowError("ASSET_GATE_NOT_READY")
            duration = contract.get("duration_seconds") or {}
            if not isinstance(duration, dict) or float(duration.get("min", 0)) <= 0 or float(duration.get("max", 0)) < float(duration.get("min", 0)):
                raise WorkflowError("INVALID_DURATION_CONTRACT")
            actions = contract.get("actions")
            if actions is not None and (not isinstance(actions, list) or len(actions) != 1):
                raise WorkflowError("SHOT_MUST_HAVE_ONE_PRIMARY_ACTION")
            if not str(contract.get("primary_action") or (actions[0] if actions else "")).strip():
                raise WorkflowError("PRIMARY_ACTION_REQUIRED")
            existing = payload["shots"].get(shot_id)
            if existing:
                runtime_fields = {"stale", "selected_take_id"}
                existing_contract = {k: v for k, v in existing.items() if k not in runtime_fields}
                if existing_contract != contract:
                    raise WorkflowError(f"SHOT_CONFLICT:{shot_id}")
                # Asset-gate regression invalidates runtime lineage, but must not
                # make the immutable shot contract impossible to re-lock.
                if existing.get("stale") or payload.get("stage") == "ASSETS_READY":
                    payload["shots"][shot_id] = {**contract, "stale": False, "selected_take_id": None}
            else:
                payload["shots"][shot_id] = contract
            if STAGE_ORDER[payload["stage"]] < STAGE_ORDER["SHOT_LOCKED"]:
                self._advance(payload, "SHOT_LOCKED")
            return {"shot_id": shot_id, "contract": contract}
        return self._mutate("SHOT_LOCKED", {"shot_id": shot_id}, apply)

    def admit_generation(
        self,
        shot_id: str,
        request: dict[str, Any],
        *,
        resume_video_id: str | None = None,
        revision_of: str | None = None,
    ) -> dict[str, Any]:
        """Admit one immutable request, or an explicitly lineage-bound revision.

        A changed request is never a transparent retry.  Callers must name the
        prior request hash they are superseding; the ledger then records a new
        revision and preserves the original admission for audit/reconciliation.
        """
        request_hash = _hash_bytes(_canonical(request).encode("utf-8"))
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            if self._evaluate_asset_gate_payload(payload, mutate_stage=False).get("status") != "READY":
                raise WorkflowError("ASSET_GATE_NOT_READY")
            self._require_active_shot(payload, shot_id)
            if shot_id not in payload["shots"]:
                raise WorkflowError(f"SHOT_NOT_LOCKED:{shot_id}")
            locked_contract = payload["shots"][shot_id]
            if payload.get("mode") == "PRODUCTION":
                if locked_contract.get("generation_allowed") is not True:
                    raise WorkflowError(f"GENERATION_NOT_ALLOWED:{shot_id}")
                if locked_contract.get("rebuild_required") is True:
                    raise WorkflowError(f"SHOT_REBUILD_REQUIRED:{shot_id}")
                gate = locked_contract.get("five_gate_receipt") or locked_contract.get("quality_gate")
                if isinstance(gate, dict) and gate.get("status") not in {"PASS", "READY"}:
                    raise WorkflowError(f"FIVE_GATE_NOT_READY:{shot_id}")
            scoped = self._scoped_shots(payload)
            if (
                payload.get("mode") == "PRODUCTION"
                and payload.get("scope_explicit", False)
                and scoped
            ):
                shot_index = scoped.index(shot_id)
                if shot_index > 0:
                    previous_shot_id = scoped[shot_index - 1]
                    previous_state = payload.get("shots", {}).get(previous_shot_id, {})
                    previous_take_id = previous_state.get("selected_take_id")
                    previous = self._find_take(payload, str(previous_take_id), previous_shot_id) if previous_take_id else None
                    if not previous or previous.get("stale"):
                        raise WorkflowError(f"PREVIOUS_SHOT_GENERATION_REQUIRED:{previous_shot_id}")
                    self._take_frame_proof(payload, previous, frame="last_frame")
                    edge_id = f"{previous_shot_id}->{shot_id}"
                    edge = payload.get("continuity", {}).get(edge_id)
                    if not isinstance(edge, dict):
                        raise WorkflowError(f"CONTINUITY_EVIDENCE_REQUIRED:{edge_id}")
                    self._continuity_file_ready(payload, edge, allow_pending_structure=True)
                    previous_request_hash = next(
                        (
                            row.get("request_hash")
                            for row in reversed(payload.get("generation_admissions", []))
                            if row.get("shot_id") == previous_shot_id and not row.get("invalidated")
                        ),
                        None,
                    )
                    if not previous_request_hash:
                        raise WorkflowError(f"PREVIOUS_SHOT_REQUEST_HASH_REQUIRED:{previous_shot_id}")
                    if edge.get("request_hash") and edge.get("request_hash") != previous_request_hash:
                        raise WorkflowError(f"CONTINUITY_REQUEST_HASH_MISMATCH:{edge_id}")
            prior = [row for row in payload["generation_admissions"] if row.get("shot_id") == shot_id and not row.get("invalidated")]
            if prior:
                if prior[-1].get("request_hash") == request_hash and prior[-1].get("resume_video_id") == resume_video_id:
                    return prior[-1]
                if revision_of != prior[-1].get("request_hash"):
                    raise WorkflowError(f"GENERATION_ALREADY_ADMITTED:{shot_id}")
                prior[-1]["superseded_by_request_hash"] = request_hash
                prior[-1]["superseded_at"] = _utc_now()
            record = {
                "shot_id": shot_id,
                "request_hash": request_hash,
                "request": request,
                "resume_video_id": resume_video_id,
                "revision": len(prior) + 1,
                "supersedes_request_hash": revision_of,
                "admitted_at": _utc_now(),
            }
            payload["generation_admissions"].append(record)
            if STAGE_ORDER[payload["stage"]] < STAGE_ORDER["GENERATION_ADMITTED"]:
                self._advance(payload, "GENERATION_ADMITTED")
            return record
        return self._mutate("GENERATION_ADMITTED", {"shot_id": shot_id, "request_hash": request_hash, "revision_of": revision_of}, apply)

    def record_generation(self, shot_id: str, take_id: str, *, video_id: str, artifact_path: str | Path, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        artifact_path = Path(artifact_path)
        metadata = dict(metadata or {})
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            admission = next((row for row in reversed(payload["generation_admissions"]) if row.get("shot_id") == shot_id and not row.get("invalidated")), None)
            if not admission:
                raise WorkflowError(f"GENERATION_NOT_ADMITTED:{shot_id}")
            if self._evaluate_asset_gate_payload(payload, mutate_stage=False).get("status") != "READY":
                raise WorkflowError("ASSET_GATE_NOT_READY")
            if not str(video_id).strip():
                raise WorkflowError("VIDEO_ID_REQUIRED")
            supplied_request_hash = metadata.get("request_hash")
            if payload.get("mode") == "PRODUCTION" and supplied_request_hash != admission.get("request_hash"):
                raise WorkflowError("GENERATION_REQUEST_HASH_REQUIRED")
            if supplied_request_hash and supplied_request_hash != admission.get("request_hash"):
                raise WorkflowError("GENERATION_REQUEST_HASH_MISMATCH")
            if admission.get("resume_video_id") and admission.get("resume_video_id") != video_id:
                raise WorkflowError("RESUME_VIDEO_ID_MISMATCH")
            if any(row.get("take_id") == take_id for row in payload["takes"]):
                raise WorkflowError(f"TAKE_ALREADY_RECORDED:{take_id}")
            root = self._root(payload)
            try:
                candidate = _contained_path(root, artifact_path)
            except WorkflowError as exc:
                raise WorkflowError("ARTIFACT_PATH_ESCAPE") from exc
            if not candidate.is_file():
                raise WorkflowError(f"ARTIFACT_NOT_FOUND:{artifact_path}")
            actual_hash = sha256_file(candidate)
            probed = _probe_media(candidate) if payload.get("mode") == "PRODUCTION" else None
            if payload.get("mode") == "PRODUCTION" and probed is None:
                raise WorkflowError("MEDIA_PROBE_UNKNOWN")
            if payload.get("mode") == "PRODUCTION" and (not probed.get("duration_seconds") or not probed.get("width") or not probed.get("height")):
                raise WorkflowError("MEDIA_METADATA_INCOMPLETE")
            frame_proof: dict[str, Any] = {}
            frame_proof_status = "PENDING"
            if payload.get("mode") == "PRODUCTION":
                frame_dir = _contained_path(
                    root,
                    Path(".control") / "frames" / str(shot_id) / str(take_id),
                )
                extracted = _extract_frames(candidate, frame_dir)
                frame_proof = {
                    "tool": extracted["tool"],
                    "tool_path": extracted["tool_path"],
                    "tool_version": extracted["tool_version"],
                    "first_frame": {
                        **extracted["first_frame"],
                        "path": str(Path(extracted["first_frame"]["path"]).resolve().relative_to(root)),
                    },
                    "last_frame": {
                        **extracted["last_frame"],
                        "path": str(Path(extracted["last_frame"]["path"]).resolve().relative_to(root)),
                    },
                    "artifact_sha256": actual_hash,
                    "generation_id": video_id,
                    "admission_request_hash": admission.get("request_hash"),
                }
                frame_proof_status = "PENDING"
            record = {
                "shot_id": shot_id,
                "take_id": take_id,
                "video_id": video_id,
                "generation_id": video_id,
                "artifact_path": str(artifact_path),
                "artifact_sha256": actual_hash,
                "admission_request_hash": admission.get("request_hash"),
                "metadata": metadata,
                "probed_media": probed,
                "frame_proof": frame_proof,
                "frame_proof_status": frame_proof_status,
                "status": "GENERATED_PENDING_QC",
                "recorded_at": _utc_now(),
            }
            payload["takes"].append(record)
            for outcome in payload.get("execution_outcomes", []):
                if outcome.get("shot_id") == shot_id and outcome.get("status") in {"UNKNOWN", "FAILED"} and not outcome.get("resolved"):
                    outcome["resolved"] = True
                    outcome["resolved_by_take_id"] = take_id
                    outcome["resolved_at"] = _utc_now()
            if STAGE_ORDER[payload["stage"]] < STAGE_ORDER["GENERATED"]:
                self._advance(payload, "GENERATED")
            return record
        return self._mutate("GENERATION_RECORDED", {"shot_id": shot_id, "take_id": take_id}, apply)

    def record_execution_outcome(self, *, shot_id: str, status: str, manifest_path: str | Path,
                                 manifest_sha256: str, video_id: str | None = None,
                                 action_id: str | None = None, detail: str | None = None) -> dict[str, Any]:
        status = str(status).upper().strip()
        if status not in {"UNKNOWN", "FAILED"}:
            raise WorkflowError(f"INVALID_EXECUTION_OUTCOME:{status}")
        manifest_path = Path(manifest_path)

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            record = {
                "shot_id": str(shot_id),
                "status": status,
                "run_id": str(payload.get("run_id") or ""),
                "manifest_path": str(manifest_path),
                "manifest_sha256": str(manifest_sha256),
                "video_id": str(video_id) if video_id else None,
                "action_id": str(action_id) if action_id else None,
                "detail": str(detail) if detail else None,
                "resolved": False,
                "recorded_at": _utc_now(),
            }
            for existing in payload.setdefault("execution_outcomes", []):
                if all(existing.get(key) == record.get(key) for key in ("shot_id", "status", "manifest_sha256", "video_id", "action_id")):
                    return existing
            payload["execution_outcomes"].append(record)
            return record

        return self._mutate("EXECUTION_OUTCOME_RECORDED", {"shot_id": str(shot_id), "status": status}, apply)

    def assign_execution_owner(self, *, owner: str, action_id: str, executor_kind: str = "external_provider") -> dict[str, Any]:
        """Bind the current external execution window to this run.

        This is coordination metadata only.  It does not call a provider or
        create a second runtime; it makes the responsible executor and action
        identity explicit before a real execution window starts.
        """
        owner = str(owner).strip()
        action_id = str(action_id).strip()
        executor_kind = str(executor_kind).strip() or "external_provider"
        if not owner or not action_id:
            raise WorkflowError("EXECUTION_OWNER_AND_ACTION_REQUIRED")

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            execution = payload.setdefault("execution", {"owner": None, "action_id": None, "executor_kind": None, "handoff_seq": 0})
            current_owner = execution.get("owner")
            current_action = execution.get("action_id")
            if current_owner and current_owner != owner:
                raise WorkflowError("EXECUTION_OWNER_CONFLICT")
            if current_action and current_action != action_id:
                raise WorkflowError("EXECUTION_ACTION_CONFLICT")
            execution.update({"owner": owner, "action_id": action_id, "executor_kind": executor_kind, "assigned_at": _utc_now()})
            return dict(execution)

        return self._mutate("EXECUTION_OWNER_ASSIGNED", {"owner": owner, "action_id": action_id}, apply)

    def handoff_execution(self, *, from_owner: str, to_owner: str, action_id: str, reason: str = "") -> dict[str, Any]:
        """Transfer the same execution action without changing the run id."""
        from_owner = str(from_owner).strip()
        to_owner = str(to_owner).strip()
        action_id = str(action_id).strip()
        if not from_owner or not to_owner or not action_id:
            raise WorkflowError("EXECUTION_HANDOFF_FIELDS_REQUIRED")

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            execution = payload.setdefault("execution", {"owner": None, "action_id": None, "executor_kind": None, "handoff_seq": 0})
            if execution.get("owner") != from_owner or execution.get("action_id") != action_id:
                raise WorkflowError("EXECUTION_HANDOFF_SOURCE_MISMATCH")
            sequence = int(execution.get("handoff_seq") or 0) + 1
            execution.update({"owner": to_owner, "handoff_seq": sequence, "handoff_at": _utc_now(), "handoff_reason": str(reason)})
            return dict(execution)

        return self._mutate("EXECUTION_HANDOFF", {"from_owner": from_owner, "to_owner": to_owner, "action_id": action_id, "reason": str(reason)}, apply)

    def record_qc(self, take_id: str, layers: dict[str, str], *, notes: str = "") -> dict[str, Any]:
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            if self._evaluate_asset_gate_payload(payload, mutate_stage=False).get("status") != "READY":
                raise WorkflowError("ASSET_GATE_NOT_READY")
            if set(layers) != set(QC_LAYERS) or any(layers[k] not in {"PASS", "FAIL", "UNKNOWN"} for k in QC_LAYERS):
                raise WorkflowError("QC_REQUIRES_EXACT_FIVE_LAYERS")
            take = next((row for row in payload["takes"] if row.get("take_id") == take_id), None)
            if not take:
                raise WorkflowError(f"TAKE_NOT_FOUND:{take_id}")
            if take.get("stale"):
                raise WorkflowError(f"STALE_TAKE:{take_id}")
            try:
                take_path = _contained_path(self._root(payload), Path(str(take.get("artifact_path") or "")))
            except WorkflowError as exc:
                raise WorkflowError("ARTIFACT_PATH_ESCAPE") from exc
            if not take_path.is_file() or sha256_file(take_path) != take.get("artifact_sha256"):
                raise WorkflowError(f"ARTIFACT_HASH_DRIFT:{take_id}")
            existing = payload.get("qc", {}).get(take_id)
            if existing and existing.get("layers") != layers:
                raise WorkflowError(f"QC_CONFLICT:{take_id}")
            status = "PASS" if all(layers[k] == "PASS" for k in QC_LAYERS) else "BLOCKED"
            receipt = {"take_id": take_id, "layers": dict(layers), "status": status, "notes": notes, "recorded_at": _utc_now()}
            payload["qc"][take_id] = receipt
            take["status"] = "QC_READY" if status == "PASS" else "QC_BLOCKED"
            target = "QC_READY" if status == "PASS" else "QC_BLOCKED"
            if STAGE_ORDER[payload["stage"]] < STAGE_ORDER[target]:
                self._advance(payload, target)
            return receipt
        return self._mutate("QC_RECORDED", {"take_id": take_id}, apply)

    def select_take(self, shot_id: str, take_id: str) -> dict[str, Any]:
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            if self._evaluate_asset_gate_payload(payload, mutate_stage=False).get("status") != "READY":
                raise WorkflowError("ASSET_GATE_NOT_READY")
            take = next((row for row in payload["takes"] if row.get("take_id") == take_id and row.get("shot_id") == shot_id), None)
            if not take or take.get("stale") or payload.get("qc", {}).get(take_id, {}).get("status") != "PASS":
                raise WorkflowError(f"TAKE_NOT_READY:{shot_id}/{take_id}")
            root = self._root(payload)
            candidate = Path(take["artifact_path"])
            try:
                candidate = _contained_path(root, candidate)
            except WorkflowError as exc:
                raise WorkflowError("ARTIFACT_PATH_ESCAPE") from exc
            if not candidate.is_file() or sha256_file(candidate) != take.get("artifact_sha256"):
                raise WorkflowError(f"ARTIFACT_HASH_DRIFT:{take_id}")
            for row in payload["takes"]:
                if row.get("shot_id") == shot_id:
                    row["selected"] = row.get("take_id") == take_id
            payload["shots"][shot_id]["selected_take_id"] = take_id
            return {"shot_id": shot_id, "take_id": take_id}
        return self._mutate("TAKE_SELECTED", {"shot_id": shot_id, "take_id": take_id}, apply)

    def record_assembly(self, artifact_path: str | Path, *, ordered_shots: list[str], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        artifact_path = Path(artifact_path)
        metadata = dict(metadata or {})
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            if not ordered_shots:
                raise WorkflowError("ASSEMBLY_REQUIRES_SHOTS")
            if len(ordered_shots) != len(set(ordered_shots)):
                raise WorkflowError("ASSEMBLY_DUPLICATE_SHOTS")
            plan_shots = list(payload.get("plan_shot_ids") or [])
            if plan_shots:
                expected_shots = plan_shots
                if list(payload.get("scope", {}).get("shot_ids") or []) != plan_shots:
                    raise WorkflowError("ASSEMBLY_REQUIRES_FULL_PLAN_SCOPE")
            else:
                expected_shots = list(payload.get("shots", {}).keys())
            if ordered_shots != expected_shots:
                raise WorkflowError("ASSEMBLY_SHOT_SET_MISMATCH")
            selected_takes: dict[str, dict[str, str]] = {}
            for shot_id in ordered_shots:
                take_id = payload["shots"].get(shot_id, {}).get("selected_take_id")
                if not take_id or payload.get("qc", {}).get(take_id, {}).get("status") != "PASS":
                    raise WorkflowError(f"ASSEMBLY_SHOT_NOT_READY:{shot_id}")
                take = next((row for row in payload["takes"] if row.get("take_id") == take_id and row.get("shot_id") == shot_id), None)
                if not take or take.get("stale"):
                    raise WorkflowError(f"ASSEMBLY_TAKE_STALE:{shot_id}/{take_id}")
                try:
                    take_path = _contained_path(self._root(payload), Path(str(take.get("artifact_path") or "")))
                except WorkflowError as exc:
                    raise WorkflowError("ARTIFACT_PATH_ESCAPE") from exc
                if not take_path.is_file() or sha256_file(take_path) != take.get("artifact_sha256"):
                    raise WorkflowError(f"ARTIFACT_HASH_DRIFT:{take_id}")
                selected_takes[shot_id] = {"take_id": str(take_id), "artifact_sha256": str(take.get("artifact_sha256"))}
            root = self._root(payload)
            try:
                candidate = _contained_path(root, artifact_path)
            except WorkflowError as exc:
                raise WorkflowError("ASSEMBLY_PATH_ESCAPE") from exc
            if not candidate.is_file():
                raise WorkflowError(f"ASSEMBLY_ARTIFACT_NOT_FOUND:{artifact_path}")
            record = {
                "artifact_path": str(artifact_path),
                "artifact_sha256": sha256_file(candidate),
                "ordered_shots": ordered_shots,
                "selected_takes": selected_takes,
                "plan_shot_ids": list(plan_shots),
                "total_plan_shots": len(plan_shots),
                "metadata": metadata,
                "recorded_at": _utc_now(),
            }
            if payload.get("assembly"):
                if payload["assembly"].get("artifact_sha256") == record["artifact_sha256"] and payload["assembly"].get("ordered_shots") == ordered_shots:
                    return payload["assembly"]
                raise WorkflowError("ASSEMBLY_CONFLICT")
            payload["assembly"] = record
            self._advance(payload, "ASSEMBLED")
            return record
        return self._mutate("ASSEMBLY_RECORDED", {"ordered_shots": ordered_shots}, apply)

    def promote_delivery(self, delivery_path: str | Path | None = None) -> dict[str, Any]:
        delivery_path = Path(delivery_path) if delivery_path else None
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            if not payload.get("assembly"):
                raise WorkflowError("ASSEMBLY_NOT_READY")
            if self._evaluate_asset_gate_payload(payload, mutate_stage=False).get("status") != "READY":
                raise WorkflowError("ASSET_GATE_NOT_READY")
            if any(row.get("status") != "QC_READY" or row.get("stale") for row in payload["takes"] if row.get("selected")):
                raise WorkflowError("SELECTED_TAKE_QC_NOT_READY")
            bound = payload.get("assembly", {}).get("selected_takes")
            if not isinstance(bound, dict):
                raise WorkflowError("ASSEMBLY_SELECTION_BINDING_MISSING")
            for shot_id, expected in bound.items():
                current_take_id = payload.get("shots", {}).get(shot_id, {}).get("selected_take_id")
                if current_take_id != expected.get("take_id"):
                    raise WorkflowError(f"ASSEMBLY_SELECTION_DRIFT:{shot_id}")
                current_take = next((row for row in payload.get("takes", []) if row.get("take_id") == current_take_id and row.get("shot_id") == shot_id), None)
                if not current_take or current_take.get("artifact_sha256") != expected.get("artifact_sha256"):
                    raise WorkflowError(f"ASSEMBLY_SELECTION_HASH_DRIFT:{shot_id}")
            source = delivery_path or Path(payload["assembly"]["artifact_path"])
            root = self._root(payload)
            try:
                candidate = _contained_path(root, source)
            except WorkflowError as exc:
                raise WorkflowError("DELIVERY_PATH_ESCAPE") from exc
            if not candidate.is_file():
                raise WorkflowError(f"DELIVERY_ARTIFACT_NOT_FOUND:{source}")
            current_assembly_hash = sha256_file(candidate)
            if current_assembly_hash != payload["assembly"].get("artifact_sha256"):
                raise WorkflowError("ASSEMBLY_HASH_DRIFT")
            acceptance = payload.get("assembly", {}).get("metadata", {})
            acceptance_path = acceptance.get("acceptance_path")
            acceptance_hash = acceptance.get("acceptance_sha256")
            if acceptance_path and acceptance_hash:
                try:
                    acceptance_candidate = _contained_path(root, acceptance_path)
                except WorkflowError as exc:
                    raise WorkflowError("ACCEPTANCE_PATH_ESCAPE") from exc
                if not acceptance_candidate.is_file() or sha256_file(acceptance_candidate) != acceptance_hash:
                    raise WorkflowError("ACCEPTANCE_RECEIPT_HASH_DRIFT")
            if set(payload.get("shots", {})) != {row.get("shot_id") for row in payload.get("takes", []) if row.get("selected")}:
                raise WorkflowError("ALL_SHOTS_MUST_HAVE_SELECTED_TAKES")
            for row in payload.get("takes", []):
                if not row.get("selected"):
                    continue
                try:
                    take_path = _contained_path(root, Path(str(row.get("artifact_path") or "")))
                except WorkflowError as exc:
                    raise WorkflowError("ARTIFACT_PATH_ESCAPE") from exc
                if not take_path.is_file() or sha256_file(take_path) != row.get("artifact_sha256"):
                    raise WorkflowError(f"ARTIFACT_HASH_DRIFT:{row.get('take_id')}")
            if payload.get("mode") == "PRODUCTION":
                if not acceptance_path or not acceptance_hash:
                    raise WorkflowError("ACCEPTANCE_RECEIPT_REQUIRED")
                try:
                    acceptance_payload = json.loads(acceptance_candidate.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise WorkflowError("ACCEPTANCE_RECEIPT_INVALID") from exc
                if acceptance_payload.get("status") != "PASS" or acceptance_payload.get("delivery_approved") is not True:
                    raise WorkflowError("ACCEPTANCE_NOT_READY")
                lane_statuses = {
                    "pacing": (acceptance_payload.get("pacing") or {}).get("status"),
                    "continuity": (acceptance_payload.get("continuity") or {}).get("status"),
                    "subtitle": acceptance_payload.get("subtitle"),
                    "audio": acceptance_payload.get("audio"),
                    "creative": acceptance_payload.get("creative"),
                }
                if any(value != "PASS" for value in lane_statuses.values()):
                    raise WorkflowError("ACCEPTANCE_LANES_NOT_READY")
                # A lane-level PASS is not enough when the receipt carries
                # per-shot continuity review rows. Every REVIEW_REQUIRED row
                # must have an explicit reviewed outcome before delivery can
                # cross the production boundary.
                continuity = acceptance_payload.get("continuity") or {}
                continuity_rows = continuity.get("shots") or []
                reviews = {
                    (row.get("shot_id"), row.get("status"))
                    for row in (continuity.get("review") or [])
                    if isinstance(row, dict)
                }
                for row in continuity_rows:
                    if (
                        isinstance(row, dict)
                        and row.get("status") == "REVIEW_REQUIRED"
                        and (row.get("shot_id"), "PASS_REVIEWED_NO_INTERNAL_CUTS") not in reviews
                    ):
                        raise WorkflowError("ACCEPTANCE_CONTINUITY_REVIEW_REQUIRED")
                output = acceptance_payload.get("output")
                if not output:
                    raise WorkflowError("ACCEPTANCE_OUTPUT_REQUIRED")
                try:
                    output_candidate = _contained_path(root, str(output))
                except WorkflowError as exc:
                    raise WorkflowError("ACCEPTANCE_OUTPUT_PATH_ESCAPE") from exc
                if not output_candidate.is_file() or sha256_file(output_candidate) != current_assembly_hash:
                    raise WorkflowError("ACCEPTANCE_OUTPUT_HASH_MISMATCH")
                declared_hash = acceptance_payload.get("artifact_sha256") or acceptance_payload.get("output_sha256")
                if not declared_hash or declared_hash != current_assembly_hash:
                    raise WorkflowError("ACCEPTANCE_ARTIFACT_HASH_REQUIRED")
            record = {"artifact_path": str(source), "artifact_sha256": sha256_file(candidate), "status": "READY", "promoted_at": _utc_now()}
            payload["delivery"] = record
            self._advance(payload, "DELIVERY_READY")
            return record
        return self._mutate("DELIVERY_PROMOTED", {"delivery_path": str(delivery_path) if delivery_path else None}, apply)

    def mark_delivered(self, *, destination: str, authorized: bool = False) -> dict[str, Any]:
        if not str(destination).strip():
            raise WorkflowError("DESTINATION_REQUIRED")
        if self.snapshot().get("mode") == "PRODUCTION" and not authorized:
            raise WorkflowError("DELIVERY_AUTHORIZATION_REQUIRED")
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            if payload.get("delivery", {}).get("status") != "READY":
                raise WorkflowError("DELIVERY_NOT_READY")
            if payload.get("mode") == "SANDBOX" and not str(destination).startswith("sandbox://"):
                raise WorkflowError("SANDBOX_REALITY_BOUNDARY")
            payload["delivery"].update({
                "status": "DELIVERED",
                "destination": destination,
                "authorization_confirmed": bool(authorized),
                "delivered_at": _utc_now(),
            })
            self._advance(payload, "DELIVERED")
            return payload["delivery"]
        return self._mutate("DELIVERY_CONFIRMED", {"destination": destination}, apply)

    def close_run(
        self,
        *,
        outcome: str = "DELIVERED_CLOSED",
        closure_id: str | None = None,
        manifest: dict[str, Any] | None = None,
        project_id: str | None = None,
        script_hash: str | None = None,
        contract_hash: str | None = None,
        final_confirmation: dict[str, Any] | None = None,
        final_qc: dict[str, Any] | None = None,
        outputs: list[dict[str, Any]] | None = None,
        rights_receipts: list[dict[str, Any]] | None = None,
        excluded_candidates: list[Any] | None = None,
        known_limits: list[Any] | None = None,
        recovery: dict[str, Any] | str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Close a run with one immutable, evidence-bearing terminal receipt.

        Delivery confirmation answers "may this artifact cross the boundary?";
        closure answers "is this run finished, and what must survive it?".
        The receipt is stored in the existing run state (not a second control
        plane or a pile of sidecar files) and is protected by the same event
        chain/state digest as every other transition.
        """
        supplied = dict(manifest or {})
        outcome = str(supplied.get("outcome") or outcome).upper().strip()
        if outcome not in CLOSURE_OUTCOMES:
            raise WorkflowError(f"INVALID_CLOSURE_OUTCOME:{outcome}")
        closure_id = str(supplied.get("closure_id") or closure_id or f"closure_{uuid.uuid4().hex[:12]}").strip()
        if not closure_id:
            raise WorkflowError("CLOSURE_ID_REQUIRED")

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            if payload.get("closure") is not None:
                raise WorkflowError("RUN_ALREADY_CLOSED")
            delivery = payload.get("delivery") if isinstance(payload.get("delivery"), dict) else {}
            if outcome == "DELIVERED_CLOSED":
                if payload.get("stage") != "DELIVERED" or delivery.get("status") != "DELIVERED":
                    raise WorkflowError("DELIVERY_NOT_CONFIRMED")

            identity = dict(payload.get("identity") or {})
            supplied_identity = supplied.get("identity") if isinstance(supplied.get("identity"), dict) else {}
            identity.update({key: value for key, value in supplied_identity.items() if value is not None})
            identity.update({
                "project_id": project_id or supplied.get("project_id") or identity.get("project_id"),
                "script_hash": script_hash or supplied.get("script_hash") or identity.get("script_hash"),
                "contract_hash": contract_hash or supplied.get("contract_hash") or identity.get("contract_hash"),
            })
            identity = {key: str(value).strip() if value is not None else None for key, value in identity.items()}
            if outcome == "DELIVERED_CLOSED" and any(not identity.get(key) for key in ("project_id", "script_hash", "contract_hash")):
                raise WorkflowError("CLOSURE_IDENTITY_INCOMPLETE")

            expected_shots = list(payload.get("plan_shot_ids") or payload.get("shots", {}).keys())
            selected_rows = [row for row in payload.get("takes", []) if row.get("selected")]
            selected_by_shot = {row.get("shot_id"): row for row in selected_rows}
            unresolved = [
                row for row in payload.get("execution_outcomes", [])
                if row.get("status") in {"UNKNOWN", "FAILED"} and not row.get("resolved")
            ]
            if outcome == "DELIVERED_CLOSED":
                if unresolved:
                    raise WorkflowError("CLOSURE_UNRESOLVED_EXECUTION")
                if set(selected_by_shot) != set(expected_shots):
                    raise WorkflowError("CLOSURE_SHOT_SELECTION_INCOMPLETE")
                for shot_id in expected_shots:
                    row = selected_by_shot.get(shot_id)
                    if not row or row.get("stale") or payload.get("qc", {}).get(row.get("take_id"), {}).get("status") != "PASS":
                        raise WorkflowError(f"CLOSURE_SELECTED_TAKE_NOT_READY:{shot_id}")

            confirmation = supplied.get("final_confirmation")
            if not isinstance(confirmation, dict):
                confirmation = dict(final_confirmation or {})
            else:
                confirmation = dict(confirmation)
            confirmer = str(confirmation.get("confirmed_by") or confirmation.get("approved_by") or "").strip()
            if outcome == "DELIVERED_CLOSED" and not confirmer:
                raise WorkflowError("CLOSURE_FINAL_CONFIRMATION_REQUIRED")
            if confirmer:
                confirmation["confirmed_by"] = confirmer
                confirmation.setdefault("confirmed_at", _utc_now())
                confirmation["confirmed"] = True

            qc = supplied.get("final_qc") if isinstance(supplied.get("final_qc"), dict) else dict(final_qc or {})
            if not qc:
                qc = {
                    "selected_takes": {
                        str(take_id): dict(receipt)
                        for take_id, receipt in (payload.get("qc") or {}).items()
                        if take_id in {row.get("take_id") for row in selected_rows}
                    },
                    "delivery_status": delivery.get("status"),
                }
            serialized_qc = _canonical(qc).upper()
            if outcome == "DELIVERED_CLOSED" and any(token in serialized_qc for token in ("UNKNOWN", "REVIEW_REQUIRED", '"FAIL"', '"BLOCKED"')):
                raise WorkflowError("CLOSURE_QC_NOT_CLEAR")

            closure_outputs = supplied.get("outputs") if isinstance(supplied.get("outputs"), list) else list(outputs or [])
            if outcome == "DELIVERED_CLOSED" and not closure_outputs:
                raise WorkflowError("CLOSURE_OUTPUTS_REQUIRED")
            checked_outputs: list[dict[str, Any]] = []
            root = self._root(payload)
            for item in closure_outputs:
                if not isinstance(item, dict) or not str(item.get("role") or "").strip() or not str(item.get("path") or "").strip():
                    raise WorkflowError("CLOSURE_OUTPUT_REFERENCE_INVALID")
                path = Path(str(item["path"]))
                try:
                    candidate = _contained_path(root, path)
                except WorkflowError as exc:
                    raise WorkflowError("CLOSURE_OUTPUT_PATH_ESCAPE") from exc
                if not candidate.is_file():
                    raise WorkflowError(f"CLOSURE_OUTPUT_NOT_FOUND:{path}")
                actual_hash = sha256_file(candidate)
                declared_hash = str(item.get("sha256") or item.get("artifact_sha256") or "")
                if not declared_hash or declared_hash != actual_hash:
                    raise WorkflowError(f"CLOSURE_OUTPUT_HASH_MISMATCH:{item.get('role')}")
                checked_outputs.append({**item, "path": str(path), "sha256": actual_hash})
            if outcome == "DELIVERED_CLOSED":
                roles = {str(item.get("role") or "").lower() for item in checked_outputs}
                aliases = {
                    "final_master": {"final_master", "master", "video"},
                    "subtitle": {"subtitle", "subtitles", "caption_files", "subtitle_receipt"},
                    "master_audio": {"master_audio", "audio", "audio_files"},
                    "manifest": {"manifest", "version_manifest", "shot_manifest"},
                    "acceptance_receipt": {"acceptance_receipt", "qc_report", "delivery_receipt"},
                }
                missing = [name for name, accepted in aliases.items() if not roles.intersection(accepted)]
                if missing:
                    raise WorkflowError("CLOSURE_OUTPUT_ROLES_MISSING:" + ",".join(missing))

            rights = supplied.get("rights_receipts") if isinstance(supplied.get("rights_receipts"), list) else list(rights_receipts or [])
            if outcome == "DELIVERED_CLOSED" and not rights:
                raise WorkflowError("CLOSURE_RIGHTS_RECEIPTS_REQUIRED")
            checked_rights: list[dict[str, Any]] = []
            for item in rights:
                if not isinstance(item, dict):
                    raise WorkflowError("CLOSURE_RIGHTS_RECEIPT_INVALID")
                right = dict(item)
                if right.get("path"):
                    try:
                        candidate = _contained_path(root, Path(str(right["path"])))
                    except WorkflowError as exc:
                        raise WorkflowError("CLOSURE_RIGHTS_PATH_ESCAPE") from exc
                    if not candidate.is_file():
                        raise WorkflowError(f"CLOSURE_RIGHTS_RECEIPT_NOT_FOUND:{right['path']}")
                    actual_hash = sha256_file(candidate)
                    if str(right.get("sha256") or "") != actual_hash:
                        raise WorkflowError("CLOSURE_RIGHTS_HASH_MISMATCH")
                    right["sha256"] = actual_hash
                checked_rights.append(right)

            close_reason = str(supplied.get("reason") or reason or "").strip()
            if outcome in {"BLOCKED", "PAUSED", "ARCHIVED"} and not close_reason:
                raise WorkflowError("CLOSURE_REASON_REQUIRED")
            known = supplied.get("known_limits") if isinstance(supplied.get("known_limits"), list) else list(known_limits or [])
            recovery_plan = supplied.get("recovery") if supplied.get("recovery") is not None else recovery
            if outcome in {"BLOCKED", "PAUSED"} and not recovery_plan:
                raise WorkflowError("CLOSURE_RECOVERY_REQUIRED")
            excluded = supplied.get("excluded_candidates") if isinstance(supplied.get("excluded_candidates"), list) else list(excluded_candidates or [])
            excluded_ids = {str(item.get("take_id")) for item in payload.get("takes", []) if not item.get("selected") and item.get("take_id")}
            excluded_ids.update(str(item) for item in excluded)

            closure = {
                "schema": _CLOSURE_SCHEMA,
                "closure_id": closure_id,
                "outcome": outcome,
                "run_id": str(payload.get("run_id") or ""),
                "project_id": identity.get("project_id"),
                "script_hash": identity.get("script_hash"),
                "contract_hash": identity.get("contract_hash"),
                "selected_takes": [
                    {
                        "shot_id": row.get("shot_id"),
                        "take_id": row.get("take_id"),
                        "artifact_path": row.get("artifact_path"),
                        "artifact_sha256": row.get("artifact_sha256"),
                    }
                    for row in selected_rows
                ],
                "excluded_candidates": sorted(excluded_ids),
                "qc": qc,
                "rights_receipts": checked_rights,
                "outputs": checked_outputs,
                "final_confirmation": confirmation,
                "known_limits": known,
                "recovery": recovery_plan,
                "reason": close_reason or None,
                "closed_at": _utc_now(),
            }
            closure["closure_hash"] = _hash_bytes(_canonical(closure).encode("utf-8"))
            payload["identity"] = identity
            payload["closure"] = closure
            self._advance(payload, outcome)
            return closure

        return self._mutate(
            "RUN_CLOSED",
            {"closure_id": closure_id, "outcome": outcome},
            apply,
        )

    # Explicit aliases keep callers from inventing a second closure path.
    record_closure = close_run
    close = close_run
