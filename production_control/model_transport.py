"""Safe OpenAI-compatible model transport.

The model boundary receives only asset references.  A provider adapter may
resolve a remote reference to a normal URL immediately before POST; it never
re-embeds the original bytes or copies the UI data URL into the request.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Mapping

from .image_assets import AssetStore, InlineImageError, assert_model_boundary
from .projection import prepare_model_request


def _resolve_provider_value(value: Any, store: AssetStore) -> Any:
    if isinstance(value, list):
        return [_resolve_provider_value(item, store) for item in value]
    if not isinstance(value, Mapping):
        return value
    if value.get("asset_id") or value.get("asset_ref"):
        reference = store.resolve_for_provider(value)
        if reference.startswith(("https://", "http://")):
            return {"url": reference}
        raise InlineImageError("PROVIDER_REFERENCE_NOT_PUBLIC_URL")
    return {key: _resolve_provider_value(child, store) for key, child in value.items()}


def materialize_provider_messages(messages: list[Mapping[str, Any]], store: AssetStore) -> list[dict[str, Any]]:
    """Resolve references at the provider edge without allowing inline data."""
    output = _resolve_provider_value(messages, store)
    assert isinstance(output, list)
    return [dict(item) for item in output]


def build_chat_payload(
    *,
    model: str,
    messages: list[Mapping[str, Any]],
    asset_store: AssetStore | str | Path | None = None,
    image_variant: str = "thumbnail",
    max_tokens: int = 512,
    temperature: float = 0.2,
) -> tuple[dict[str, Any], dict[str, Any]]:
    store = asset_store if isinstance(asset_store, AssetStore) else AssetStore(asset_store)
    model_request = prepare_model_request(messages, asset_store=store, image_variant=image_variant)
    assert_model_boundary(model_request)
    provider_messages = materialize_provider_messages(model_request["messages"], store)
    payload = {
        "model": model,
        "messages": provider_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # This boundary permits URLs only after the controlled reference has been
    # resolved; data URLs/base64 remain forbidden.
    assert_model_boundary(payload)
    return payload, model_request


def _to_responses_content(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "input_text", "text": content}]
    if not isinstance(content, list):
        raise ValueError("RESPONSES_CONTENT_INVALID")
    output: list[dict[str, Any]] = []
    for item in content:
        if not isinstance(item, Mapping):
            raise ValueError("RESPONSES_CONTENT_ITEM_INVALID")
        if item.get("type") == "text":
            output.append({"type": "input_text", "text": str(item.get("text") or "")})
            continue
        if item.get("type") in {"image_url", "input_image"}:
            image = item.get("image_url")
            if isinstance(image, Mapping):
                image = image.get("url")
            if not isinstance(image, str) or not image.startswith(("https://", "http://")):
                raise InlineImageError("RESPONSES_IMAGE_REFERENCE_NOT_PUBLIC_URL")
            output.append({"type": "input_image", "image_url": image})
            continue
        raise ValueError("RESPONSES_CONTENT_TYPE_UNSUPPORTED")
    return output


def build_responses_payload(
    *,
    model: str,
    messages: list[Mapping[str, Any]],
    asset_store: AssetStore | str | Path | None = None,
    image_variant: str = "thumbnail",
    max_output_tokens: int = 512,
) -> tuple[dict[str, Any], dict[str, Any]]:
    store = asset_store if isinstance(asset_store, AssetStore) else AssetStore(asset_store)
    model_request = prepare_model_request(messages, asset_store=store, image_variant=image_variant)
    provider_messages = materialize_provider_messages(model_request["messages"], store)
    payload = {
        "model": model,
        "input": [
            {"role": message.get("role", "user"), "content": _to_responses_content(message.get("content", ""))}
            for message in provider_messages
        ],
        "max_output_tokens": max_output_tokens,
    }
    assert_model_boundary(payload)
    return payload, model_request


def post_responses(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[Mapping[str, Any]],
    asset_store: AssetStore | str | Path | None = None,
    image_variant: str = "thumbnail",
    max_output_tokens: int = 512,
    timeout: float = 90,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload, model_request = build_responses_payload(
        model=model,
        messages=messages,
        asset_store=asset_store,
        image_variant=image_variant,
        max_output_tokens=max_output_tokens,
    )
    request = urllib.request.Request(
        base_url.rstrip("/") + "/responses",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    return result, {
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "request_bytes": len(request.data or b""),
        "asset_ids": model_request["asset_ids"],
        "model_boundary": model_request["projection"]["model_boundary"],
    }


def post_chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[Mapping[str, Any]],
    asset_store: AssetStore | str | Path | None = None,
    image_variant: str = "thumbnail",
    max_tokens: int = 512,
    temperature: float = 0.2,
    timeout: float = 90,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload, model_request = build_chat_payload(
        model=model,
        messages=messages,
        asset_store=asset_store,
        image_variant=image_variant,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    result_meta = {
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "request_bytes": len(request.data or b""),
        "asset_ids": model_request["asset_ids"],
        "model_boundary": model_request["projection"]["model_boundary"],
    }
    return result, result_meta


__all__ = ["build_chat_payload", "build_responses_payload", "materialize_provider_messages", "post_chat_completion", "post_responses"]
