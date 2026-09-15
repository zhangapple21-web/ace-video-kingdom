"""Demand-driven orchestration for the single video production control plane.

This module is intentionally a thin decision layer over :mod:`workflow` and
``ProductionControl``.  It turns a user request (structured or short natural
language) into the next safe local action.  It never treats a provider's
``queued``/``completed`` label as a delivery decision and never crosses the
reality boundary on its own.

The important property is *automatic routing without a second runtime*:
every invocation re-reads the hash-chained run, evaluates the asset gate, and
chooses the next action from the authoritative state.  A blocked gate returns
the missing evidence instead of guessing or submitting work.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import hashlib
import time
from pathlib import Path
from typing import Any

from .engine import ProductionControl, WorkflowError
from .workflow import (
    _read_json,
    bootstrap,
    ingest_execution,
    lock_plan_shots,
    next_action,
    recover,
)
from .media_routing import route_media_demand


GOALS = {"PRODUCE", "RESUME", "STATUS", "AUDIT", "DELIVER"}

# Model routing stays inside this existing demand control plane.  This is a
# capability decision receipt only: it does not call a provider, mutate a
# production run, or promote an unverified model.
CAPABILITY_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "research" / "model_capability_registry.v1.json"
# The ACE watchdog is the existing provider-health authority.  This adapter is
# deliberately read-only: it normalizes its persisted snapshot for the
# capability route and never starts, stops, or refreshes the watchdog.
DEFAULT_WATCHDOG_STATE_PATH = Path(
    os.environ.get(
        "ACE_PROVIDER_WATCHDOG_STATE",
        r"C:\tmp\ace_core\06_RUNTIME\ace\data\miner_pool\provider_watchdog\watchdog_state.json",
    )
)
WATCHDOG_MAX_AGE_SECONDS = 24 * 60 * 60
# A route observation is not capability proof.  Only capability-level
# verification (or a scoped live HTTP proof for the specific capability) may
# satisfy a requirement.
CAPABILITY_EVIDENCE_OK = {"VERIFIED", "VERIFIED_SCOPED", "LIVE_HTTP_200"}


def load_provider_health_snapshot(path: Path | None = None) -> dict[str, Any]:
    """Read and normalize the existing ACE Watchdog snapshot.

    A missing or malformed snapshot is an empty observation, not proof that a
    provider is healthy.  The returned ``_meta`` member is metadata only and
    is ignored when matching model providers.
    """
    state_path = Path(path or DEFAULT_WATCHDOG_STATE_PATH)
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"_meta": {"loaded": False, "source_path": str(state_path)}}
    raw = payload.get("providers") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        return {"_meta": {"loaded": False, "source_path": str(state_path)}}
    status_scores = {"HEALTHY": 100.0, "RECOVERING": 70.0, "DEGRADED": 50.0,
                     "UNHEALTHY": 20.0, "OFFLINE": 0.0}
    updated = payload.get("last_updated") if isinstance(payload, dict) else None
    try:
        snapshot_age = max(0.0, time.time() - float(updated))
    except (TypeError, ValueError):
        snapshot_age = None
    snapshot_stale = snapshot_age is None or snapshot_age > WATCHDOG_MAX_AGE_SECONDS
    normalized: dict[str, Any] = {}
    for provider, row in raw.items():
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "UNKNOWN").upper()
        if snapshot_stale:
            status = "STALE"
        score = row.get("health_score")
        try:
            score = float(score) if score is not None else status_scores.get(status, 50.0)
        except (TypeError, ValueError):
            score = status_scores.get(status, 50.0)
        normalized[str(provider)] = {
            "status": status,
            "health_score": round(max(0.0, min(100.0, score)), 2),
            "last_check": row.get("last_check"),
            "last_success": row.get("last_success"),
            "total_calls": row.get("total_calls", 0),
            "failed_calls": row.get("failed_calls", 0),
        }
    normalized["_meta"] = {
        "loaded": True,
        "source_path": str(state_path.resolve()),
        "last_updated": payload.get("last_updated"),
        "age_seconds": round(snapshot_age, 2) if snapshot_age is not None else None,
        "stale": snapshot_stale,
    }
    return normalized


def _load_capability_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = path or CAPABILITY_REGISTRY_PATH
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"MODEL_CAPABILITY_REGISTRY_INVALID:{registry_path}:{exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        raise WorkflowError(f"MODEL_CAPABILITY_REGISTRY_INVALID:{registry_path}:models_required")
    return payload


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)


def infer_task_requirements(text: str) -> dict[str, Any]:
    """Turn natural language into capability requirements, not model names.

    The classifier is deliberately deterministic for the POC.  A later
    semantic classifier may propose richer requirements, but it must preserve
    this output contract and the fail-closed evidence boundary.
    """
    normalized = str(text or "").strip().lower()
    if not normalized:
        return {
            "task_class": "GENERAL",
            "required_capabilities": ["speed", "cost"],
            "priority": "cost>latency>reliability>quality",
            "signals": [],
        }

    signals: list[str] = []
    capabilities: list[str] = []
    task_class = "GENERAL"
    priority = "quality>reliability>cost>latency"

    if _contains_any(normalized, ("图片", "图像", "截图", "看图", "画面", "视觉", "视频帧", "image", "vision")):
        task_class = "VISION"
        capabilities.extend(["vision", "reliability"])
        priority = "quality>reliability>latency>cost"
        signals.append("vision_input")

    if _contains_any(normalized, ("新项目策划", "复杂制作", "3d预演", "3d 预演", "导演", "分镜", "架构", "结构性风险", "复杂流程", "long chain", "长链")):
        task_class = "DIRECTOR"
        capabilities.extend(["reasoning", "planning", "long_context"])
        priority = "quality>reliability>provider_stability>cost>latency"
        signals.append("complex_planning")
    elif _contains_any(normalized, ("研究", "分析", "比较", "反例", "100 个", "长文", "长上下文", "research")):
        task_class = "RESEARCH"
        capabilities.extend(["reasoning", "long_context"])
        priority = "quality>reliability>cost>latency"
        signals.append("long_context_research")

    if _contains_any(normalized, ("代码", "编程", "修复 bug", "debug", "coding", "code review")):
        task_class = "CODING"
        capabilities.extend(["coding", "reasoning"])
        priority = "quality>reliability>latency>cost"
        signals.append("code_task")

    if _contains_any(normalized, ("批量整理", "清洗", "归档", "字幕", "清单", "格式化", "哈希", "整理文件", "batch", "format")):
        task_class = "UTILITY"
        capabilities.extend(["speed", "cost"])
        priority = "cost>latency>reliability>quality"
        signals.append("utility_task")

    # Preserve order while removing duplicate capabilities from overlapping
    # signals such as “看图并分析风险”.
    capabilities = list(dict.fromkeys(capabilities or ["speed", "cost"]))
    return {
        "task_class": task_class,
        "required_capabilities": capabilities,
        "priority": priority,
        "signals": signals,
    }


def _priority_weights(priority: str) -> dict[str, float]:
    names = [part.strip() for part in str(priority or "").split(">") if part.strip()]
    base = [0.40, 0.28, 0.17, 0.10, 0.05]
    return {name: base[index] for index, name in enumerate(names[: len(base)])}


def _model_capability_state(model: dict[str, Any], capability: str) -> str:
    states = model.get("capability_states")
    if not isinstance(states, dict):
        return "NOT_PROVEN"
    return str(states.get(capability, "NOT_PROVEN")).upper()


def _scope_allowed(scopes: Any, requested_scope: str) -> bool:
    """Match explicit scopes or the bounded autonomous research scope."""
    if not isinstance(scopes, list):
        return False
    if requested_scope in scopes:
        return True
    if requested_scope in {"auto", "autonomous", "auto_research"}:
        return any(scope in scopes for scope in (
            "auto", "current_control_plane", "remote_shenwen", "ace_provider"
        ))
    return False


def _canonical_model_override(value: str | None, text: str = "") -> tuple[str | None, str | None]:
    requested = str(value or "").strip()
    if not requested:
        match = re.search(r"(?:用|指定|强制(?:使用)?|use)\s*(?:模型\s*)?(astra|gpt-6-astra)", str(text or "").lower())
        requested = match.group(1) if match else ""
    if not requested:
        return None, None
    aliases = {
        "astra": "shenwen:gpt-6-astra",
        "gpt-6-astra": "shenwen:gpt-6-astra",
    }
    return aliases.get(requested.lower(), requested), requested


def route_model_demand(
    text: str,
    *,
    scope: str = "current_control_plane",
    model_override: str | None = None,
    registry_path: Path | None = None,
    health_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve ``natural language -> capabilities -> labor`` without calling it.

    A route is usable only when every required capability has evidence in the
    registry and the labor is eligible for the requested execution scope.
    Unknown, remote-only, or unproven candidates stay visible as evidence but
    cannot silently become a route.
    """
    media_route = route_media_demand(text, scope=scope)
    if media_route is not None:
        return media_route
    requirements = infer_task_requirements(text)
    registry = _load_capability_registry(registry_path)
    canonical_override, requested_override = _canonical_model_override(model_override, text)
    if health_snapshot is None:
        health_snapshot = load_provider_health_snapshot()
    snapshot_meta = (health_snapshot or {}).get("_meta") if isinstance(health_snapshot, dict) else {}
    health_action = "NONE"
    if isinstance(snapshot_meta, dict) and snapshot_meta.get("stale") is True:
        health_action = "REFRESH_WATCHDOG_THEN_RETRY"
    models = [row for row in registry.get("models", []) if isinstance(row, dict)]
    weights = _priority_weights(requirements["priority"])
    required = requirements["required_capabilities"]
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for model in models:
        model_id = str(model.get("id") or "")
        reasons: list[str] = []
        scopes = model.get("eligible_scopes")
        if not model_id:
            continue
        if not _scope_allowed(scopes, scope):
            reasons.append("SCOPE_NOT_ELIGIBLE")
        # A research model may execute through a verified local gateway even
        # when its direct upstream credential is stale.  Keep the model's
        # provider identity for routing receipts, but allow an explicit
        # health_provider alias to supply the live transport evidence.
        health_provider = str(model.get("health_provider") or model.get("provider") or "")
        provider_health = (health_snapshot or {}).get(health_provider)
        snapshot_meta = (health_snapshot or {}).get("_meta")
        if (
            isinstance(snapshot_meta, dict)
            and snapshot_meta.get("stale") is True
            and (str(model.get("provider") or "") == "shenwen" or "remote_shenwen" in (scopes or []))
        ):
            reasons.append("PROVIDER_UNHEALTHY")
            reasons.append("PROVIDER_HEALTH_SNAPSHOT_STALE")
        if isinstance(provider_health, dict):
            health_status = str(provider_health.get("status") or "").upper()
            if health_status in {"OFFLINE", "DOWN", "UNHEALTHY", "STALE", "UNKNOWN"}:
                reasons.append("PROVIDER_UNHEALTHY")
                if health_action == "NONE":
                    health_action = "REFRESH_WATCHDOG_THEN_RETRY"
        missing = [cap for cap in required if _model_capability_state(model, cap) not in CAPABILITY_EVIDENCE_OK]
        if missing:
            reasons.append("CAPABILITY_NOT_PROVEN:" + ",".join(missing))
        limits = model.get("verification_limits") if isinstance(model.get("verification_limits"), dict) else {}
        max_chars = limits.get("max_input_chars")
        if max_chars is not None:
            try:
                if len(str(text or "")) > int(max_chars):
                    reasons.append(f"CONTEXT_EXCEEDS_VERIFIED_LIMIT:{int(max_chars)}")
            except (TypeError, ValueError):
                reasons.append("VERIFICATION_LIMIT_INVALID")
        if reasons:
            blocked.append({
                "id": model_id,
                "provider": model.get("provider"),
                "health_provider": health_provider,
                "reasons": reasons,
                "recovery_action": health_action if any(reason.startswith("PROVIDER_") for reason in reasons) else "REVIEW_CAPABILITY_EVIDENCE",
                "capability_states": {cap: _model_capability_state(model, cap) for cap in required},
            })
            continue

        metrics = model.get("metrics") if isinstance(model.get("metrics"), dict) else {}
        score = sum(weights.get(name, 0.0) * float(metrics.get(name, 0.0) or 0.0) for name in weights)
        if isinstance(provider_health, dict) and provider_health.get("health_score") is not None:
            try:
                score *= max(0.0, min(1.0, float(provider_health["health_score"]) / 100.0))
            except (TypeError, ValueError):
                pass
        candidates.append({
            "id": model_id,
            "provider": model.get("provider"),
            "health_provider": health_provider,
            "model": model.get("model"),
            "status": model.get("status"),
            "execution_profile": model.get("execution_profile"),
            "score": round(score, 6),
            "capability_states": {cap: _model_capability_state(model, cap) for cap in required},
            "evidence": model.get("evidence", []),
        })

    candidates.sort(key=lambda row: (-row["score"], str(row["id"])))
    selected: dict[str, Any] | None = None
    status = "ROUTED"
    reason = "CAPABILITY_MATCH"

    if canonical_override:
        override = canonical_override.lower()
        requested_name = str(requested_override or "").lower()
        selected = next(
            (row for row in candidates if str(row["id"]).lower() == override or str(row.get("model") or "").lower() in {override, requested_name}),
            None,
        )
        if selected is None:
            status = "BLOCKED"
            reason = "MODEL_OVERRIDE_UNAVAILABLE_OR_UNPROVEN"
        else:
            reason = "EXPLICIT_MODEL_OVERRIDE"
    elif candidates:
        selected = candidates[0]
    else:
        status = "BLOCKED"
        reason = "NO_ELIGIBLE_LABOR_FOR_VERIFIED_CAPABILITIES"

    return {
        "schema": "ace.video_kingdom.model_capability_route_receipt.v1",
        "status": status,
        "scope": scope,
        "input_text": str(text or ""),
        "task_class": requirements["task_class"],
        "required_capabilities": required,
        "priority": requirements["priority"],
        "signals": requirements["signals"],
        "selected_labor": selected,
        "candidate_set": candidates,
        "blocked_candidates": blocked,
        "fallback_policy": "retry_next_scored_candidate_after_execution_failure; never promote unproven capability",
        "health_snapshot": health_snapshot or {},
        "health_action": health_action,
        "reason": reason,
        "model_override": requested_override,
        "production_integration": False,
    }


def select_fallback_labor(receipt: dict[str, Any], attempted_ids: list[str] | tuple[str, ...] = ()) -> dict[str, Any] | None:
    """Return the next already-eligible labor candidate after a failed call.

    This is a pure selector.  It never retries a provider, mutates the route,
    or promotes an unproven capability; callers must write the execution and
    failure receipt before asking for the next candidate.
    """
    attempted = {str(item) for item in attempted_ids}
    candidates = receipt.get("candidate_set") if isinstance(receipt, dict) else None
    if not isinstance(candidates, list):
        return None
    for candidate in candidates:
        if isinstance(candidate, dict) and str(candidate.get("id") or "") not in attempted:
            return candidate
    return None


def _load_request(value: dict[str, Any] | Path | str) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    path = Path(value)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"REQUEST_INVALID:{path}:{exc}") from exc
    if not isinstance(payload, dict):
        raise WorkflowError("REQUEST_MUST_BE_OBJECT")
    return payload


def infer_goal(*, text: str = "", explicit: str | None = None) -> str:
    """Infer only the workflow class; never infer permission to deliver."""
    if explicit:
        goal = str(explicit).upper().strip()
        if goal not in GOALS:
            raise WorkflowError(f"UNKNOWN_GOAL:{explicit}")
        return goal
    normalized = str(text or "").lower()
    if re.search(r"继续|恢复|断点|重开|resume|recover", normalized):
        return "RESUME"
    if re.search(r"状态|进展|现在到哪|检查|审计|验收|qc|audit|status", normalized):
        return "AUDIT"
    if re.search(r"交付|发布|导出|上线|deliver|release", normalized):
        return "DELIVER"
    return "PRODUCE"


def normalize_request(request: dict[str, Any]) -> dict[str, Any]:
    text = str(request.get("text") or request.get("idea") or request.get("prompt") or "")
    goal = infer_goal(text=text, explicit=request.get("goal"))
    result = dict(request)
    result["goal"] = goal
    result["text"] = text
    return result


def _plan_requests(plan: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Extract immutable per-shot generation requests without inventing them."""
    rows: list[tuple[str, dict[str, Any]]] = []
    for shot in plan.get("shots", []) if isinstance(plan.get("shots"), list) else []:
        if not isinstance(shot, dict):
            continue
        shot_id = str(shot.get("shot_id") or "")
        request = shot.get("generation_request")
        if shot_id and isinstance(request, dict) and request:
            rows.append((shot_id, dict(request)))
    return rows


def _discover_latest_run(root: Path) -> tuple[Path, Path | None, Path | None] | None:
    """Find the newest valid local run without requiring a path from the user.

    Discovery is deliberately bounded to the current workspace and its
    ``episodes/generated`` directory.  It only reads candidate ledgers; it
    never creates, resumes, submits, or mutates a run by itself.
    """
    candidates: list[Path] = []
    direct = root / ".control" / "production_run.json"
    if direct.is_file():
        candidates.append(direct)
    generated = root / "episodes" / "generated"
    if generated.is_dir():
        candidates.extend(generated.glob("*/.control/production_run.json"))
    valid: list[tuple[float, Path, dict[str, Any]]] = []
    for candidate in candidates:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or payload.get("schema") != "video_kingdom.production_control_run.v1":
            continue
        valid.append((candidate.stat().st_mtime, candidate, payload))
    if not valid:
        return None
    # Prefer a non-terminal run, then the newest ledger.  A terminal run is
    # still a valid audit target when it is the only local run.
    valid.sort(key=lambda item: (item[2].get("stage") in {"DELIVERED", "FAILED"}, -item[0]))
    run_path = valid[0][1].resolve()
    candidate_project = run_path.parent.parent.resolve()
    # A run directory is not automatically an execution receipt directory.
    # Only expose it for ingestion when the manifest is already present;
    # otherwise RESUME must stop at the explicit external-execution boundary.
    project_dir = candidate_project if (candidate_project / "manifest.json").is_file() else None
    plan_path = candidate_project / "episode_plan.json"
    return run_path, project_dir, plan_path if plan_path.is_file() else None


def _compile_idea_locally(request: dict[str, Any], *, root: Path) -> tuple[Path, Path, dict[str, Any]]:
    """Compile a plain idea through the existing plan compiler, offline.

    This is deliberately ``--plan-only``.  It lets the control plane respond
    to a user request without requiring the user to know the internal CLI,
    while keeping provider submission behind the asset and generation gates.
    """
    idea = str(request.get("idea") or request.get("text") or "").strip()
    if not idea:
        raise WorkflowError("PLAN_REQUIRED")
    repo_root = Path(__file__).resolve().parents[1]
    output_root = Path(str(request.get("output_root") or (repo_root / "episodes" / "generated")))
    if not output_root.is_absolute():
        output_root = (root / output_root).resolve()
    project_id = str(request.get("project_id") or "idea_" + hashlib.sha256(idea.encode("utf-8")).hexdigest()[:12])
    project_dir = (output_root / project_id).resolve()
    command = [sys.executable, str(repo_root / "tools" / "run_idea_pipeline.py"), "--idea", idea,
               "--project-id", project_id, "--output-root", str(output_root), "--plan-only"]
    if project_dir.exists():
        command.append("--resume")
    if request.get("target_seconds") is not None:
        command.extend(["--target-seconds", str(request["target_seconds"])])
    try:
        completed = subprocess.run(command, cwd=repo_root, capture_output=True, text=True, check=False, timeout=900)
    except subprocess.TimeoutExpired as exc:
        raise WorkflowError("PLAN_COMPILE_TIMEOUT") from exc
    plan_path = project_dir / "episode_plan.json"
    # The compiler may return non-zero after producing a valid plan when its
    # own asset/provider gate is blocked.  That is useful evidence for this
    # control plane, not a failed compilation.  Only a missing plan is a hard
    # compile failure.
    if not plan_path.is_file():
        detail = (completed.stderr or completed.stdout or "plan compiler failed").strip()[-1200:]
        raise WorkflowError(f"PLAN_COMPILE_FAILED:{detail}")
    return plan_path, project_dir, {
        "returncode": completed.returncode,
        "stdout_tail": (completed.stdout or "").strip()[-1200:],
        "stderr_tail": (completed.stderr or "").strip()[-1200:],
    }


def _result(*, status: str, goal: str, run: Path | None, snapshot: dict[str, Any] | None = None,
            actions: list[str] | None = None, reason: str | None = None,
            external_action: str | None = None) -> dict[str, Any]:
    snap = snapshot or {}
    payload: dict[str, Any] = {
        "schema": "video_kingdom.demand_route_receipt.v1",
        "status": status,
        "goal": goal,
        "run": str(run.resolve()) if run else None,
        "stage": snap.get("stage"),
        "asset_gate": snap.get("asset_gate"),
        "actions_taken": list(actions or []),
        "next_action": next_action(snap) if snap else reason or "provide plan or run",
        "external_action_required": external_action,
    }
    if reason:
        payload["reason"] = reason
    return payload


def _status_for_snapshot(snapshot: dict[str, Any]) -> str:
    """Expose workflow stage as the status; only delivery-ready is READY."""
    gate = snapshot.get("asset_gate") or {}
    if gate.get("status") != "READY":
        return "BLOCKED"
    stage = snapshot.get("stage") or "UNKNOWN"
    return "READY" if stage == "DELIVERY_READY" else str(stage)


def route(request: dict[str, Any] | Path | str, *, root: Path | None = None) -> dict[str, Any]:
    """Route one demand through the current production state.

    Safe local transitions happen automatically.  Provider execution is
    represented as an explicit next action and is never repeated implicitly;
    an existing project directory may be ingested when the caller supplies it.
    """
    req = normalize_request(_load_request(request))
    goal = req["goal"]
    root = (root or Path.cwd()).resolve()
    raw_plan = str(req.get("plan") or "").strip()
    plan_path = Path(raw_plan) if raw_plan else None
    if plan_path is not None and not plan_path.is_absolute():
        plan_path = (root / plan_path).resolve()
    raw_run = str(req.get("run") or "").strip()
    run_path = Path(raw_run) if raw_run else None
    if run_path is not None and not run_path.is_absolute():
        run_path = (root / run_path).resolve()
    raw_project = str(req.get("project_dir") or "").strip()
    project_dir = Path(raw_project) if raw_project else None
    if project_dir is not None and not project_dir.is_absolute():
        project_dir = (root / project_dir).resolve()

    actions: list[str] = []
    compile_detail: dict[str, Any] | None = None

    def finish(result: dict[str, Any]) -> dict[str, Any]:
        if compile_detail is not None:
            result["plan"] = str(plan_path) if plan_path else None
            result["project_dir"] = str(project_dir) if project_dir else None
            result["compile"] = compile_detail
        return result

    if plan_path is None and req.get("idea") and goal == "PRODUCE":
        try:
            plan_path, compiled_project, compile_detail = _compile_idea_locally(req, root=root)
            project_dir = project_dir or compiled_project
            actions.append("compile_plan")
        except (WorkflowError, OSError) as exc:
            return finish(_result(status="BLOCKED", goal=goal, run=run_path, actions=actions, reason=str(exc)))

    if not run_path:
        discovered = _discover_latest_run(root)
        if discovered is not None and goal in {"STATUS", "AUDIT", "RESUME", "DELIVER"}:
            run_path, discovered_project, discovered_plan = discovered
            project_dir = project_dir or discovered_project
            plan_path = plan_path or discovered_plan
            actions.append("discover_latest_run")
    if not run_path:
        if goal in {"STATUS", "AUDIT", "RESUME", "DELIVER"}:
            return finish(_result(status="BLOCKED", goal=goal, run=None, reason="RUN_REQUIRED"))
        if plan_path is None or not plan_path.is_file():
            return finish(_result(status="BLOCKED", goal=goal, run=None, reason="PLAN_REQUIRED"))
        run_path = (plan_path.parent / ".control" / "production_run.json").resolve()

    if not run_path.exists():
        if goal not in {"PRODUCE", "RESUME"} or plan_path is None or not plan_path.is_file():
            return finish(_result(status="BLOCKED", goal=goal, run=run_path, reason="RUN_NOT_FOUND"))
        boot = bootstrap(plan_path, run_path, mode=str(req.get("mode") or "PRODUCTION").upper())
        actions.append("bootstrap")
        if boot.get("status") == "BLOCKED":
            snapshot = {
                "stage": boot.get("stage", "ASSETS_BLOCKED"),
                "asset_gate": boot.get("asset_gate"),
            }
            result = _result(status="BLOCKED", goal=goal, run=None, snapshot=snapshot, actions=actions, reason="ASSET_GATE_BLOCKED")
            if boot.get("preflight_receipt"):
                result["preflight_receipt"] = boot["preflight_receipt"]
            return finish(result)

    chain = recover(run_path)
    if chain.get("status") == "BLOCKED":
        return finish(_result(status="BLOCKED", goal=goal, run=run_path, reason="EVENT_CHAIN_INVALID"))
    run = ProductionControl(run_path)
    snapshot = run.snapshot()

    if snapshot.get("stage") in {"DELIVERED", "FAILED"}:
        if goal in {"STATUS", "AUDIT"}:
            gate = run.evaluate_asset_gate(persist=False)
            actions.append("evaluate_asset_gate")
            snapshot = {**run.snapshot(), "asset_gate": gate}
            return finish(_result(status=snapshot.get("stage", "UNKNOWN"), goal=goal, run=run_path, snapshot=snapshot, actions=actions,
                                  reason=None if snapshot.get("stage") == "DELIVERED" else "RUN_TERMINAL"))
        return finish(_result(status=snapshot.get("stage", "UNKNOWN"), goal=goal, run=run_path, snapshot=snapshot, actions=actions, reason="RUN_TERMINAL"))

    if goal in {"STATUS", "AUDIT"}:
        gate = run.evaluate_asset_gate(persist=False)
        actions.append("evaluate_asset_gate")
        snapshot = {**run.snapshot(), "asset_gate": gate}
        status = _status_for_snapshot(snapshot)
        return finish(_result(status=status, goal=goal, run=run_path, snapshot=snapshot, actions=actions,
                              reason=None if status not in {"BLOCKED", "UNKNOWN"} else "ASSET_GATE_BLOCKED"))

    # Re-evaluate on every mutating route.  This catches hash drift before any
    # lock, admission, ingest, assembly, or delivery transition.
    gate = run.evaluate_asset_gate()
    actions.append("evaluate_asset_gate")
    snapshot = run.snapshot()

    if gate.get("status") != "READY":
        result = _result(status="BLOCKED", goal=goal, run=run_path, snapshot=snapshot, actions=actions, reason="ASSET_GATE_BLOCKED")
        return finish(result)

    if snapshot.get("stage") == "ASSETS_READY":
        if plan_path is None or not plan_path.is_file():
            return finish(_result(status="BLOCKED", goal=goal, run=run_path, snapshot=snapshot, actions=actions, reason="PLAN_REQUIRED_FOR_SHOT_LOCK"))
        lock_plan_shots(run_path, plan_path)
        actions.append("lock_plan_shots")
        snapshot = run.snapshot()

    if snapshot.get("stage") in {"SHOT_LOCKED", "GENERATION_ADMITTED", "GENERATED", "QC_BLOCKED", "QC_READY", "ASSEMBLED"}:
        # A resumed run already contains immutable shot contracts and may have
        # existing admissions.  It must not require the original plan just to
        # continue polling or ingesting receipts.
        if plan_path is not None and plan_path.is_file():
            plan = _read_json(plan_path)
            requests = _plan_requests(plan)
            if not requests:
                return finish(_result(status="BLOCKED", goal=goal, run=run_path, snapshot=snapshot, actions=actions, reason="GENERATION_REQUESTS_MISSING"))
            locked = set(snapshot.get("shots", {}))
            admitted = {row.get("shot_id") for row in snapshot.get("generation_admissions", []) if not row.get("invalidated")}
            for shot_id, request in requests:
                if shot_id in locked:
                    if shot_id not in admitted:
                        run.admit_generation(shot_id, request, resume_video_id=(request.get("resume_video_id") if isinstance(request, dict) else None))
                        actions.append(f"admit:{shot_id}")
            snapshot = run.snapshot()
        elif not snapshot.get("generation_admissions") or set(snapshot.get("shots", {})) - {
            row.get("shot_id") for row in snapshot.get("generation_admissions", []) if not row.get("invalidated")
        }:
            return finish(_result(status="BLOCKED", goal=goal, run=run_path, snapshot=snapshot, actions=actions, reason="PLAN_REQUIRED_FOR_ADMISSION"))

    unresolved = [row for row in snapshot.get("execution_outcomes", []) if row.get("status") in {"UNKNOWN", "FAILED"} and not row.get("resolved")]
    if unresolved and not (project_dir is not None and project_dir.is_dir()):
        return finish(_result(status="BLOCKED", goal=goal, run=run_path, snapshot=snapshot, actions=actions,
                              reason="EXECUTION_OUTCOME_UNRESOLVED"))

    if project_dir is not None and project_dir.is_dir() and snapshot.get("stage") in {"GENERATION_ADMITTED", "GENERATED", "QC_BLOCKED", "QC_READY", "ASSEMBLED"}:
        ingest_execution(run_path, project_dir)
        actions.append("ingest_execution")
        snapshot = run.snapshot()
        unresolved = [row for row in snapshot.get("execution_outcomes", []) if row.get("status") in {"UNKNOWN", "FAILED"} and not row.get("resolved")]
        if unresolved:
            return finish(_result(status="BLOCKED", goal=goal, run=run_path, snapshot=snapshot, actions=actions,
                                  reason="EXECUTION_OUTCOME_UNRESOLVED"))
    elif snapshot.get("stage") in {"GENERATION_ADMITTED", "GENERATED", "QC_BLOCKED"}:
        return finish(_result(status="READY_FOR_EXECUTION", goal=goal, run=run_path, snapshot=snapshot, actions=actions,
                              external_action="assign an executor owner/action_id on this run; execute admitted shot requests once; write manifest and acceptance receipts with this run_id; then provide project_dir for receipt ingestion"))

    if goal == "DELIVER" and snapshot.get("stage") == "ASSEMBLED":
        run.promote_delivery()
        actions.append("promote_delivery")
        snapshot = run.snapshot()
    if snapshot.get("stage") == "DELIVERY_READY":
        return finish(_result(status="READY", goal=goal, run=run_path, snapshot=snapshot, actions=actions,
                              external_action="authorized destination confirmation required"))
    return finish(_result(status=snapshot.get("stage", "UNKNOWN"), goal=goal, run=run_path, snapshot=snapshot, actions=actions))
