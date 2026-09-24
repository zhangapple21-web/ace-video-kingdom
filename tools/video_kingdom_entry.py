"""唯一公共入口：将视频王国需求送入统一控制面。

This facade never calls a media provider directly.  It classifies media
requests through the registered route or sends narrative work to the role
room.  Provider wrappers remain internal adapters and are not public workflow
entry points.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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

from production_control.media_routing import build_image_model_plan, choose_image_strategy, classify_media_intent, route_media_demand
from production_control.semantic_context import build_semantic_context
from production_control.collaboration import load_default_collaboration_context
from tools import role_room
from tools.creator_workflow import build_creative_development_profile, validate_creative_development_profile
from tools.workflow_decision_matrix import build_workflow_policy_receipt


# Agnes' V2.5 Flash contract is deliberately kept here, at the public
# workflow boundary, so that all adapters use one request shape.  The
# provider currently calls the image field ``images`` while newer callers use
# the less ambiguous ``input_images`` name.  ``input_images`` is the canonical
# internal spelling; transport adapters can translate it at the last moment.
AGNES_FLASH_MODEL = "agnes-video-2.5-flash"
AGNES_POLL_ENDPOINT = "https://apihub.agnes-ai.com/agnesapi"
AGNES_FLASH_MAX_INPUT_IMAGES = 5
_PENDING_STATES = {"", "queued", "pending", "running", "processing", "in_progress", "created"}
_SUCCESS_STATES = {"completed", "complete", "succeeded", "success", "done"}
_FAILURE_STATES = {"failed", "failure", "error", "cancelled", "canceled", "rejected", "expired"}
_RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}
_NARRATIVE_WORK_RE = re.compile(
    r"(?:(?:写|编|创作|改编|润色|修改|审(?:核|计)?|完善|补全|续写|拆解|分析|策划|定稿|梳理).{0,16}(?:剧本|短剧|故事|大纲|分镜|剧集)"
    r"|(?:剧本|短剧|故事|大纲|分镜|剧集).{0,16}(?:写|编|创作|改|审|补|续|拆|分析|策划|定稿|优化|完善))",
    re.IGNORECASE,
)


def _canonical_json(value: Any) -> str:
    """Serialize a request deterministically for hashing and idempotency."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _normalise_input_images(value: Any) -> list[Any]:
    """Accept the common URL/object forms and return one ordered image list."""
    if value is None:
        return []
    values = [value] if isinstance(value, (str, bytes, Mapping)) else list(value) if isinstance(value, Sequence) else None
    if values is None:
        raise ValueError("input_images must be an array")
    result: list[Any] = []
    for index, item in enumerate(values):
        if isinstance(item, bytes):
            raise ValueError(f"input_images[{index}] must be a URL or object")
        if isinstance(item, str):
            if not item.strip():
                raise ValueError(f"input_images[{index}] must not be empty")
            result.append(item.strip())
            continue
        if isinstance(item, Mapping):
            # Keep the adapter's metadata (asset_id, sha256, etc.) intact, but
            # reject objects which cannot identify an input image.
            image = dict(item)
            if not any(str(image.get(key) or "").strip() for key in ("url", "image_url", "path", "provider_ref", "data")):
                raise ValueError(f"input_images[{index}] must include a URL or image reference")
            result.append(image)
            continue
        raise ValueError(f"input_images[{index}] must be a URL or object")
    return result


def build_client_token(payload: Mapping[str, Any], *, prefix: str = "vk") -> str:
    """Build a stable, bounded idempotency token for one semantic request.

    The token intentionally excludes any existing ``client_token`` so retries
    and process resumes derive the same value instead of chaining hashes.
    """
    material = {key: value for key, value in payload.items() if key != "client_token"}
    digest = hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"[:64]


def normalize_agnes_video_payload(payload: Mapping[str, Any], *, client_token: str | None = None) -> dict[str, Any]:
    """Normalize the Agnes Flash request without making a network call.

    ``input_images`` is canonical.  The legacy ``images`` and singular
    ``image`` aliases are accepted for compatibility, but conflicting aliases
    are rejected instead of silently choosing one.
    """
    if not isinstance(payload, Mapping):
        raise ValueError("video payload must be an object")
    result = dict(payload)
    model = str(result.get("model") or AGNES_FLASH_MODEL).strip()
    if model != AGNES_FLASH_MODEL:
        raise ValueError(f"model must be {AGNES_FLASH_MODEL}")
    result["model"] = model

    supplied = [(name, result[name]) for name in ("input_images", "images", "image") if name in result and result[name] is not None]
    if supplied:
        canonical = _normalise_input_images(supplied[0][1])
        for name, value in supplied[1:]:
            if _normalise_input_images(value) != canonical:
                raise ValueError("input_images conflicts with images/image")
        if len(canonical) > AGNES_FLASH_MAX_INPUT_IMAGES:
            raise ValueError(f"{AGNES_FLASH_MODEL} accepts at most {AGNES_FLASH_MAX_INPUT_IMAGES} input_images")
        result["input_images"] = canonical
    else:
        result.pop("input_images", None)
    # Do not send compatibility aliases into the canonical hash.  A transport
    # adapter may add ``images`` after admission when talking to old Agnes.
    result.pop("images", None)
    result.pop("image", None)

    token = client_token if client_token is not None else result.get("client_token")
    if token is None or not str(token).strip():
        token = build_client_token(result)
    token = str(token).strip()
    if len(token) > 64:
        raise ValueError("client_token must be at most 64 characters")
    result["client_token"] = token
    return result


def to_agnes_transport_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Translate the canonical request to the currently deployed Agnes API."""
    result = normalize_agnes_video_payload(payload)
    # ``client_token`` is an internal idempotency value carried by the local
    # admission/manifest layer.  Agnes receives the same value through the
    # HTTP ``Idempotency-Key`` header; sending it as a JSON field causes the
    # deployed endpoint to reject an otherwise valid request.
    result.pop("client_token", None)
    images = result.pop("input_images", None)
    if images:
        result["images"] = images
    return result


def extract_video_id(response: Mapping[str, Any]) -> str | None:
    """Read only a provider ``video_id`` (never an unrelated task id)."""
    if not isinstance(response, Mapping):
        return None
    candidates: list[Any] = [response.get("video_id")]
    data = response.get("data")
    if isinstance(data, Mapping):
        candidates.append(data.get("video_id"))
    # Agnes has returned ``id`` in some gateways; it is accepted only as a
    # fallback.  ``task_id`` is intentionally excluded.
    candidates.extend([response.get("id"), data.get("id") if isinstance(data, Mapping) else None])
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _response_data(response: Any) -> dict[str, Any]:
    try:
        data = response.json()
    except (AttributeError, ValueError, TypeError):
        data = {}
    if not isinstance(data, Mapping):
        return {}
    nested = data.get("data")
    return dict(nested) if isinstance(nested, Mapping) else dict(data)


def normalize_video_status(data: Mapping[str, Any], *, video_id: str | None = None, http_status: int | None = None) -> dict[str, Any]:
    """Normalize heterogeneous Agnes poll responses into one state contract."""
    body = dict(data) if isinstance(data, Mapping) else {}
    nested = body.get("data")
    if isinstance(nested, Mapping):
        merged = dict(body)
        merged.update(nested)
        body = merged
    raw_state = str(body.get("status") or body.get("internal_status") or body.get("state") or "").strip().lower()
    if http_status is not None and http_status >= 300 and http_status not in _RETRYABLE_HTTP:
        normalized = "FAILED"
    elif raw_state in _SUCCESS_STATES:
        normalized = "COMPLETED"
    elif raw_state in _FAILURE_STATES:
        normalized = "FAILED"
    else:
        normalized = "PENDING"
    metadata = body.get("metadata") if isinstance(body.get("metadata"), Mapping) else {}
    artifact_url = body.get("url") or body.get("video_url") or body.get("output_url") or metadata.get("url")
    result: dict[str, Any] = {
        "video_id": video_id or extract_video_id(body),
        "status": normalized,
        "provider_status": raw_state or "unknown",
        "http_status": http_status,
    }
    if artifact_url:
        result["artifact_url"] = str(artifact_url)
    error = body.get("error") or body.get("message")
    if error:
        result["error"] = str(error)[:500]
    return result


def poll_agnes_video(
    video_id: str,
    api_key: str,
    *,
    session: Any = requests,
    endpoint: str = AGNES_POLL_ENDPOINT,
    timeout: float = 360,
    poll_delay: float = 2,
    max_delay: float = 60,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Poll a submitted Agnes ``video_id`` until completion or timeout.

    This function is poll-only: it never POSTs and therefore is safe to use
    after a process interruption or a response timeout.
    """
    if not str(video_id).strip():
        raise ValueError("video_id is required")
    if not str(api_key).strip():
        raise ValueError("api_key is required")
    if timeout <= 0 or poll_delay <= 0 or max_delay <= 0:
        raise ValueError("timeout, poll_delay, and max_delay must be positive")
    deadline = time.monotonic() + timeout
    delay = poll_delay
    polls = 0
    last: dict[str, Any] = {"video_id": str(video_id), "status": "PENDING", "polls": 0}
    while time.monotonic() < deadline:
        polls += 1
        try:
            response = session.get(
                endpoint,
                params={"video_id": str(video_id), "model_name": AGNES_FLASH_MODEL},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )
        except requests.RequestException as error:
            last = {"video_id": str(video_id), "status": "PENDING", "polls": polls, "error_class": "NETWORK_POLL_ERROR", "error": str(error)[:500]}
            sleep(min(delay, max(0.0, deadline - time.monotonic())))
            delay = min(delay * 2, max_delay)
            continue
        data = _response_data(response)
        last = normalize_video_status(data, video_id=str(video_id), http_status=getattr(response, "status_code", None))
        last["polls"] = polls
        if getattr(response, "status_code", 0) in _RETRYABLE_HTTP:
            retry_after = getattr(response, "headers", {}).get("Retry-After") if getattr(response, "headers", None) else None
            try:
                delay = max(0.1, min(float(retry_after), max_delay)) if retry_after is not None else min(delay * 2, max_delay)
            except (TypeError, ValueError):
                delay = min(delay * 2, max_delay)
        elif last["status"] in {"COMPLETED", "FAILED"}:
            return last
        else:
            delay = min(delay * 2, max_delay)
        remaining = deadline - time.monotonic()
        if remaining > 0:
            sleep(min(delay, remaining))
    last.update({"status": "POLL_TIMEOUT", "error_class": "POLL_TIMEOUT", "polls": polls})
    return last


def dispatch(*, text: str, out: Path, profile: str = "standard", project_id: str = "", execute: bool = False) -> dict[str, Any]:
    source = str(text or "").strip()
    if not source:
        raise ValueError("ENTRY_TEXT_REQUIRED")
    entry_id = "ENTRY-" + uuid.uuid4().hex[:12]
    detected_media_intent = classify_media_intent(source)
    # A request to develop/audit narrative must reach the writer/director room
    # before media routing, even when the same sentence mentions making a
    # video or shots. Otherwise a script can be mistaken for an instruction to
    # call the image/video capability directly.
    narrative_first = bool(_NARRATIVE_WORK_RE.search(source))
    intent = None if narrative_first else detected_media_intent
    creative_development = build_creative_development_profile(
        title=project_id or "未命名短剧",
        source_text=source,
    )
    creative_development_check = validate_creative_development_profile(creative_development)
    workflow_policy = build_workflow_policy_receipt(ROOT, creative_development=creative_development)
    out.parent.mkdir(parents=True, exist_ok=True)
    creative_development_path = out.with_name(out.stem + ".creative_development_profile.v1.json")
    creative_development_path.write_text(
        json.dumps(creative_development, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    receipt: dict[str, Any] = {
        "schema": "video_kingdom.unified_entry_receipt.v1",
        "entry_id": entry_id,
        "entrypoint": "video-kingdom",
        "control_plane": "production_control",
        "request": source,
        "routing_decision": "NARRATIVE_FIRST" if narrative_first else ("MEDIA_CAPABILITY" if intent else "NARRATIVE_OR_GENERAL"),
        "detected_media_intent": detected_media_intent,
        "semantic_context": build_semantic_context(source),
        "profile": profile,
        "project_id": project_id or None,
        "provider_submission": "NOT_PERFORMED",
        "creative_development": creative_development,
        "creative_development_artifact": str(creative_development_path),
        "creative_development_check": creative_development_check,
        # The matrix is a method/budget contract, not a second gate.  Loading
        # it here makes the 1-7 decisions available in every window and leaves
        # a hash proving which policy the run consumed.
        "workflow_policy": workflow_policy,
        # Management/default-method context is recorded at the only public
        # entry so narrative and media requests cannot silently diverge.
        # This does not replace the existing script/director/provider gates.
        "collaboration": load_default_collaboration_context(ROOT),
    }
    if intent:
        route = route_media_demand(source, scope="current_control_plane")
        receipt.update({"dispatch": "media_route", "media_intent": intent, "route": route, "status": route.get("status") if route else "BLOCKED"})
        if intent in {"VIDEO", "MIXED"}:
            receipt["image_strategy"] = choose_image_strategy(source)
            receipt["image_model_plan"] = build_image_model_plan(route or {})
    else:
        role_receipt = out.with_name(out.stem + ".role.json")
        role_args = ["--idea", source, "--out", str(role_receipt), "--profile", profile]
        if project_id:
            role_args.extend(["--project-id", project_id])
        if execute:
            role_args.append("--execute")
        role_status = role_room.main(role_args)
        receipt.update({"dispatch": "role_room", "role_receipt": str(role_receipt), "role_exit_code": role_status, "status": "COMPLETED" if role_status == 0 else "BLOCKED"})
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", "--idea", dest="text", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--profile", choices=("rapid", "standard", "full_audit"), default="standard")
    parser.add_argument("--project-id", default="")
    parser.add_argument("--execute", action="store_true", help="仅对角色房间执行 OneAPI；媒体仍只生成路由收据")
    args = parser.parse_args(argv)
    try:
        receipt = dispatch(text=args.text, out=args.out, profile=args.profile, project_id=args.project_id, execute=args.execute)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": receipt["status"], "dispatch": receipt["dispatch"], "out": str(args.out)}, ensure_ascii=False))
    return 0 if receipt["status"] in {"COMPLETED", "ROUTED", "BLOCKED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
