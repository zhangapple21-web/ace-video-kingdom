"""Unified deterministic routing for image/video generation capabilities."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Mapping

from .project import discover_project
from .semantic_context import build_semantic_context


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "research" / "capability_registry.v2.json"
GENERATION_RE = re.compile(r"(生成|绘制|画一张|画个|画出|出图|生图|制作|渲染|generate|create|render)", re.I)
IMAGE_RE = re.compile(r"(图片|图像|角色包|角色设定|参考图|分镜图|关键帧|image|illustration)", re.I)
VIDEO_RE = re.compile(r"(视频|镜头|第\s*\d+\s*镜|短片|video|clip)", re.I)
COMPOSITION_STILL_RE = re.compile(r"(首帧|关键帧|构图锁定|构图参考|复杂走位|多人空间|first[- ]?frame|keyframe|composition)", re.I)


def choose_image_strategy(text: str) -> dict[str, Any]:
    """Escalate to a reviewed composition still only when risk warrants it."""
    source = str(text or "").strip()
    if COMPOSITION_STILL_RE.search(source):
        return {"mode": "COMPOSITION_STILL_CANDIDATE", "reason": "explicit composition/keyframe risk", "requires_review": True}
    return {"mode": "REFERENCE_ONLY", "reason": "identity and shot state are sufficient by default", "requires_review": False}


def build_image_model_plan(route: Mapping[str, Any]) -> dict[str, Any]:
    """Build an explicit, evidence-backed image fallback plan.

    This is a plan recorded in the entry receipt, not a silent provider switch.
    Only variants with PROBE_PASS can be selected for a composition still.
    """
    selected = route.get("selected_routes") or []
    image_route = next((item for item in selected if item.get("capability") == "image.generate"), None)
    if not isinstance(image_route, Mapping):
        return {"status": "UNAVAILABLE", "candidates": [], "reason": "image route is not registered"}
    candidates = []
    primary = str(image_route.get("model") or "").strip()
    if primary and str((image_route.get("health") or {}).get("status")) == "PROBE_PASS":
        candidates.append({"model": primary, "role": "primary", "status": "PROBE_PASS"})
    for variant in image_route.get("available_variants") or []:
        if str(variant.get("status")) == "PROBE_PASS":
            candidates.append({"model": str(variant.get("model")), "role": "fallback", "status": "PROBE_PASS"})
    return {
        "status": "READY" if candidates and image_route.get("status") == "ROUTED" else "BLOCKED",
        "candidates": candidates,
        "selection_policy": "primary_then_verified_variant; explicit_receipt_required",
        "blocked_variants": [
            str(item.get("model")) for item in image_route.get("available_variants") or []
            if str(item.get("status")) != "PROBE_PASS"
        ],
    }


def _registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "ace.capability-registry.v2":
        raise ValueError("CAPABILITY_REGISTRY_SCHEMA_INVALID")
    return data


def classify_media_intent(text: str) -> str | None:
    value = str(text or "").strip()
    if not GENERATION_RE.search(value):
        return None
    image = bool(IMAGE_RE.search(value))
    video = bool(VIDEO_RE.search(value))
    if image and video:
        return "MIXED"
    if image:
        return "IMAGE"
    if video:
        return "VIDEO"
    return None


def _find_executable(row: Mapping[str, Any]) -> str | None:
    for raw in [row.get("executable"), *(row.get("executable_candidates") or [])]:
        path = Path(str(raw))
        if path.is_file():
            return str(path.resolve())
    return None


def _route_one(row: Mapping[str, Any], scope: str, env: Mapping[str, str]) -> dict[str, Any]:
    executable = _find_executable(row)
    credential = str(row.get("credential_env") or "")
    credential_envs = [credential, *(str(item) for item in (row.get("credential_env_aliases") or []))]
    credential_envs = [item for index, item in enumerate(credential_envs) if item and item not in credential_envs[:index]]
    reasons: list[str] = []
    if scope not in set(row.get("eligible_scopes") or []):
        reasons.append("SCOPE_NOT_ELIGIBLE")
    if row.get("production_eligible") is not True:
        reasons.append("PRODUCTION_NOT_ELIGIBLE")
    if not executable:
        reasons.append("EXECUTABLE_NOT_FOUND")
    if credential_envs and not any(str(env.get(name) or "").strip() for name in credential_envs):
        reasons.append("CREDENTIAL_MISSING")
    status = "ROUTED" if not reasons else "BLOCKED"
    return {
        "capability": row["id"],
        "provider": row["provider"],
        "model": row["model"],
        "available_variants": [
            {
                "model": str(variant.get("model")),
                "status": str(variant.get("status") or "UNKNOWN"),
                "selection": str(variant.get("selection") or "explicit_only"),
                "health_evidence": variant.get("health_evidence"),
            }
            for variant in (row.get("model_variants") or [])
            if isinstance(variant, Mapping) and variant.get("model")
        ],
        "model_locked": bool(row.get("model_locked")),
        "executable": executable or str(row.get("executable")),
        "credential_env": credential,
        "credential_envs": credential_envs,
        "status": status,
        "reasons": reasons,
        "receipt_schema": row.get("receipt_schema"),
        "health": row.get("health") or {"status": "UNKNOWN", "production_integration": "UNKNOWN"},
        "health_evidence": row.get("health_evidence"),
        "production_eligible": bool(row.get("production_eligible")),
        "retired_model_policy": row.get("retired_model_policy") or "historical_receipts_only",
        "retired_models": list(row.get("retired_models") or []),
    }


def route_media_demand(
    text: str,
    *,
    scope: str = "current_control_plane",
    registry_path: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    intent = classify_media_intent(text)
    if intent is None:
        return None
    data = _registry(registry_path or REGISTRY_PATH)
    try:
        project = discover_project()
    except (FileNotFoundError, ValueError):
        project = None
    rows = {str(row.get("task_class")): row for row in data.get("capabilities", []) if isinstance(row, dict)}
    classes = ["IMAGE", "VIDEO"] if intent == "MIXED" else [intent]
    selected = [_route_one(rows[name], scope, env if env is not None else os.environ) for name in classes if name in rows]
    if len(selected) != len(classes):
        return {"schema": "ace.media.route.v1", "status": "BLOCKED", "task_class": intent, "reason": "CAPABILITY_NOT_REGISTERED", "selected_routes": selected, "project": project}
    status = "ROUTED" if all(row["status"] == "ROUTED" for row in selected) else "BLOCKED"
    receipt_seed = json.dumps({"text": text, "intent": intent, "routes": selected}, ensure_ascii=False, sort_keys=True)
    return {
        "schema": "ace.media.route.v1",
        "status": status,
        "task_class": intent,
        "semantic_context": build_semantic_context(text),
        "required_capabilities": [row["capability"] for row in selected],
        "required_capability": selected[0]["capability"] if len(selected) == 1 else None,
        "selected_routes": selected,
        "selected_route": selected[0] if len(selected) == 1 else None,
        "route_fingerprint": hashlib.sha256(receipt_seed.encode("utf-8")).hexdigest()[:20],
        "production_integration": all(
            (row.get("health") or {}).get("production_integration") in {"ADAPTER_VERIFIED", "VERIFIED"}
            for row in selected
        ),
        "project": project,
        "next_action": "execute selected wrapper and bind ace.media.receipt.v1" if status == "ROUTED" else "resolve reasons before execution",
        "executor": selected[0].get("executable") if len(selected) == 1 else [row.get("executable") for row in selected],
    }
