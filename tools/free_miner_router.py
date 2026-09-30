"""Unified ACE model-resource routing with capability-aware free/paid selection.

The liveness receipt is the admission source; this module never upgrades a model
from catalog presence to a capability it did not prove. It is safe to import
from role-room/world evolution and is also usable as a small CLI planner.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "research" / "free_miner_pool.v1.json"
_CONFIG: dict[str, Any] | None = None


def config() -> dict[str, Any]:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = json.loads(CONFIG.read_text(encoding="utf-8"))
    return _CONFIG


def _provider_for(model: str) -> str:
    for item in config().get("paid_resources", []):
        if item.get("model") == model:
            return str(item.get("provider") or "oneapi_paid")
    if model in config()["providers"]["oneapi_local"].get("models", []):
        return "oneapi_local"
    if model in config()["providers"].get("zhipu", {}).get("models", []):
        return "zhipu"
    if model.startswith(("MiniMax", "gemma-4")):
        return "sambanova"
    return "nim"


def _free_candidates(capability: str) -> list[dict[str, Any]]:
    unavailable = {model for models in config().get("unavailable_models", {}).values() for model in models}
    unknown = set(config().get("unknown_models", []))
    pool = list(config()["pools"].get(capability, config()["pools"]["simple"]))
    result = []
    for model in pool:
        status = "unavailable" if model in unavailable else ("unknown" if model in unknown else "available")
        result.append({"model": model, "provider": _provider_for(model), "cost_tier": "free_credit", "resource_class": "free", "status": status})
    return sorted(result, key=lambda item: {"available": 0, "unknown": 1, "unavailable": 2}.get(item["status"], 3))


def _paid_candidates(capability: str) -> list[dict[str, Any]]:
    return [
        {**item, "cost_tier": "paid", "resource_class": "paid"}
        for item in config().get("paid_resources", [])
        if item.get("status") != "unavailable" and (capability in {"reasoning", "simple", "calibration"} or capability in item.get("capabilities", []))
    ]


def resource_candidates(capability: str = "simple", *, task_class: str = "routine", requested_model: str | None = None, allow_paid: bool = True, free_preferred: bool | None = None) -> list[dict[str, Any]]:
    """Return the unified ACE pool in decision order, preserving free and paid resources."""
    free = [item for item in _free_candidates(capability) if item["status"] != "unavailable"]
    paid = _paid_candidates(capability) if allow_paid else []
    must_paid = task_class in set(config()["policy"].get("paid_preferred_task_classes", []))
    prefer_free = (task_class in set(config()["policy"].get("free_preferred_task_classes", []))) if free_preferred is None else free_preferred
    if must_paid:
        ordered = paid + free
    elif prefer_free:
        ordered = free + paid
    else:
        ordered = paid + free
    if requested_model:
        exact = [item for item in ordered if item["model"] == requested_model]
        ordered = exact + [item for item in ordered if item["model"] != requested_model]
    return ordered


def candidates(capability: str = "simple", *, paid_fallback: bool = False) -> list[dict[str, Any]]:
    """Backward-compatible free-pool view; use resource_candidates for unified routing."""
    free = _free_candidates(capability)
    if paid_fallback:
        free.extend(_paid_candidates(capability))
    return free


def route_plan(capability: str = "simple", *, high_value: bool = False, task_class: str | None = None, requested_model: str | None = None) -> dict[str, Any]:
    """Return an auditable plan for the unified pool; paid models remain first-class."""
    task_class = task_class or ("high_value" if high_value else "routine")
    ordered = resource_candidates(capability, task_class=task_class, requested_model=requested_model)
    return {
        "capability": capability,
        "task_class": task_class,
        "free_first": ordered[0]["resource_class"] == "free" if ordered else False,
        "selection_factors": config()["policy"]["selection_factors"],
        "candidates": ordered,
        "paid_models_preserved": [item["model"] for item in _paid_candidates(capability)],
        "paid_fallback_requires_explicit_opt_in": False,
        "source_receipt": config()["source_receipt"],
    }


def _key_for(provider: str) -> str:
    names = {
        "oneapi_local": ("ONEAPI_API_KEY", "ONEAPI_LOCAL_MASTER_KEY", "ONEAPI_ADMIN_TOKEN", "ONE_API_KEY", "OPENAI_API_KEY"),
        "oneapi_paid": ("ONEAPI_API_KEY", "ONEAPI_LOCAL_MASTER_KEY", "ONEAPI_ADMIN_TOKEN", "ONE_API_KEY", "OPENAI_API_KEY"),
        "zhipu": ("ZHIPU_API_KEY", "ZHIPU_KEY"),
        "nim": ("NIM_KEY_1", "NVIDIA_API_KEY"),
        "sambanova": ("SAMBANOVA_API_KEY", "SAMBANOVA_KEY", "SN_API_KEY"),
    }
    return next((os.environ.get(name, "").strip() for name in names.get(provider, ()) if os.environ.get(name, "").strip()), "")


def _base_for(provider: str) -> str:
    info = config()["providers"].get(provider, {})
    return os.environ.get(info.get("base_url_env", ""), info.get("default_base_url", "")).rstrip("/")


def chat(messages: list[dict[str, str]], *, capability: str = "simple", timeout: float = 35, task_class: str = "routine", requested_model: str | None = None, allow_paid: bool = True, free_preferred: bool | None = None, paid_fallback: bool | None = None, max_tokens: int | None = None, temperature: float = 0.7, skip_unknown: bool = False, exclude_models: list[str] | None = None, min_content_chars: int = 0, must_substrings: list[str] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Call the unified pool in policy order; paid resources are never removed."""
    if paid_fallback is not None:  # compatibility with the original API
        allow_paid = paid_fallback
    attempts: list[dict[str, Any]] = []
    excluded = set(exclude_models or [])
    for item in resource_candidates(capability, task_class=task_class, requested_model=requested_model, allow_paid=allow_paid, free_preferred=free_preferred):
        if item.get("model") in excluded:
            attempts.append({**item, "status": "SKIPPED", "reason": "excluded_model"})
            continue
        if skip_unknown and item.get("status") == "unknown":
            attempts.append({**item, "status": "SKIPPED", "reason": "unknown_model"})
            continue
        provider = item["provider"]
        key = _key_for(provider)
        if not key:
            attempts.append({**item, "status": "SKIPPED", "reason": "missing_provider_key"})
            continue
        payload: dict[str, Any] = {"model": item["model"], "messages": messages, "temperature": temperature}
        if max_tokens:
            payload["max_tokens"] = int(max_tokens)
        req = urllib.request.Request(_base_for(provider) + "/chat/completions", data=json.dumps(payload).encode("utf-8"), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
        started = time.time()
        call_timeout = min(float(timeout), 45.0) if provider == "nim" else float(timeout)
        print("[miner] try model=%s provider=%s class=%s timeout=%.0fs" % (item["model"], provider, item.get("resource_class"), call_timeout), flush=True)
        try:
            with urllib.request.urlopen(req, timeout=call_timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            choice = (body.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            text = str(message.get("content") or "").strip()
            reasoning = str(message.get("reasoning_content") or "").strip()
            if not text and not reasoning:
                raise ValueError("empty_model_output")
            latency_ms = int((time.time() - started) * 1000)
            missing = [s for s in (must_substrings or []) if s not in text]
            if min_content_chars and len(text) < min_content_chars:
                attempts.append({**item, "status": "FAILED", "error": "quality_reject:short_content:%s" % len(text), "latency_ms": latency_ms})
                print("[miner] reject model=%s short_content=%s" % (item["model"], len(text)), flush=True)
                continue
            if missing:
                attempts.append({**item, "status": "FAILED", "error": "quality_reject:missing:" + ",".join(missing), "latency_ms": latency_ms})
                print("[miner] reject model=%s missing=%s" % (item["model"], ",".join(missing)), flush=True)
                continue
            attempts.append({**item, "status": "COMPLETED", "latency_ms": latency_ms, "finish_reason": str(choice.get("finish_reason") or "")})
            return {
                "content": text,
                "reasoning": reasoning,
                "model": body.get("model") or item["model"],
                "provider": provider,
                "finish_reason": str(choice.get("finish_reason") or ""),
                "usage": body.get("usage") or {},
                "latency_ms": latency_ms,
            }, attempts
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            attempts.append({**item, "status": "FAILED", "error": type(exc).__name__ + ": " + str(exc), "latency_ms": int((time.time() - started) * 1000)})
            print("[miner] fail model=%s error=%s" % (item["model"], type(exc).__name__), flush=True)
    raise RuntimeError(json.dumps({"code": "RESOURCE_POOL_EXHAUSTED", "task_class": task_class, "attempts": attempts}, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Print or execute the unified ACE model-resource route")
    parser.add_argument("--capability", choices=sorted(config()["pools"]), default="simple")
    parser.add_argument("--high-value", action="store_true")
    parser.add_argument("--task-class", choices=sorted(set(config()["policy"]["free_preferred_task_classes"] + config()["policy"]["paid_preferred_task_classes"])), default="routine")
    parser.add_argument("--model", dest="requested_model", help="指定模型时只把它作为首选，不绕过可用性检查")
    parser.add_argument("--no-paid", action="store_true", help="仅用于诊断，禁止进入付费资源")
    parser.add_argument("--paid-first", action="store_true", help="当前任务不适合免费优先时使用")
    parser.add_argument("--prompt")
    args = parser.parse_args()
    if not args.prompt:
        task_class = "high_value" if args.high_value else args.task_class
        print(json.dumps(route_plan(args.capability, high_value=args.high_value, task_class=task_class, requested_model=args.requested_model), ensure_ascii=False, indent=2))
        return 0
    try:
        task_class = "high_value" if args.high_value else args.task_class
        result, attempts = chat([{"role": "user", "content": args.prompt}], capability=args.capability, task_class=task_class, requested_model=args.requested_model, allow_paid=not args.no_paid, free_preferred=False if args.paid_first else None)
        print(json.dumps({"status": "COMPLETED", "result": result, "attempts": attempts}, ensure_ascii=False, indent=2))
        return 0
    except RuntimeError as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
