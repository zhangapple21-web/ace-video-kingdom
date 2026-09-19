"""Deterministic, bounded conversation projection for media tasks."""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .image_assets import AssetStore, InlineImageError, assert_model_boundary, build_frame_analysis_plan, decode_inline_image


IMAGE_KEYS = ("image", "image_url", "data", "b64_json")
IMPORTANT_RE = re.compile(r"(结论|决定|下一步|验收|失败|原因|状态|next action|decision|conclusion|acceptance)", re.I)
MAX_STABLE_HEAD = 16
MAX_DYNAMIC_TAIL = 8


def _image_bytes(value: Any) -> bytes | None:
    decoded = decode_inline_image(value)
    return decoded[0] if decoded else None


def _replace_nested_image_urls(value: Any, store: AssetStore, variant: str) -> tuple[Any, int, dict[str, dict[str, Any]]]:
    """Normalize OpenAI-style multimodal content before it reaches a model."""
    if isinstance(value, list):
        items: list[Any] = []
        count = 0
        assets: dict[str, dict[str, Any]] = {}
        for child in value:
            normalized, child_count, child_assets = _replace_nested_image_urls(child, store, variant)
            items.append(normalized)
            count += child_count
            assets.update(child_assets)
        return items, count, assets
    if not isinstance(value, Mapping):
        return value, 0, {}
    output = dict(value)
    count = 0
    assets: dict[str, dict[str, Any]] = {}
    image_url = output.get("image_url")
    if isinstance(image_url, Mapping):
        raw_url = image_url.get("url") or image_url.get("data") or image_url.get("b64_json")
        decoded = decode_inline_image(raw_url)
        if decoded:
            raw, mime = decoded
            reference = store.register(raw, mime=mime)
            count += 1
        elif isinstance(raw_url, Mapping) and (raw_url.get("asset_id") or raw_url.get("asset_ref")):
            reference = store.reference(str(raw_url.get("asset_id") or raw_url.get("asset_ref")), variant=variant)
        elif isinstance(raw_url, str) and raw_url.startswith(("https://", "http://")):
            reference = store.register_reference(raw_url)
        else:
            reference = None
        if reference is not None:
            reference["variant"] = variant
            reference["projection"] = "asset_reference"
            output["image_url"] = reference
            identity = str(reference.get("asset_id") or reference.get("asset_ref"))
            assets[identity] = reference
        elif raw_url not in (None, ""):
            raise InlineImageError("UNREGISTERED_NESTED_IMAGE_INPUT:image_url")
    for key, child in list(output.items()):
        if key == "image_url":
            continue
        normalized, child_count, child_assets = _replace_nested_image_urls(child, store, variant)
        output[key] = normalized
        count += child_count
        assets.update(child_assets)
    return output, count, assets


def _message_timestamp(message: Mapping[str, Any]) -> float | None:
    for field in ("timestamp", "created_at", "updated_at", "at"):
        value = message.get(field)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            try:
                parsed = float(value)
            except (OverflowError, ValueError):
                continue
            if math.isfinite(parsed):
                return parsed
        if not isinstance(value, str):
            continue
        raw = value.strip()
        try:
            parsed = float(raw)
        except ValueError:
            try:
                normalized = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
                parsed_datetime = datetime.fromisoformat(normalized)
                if parsed_datetime.tzinfo is None:
                    parsed_datetime = parsed_datetime.replace(tzinfo=timezone.utc)
                parsed = parsed_datetime.timestamp()
            except (TypeError, ValueError, OverflowError):
                continue
        if math.isfinite(parsed):
            return parsed
    return None


def project_messages(
    messages: list[Mapping[str, Any]],
    *,
    image_cap: int = 512 * 1024,
    aggregate_cap: int = 2 * 1024 * 1024,
    stable_head: int = 16,
    dynamic_tail: int = 8,
    asset_store: AssetStore | str | Path | None = None,
    image_variant: str = "thumbnail",
) -> dict[str, Any]:
    """Project history while keeping visual bytes outside the model context.

    Inline data URLs/base64 are accepted only at this UI-ingress boundary.
    They are registered in ``AssetStore`` and replaced by a stable reference;
    returned messages contain no image bytes and are safe to send to Codex or
    a 3002-compatible endpoint.
    """
    if image_cap <= 0 or aggregate_cap <= 0:
        raise ValueError("PROJECTION_BUDGET_INVALID")
    if image_variant not in ("thumbnail", "768", "1280", "original"):
        raise ValueError(f"UNKNOWN_IMAGE_VARIANT:{image_variant}")
    # Callers cannot accidentally disable bounded projection by requesting an
    # unbounded history window; this is independent of the 3002 body limit.
    stable_head = max(0, min(int(stable_head), MAX_STABLE_HEAD))
    dynamic_tail = max(0, min(int(dynamic_tail), MAX_DYNAMIC_TAIL))
    # The public contract is a hard 1 MiB single-image ceiling.  Callers may
    # request a stricter cap (for example 64 KiB in tests), but never loosen
    # the production ceiling accidentally.
    image_cap = min(int(image_cap), 1024 * 1024)
    indexed = [(i, message, _message_timestamp(message)) for i, message in enumerate(messages)]
    ordered = sorted(
        indexed,
        key=lambda item: (item[2] is None, item[2] if item[2] is not None else item[0], item[0]),
    )
    protected = [item for item in ordered if IMPORTANT_RE.search(str(item[1].get("text") or item[1].get("content") or ""))]
    dynamic_items = ordered[-dynamic_tail:] if dynamic_tail > 0 else []
    dynamic_indices = {item[0] for item in dynamic_items}
    stable_indices = {item[0] for item in ordered[:stable_head]} if stable_head > 0 else set()
    stable_indices.update(item[0] for item in protected if item[0] not in dynamic_indices)
    stable_items = [item for item in ordered if item[0] in stable_indices and item[0] not in dynamic_indices]
    selected_items = stable_items + dynamic_items
    selected = [dict(item[1]) for item in selected_items]
    dropped = len(messages) - len(selected)
    store = asset_store if isinstance(asset_store, AssetStore) else AssetStore(asset_store)
    inline_images = 0
    unique_assets: dict[str, dict[str, Any]] = {}
    asset_references: list[dict[str, Any]] = []
    visual_deferred = False
    for message in selected:
        if "content" in message:
            normalized_content, nested_count, nested_assets = _replace_nested_image_urls(message["content"], store, image_variant)
            message["content"] = normalized_content
            if nested_count or nested_assets:
                inline_images += nested_count
                visual_deferred = visual_deferred or bool(nested_count)
                for identity, reference in nested_assets.items():
                    duplicate_nested = identity in unique_assets
                    unique_assets.setdefault(identity, reference)
                    asset_references.append({
                        "asset_id": reference.get("asset_id"),
                        "asset_ref": reference.get("asset_ref"),
                        "original_bytes": reference.get("original_bytes"),
                        "projected_bytes": 0,
                        "variant": reference.get("variant"),
                        "message_role": message.get("role"),
                        "deduplicated": duplicate_nested,
                    })
        # Video frames are never copied wholesale into history. Keep only a
        # deterministic sample plus explicitly flagged suspects, then apply
        # the same asset conversion to those selected frames.
        frames = message.pop("frames", None)
        if isinstance(frames, list):
            plan = build_frame_analysis_plan(frames)
            selected_frames: list[dict[str, Any]] = []
            for frame_index in plan["selected_indices"]:
                frame = frames[frame_index]
                frame_value: Any = frame.get("image") if isinstance(frame, Mapping) and "image" in frame else frame
                decoded_frame = decode_inline_image(frame_value)
                if decoded_frame:
                    raw, mime = decoded_frame
                    frame_ref = store.register(raw, mime=mime)
                    inline_images += 1
                elif isinstance(frame_value, Mapping) and (frame_value.get("asset_id") or frame_value.get("asset_ref")):
                    frame_ref = store.reference(str(frame_value.get("asset_id") or frame_value.get("asset_ref")), variant=image_variant)
                else:
                    raise InlineImageError(f"UNREGISTERED_FRAME_INPUT:{frame_index}")
                frame_ref["variant"] = image_variant
                frame_ref["projection"] = "asset_reference"
                selected_frames.append({"frame_index": frame_index, "image": frame_ref})
                unique_id = str(frame_ref.get("asset_id") or frame_ref.get("asset_ref"))
                duplicate_frame = unique_id in unique_assets
                unique_assets.setdefault(unique_id, frame_ref)
                asset_references.append({"asset_id": frame_ref.get("asset_id"), "asset_ref": frame_ref.get("asset_ref"), "variant": image_variant, "frame_index": frame_index, "projected_bytes": 0, "deduplicated": duplicate_frame})
            message["frames"] = selected_frames
            message["frame_analysis_plan"] = plan
            visual_deferred = True
        for key in IMAGE_KEYS:
            if key not in message:
                continue
            value = message[key]
            reference: dict[str, Any] | None = None
            decoded = decode_inline_image(value)
            if decoded:
                raw, mime = decoded
                reference = store.register(raw, mime=mime)
                inline_images += 1
                visual_deferred = True
            elif isinstance(value, Mapping) and (value.get("asset_id") or value.get("asset_ref")):
                asset_id = str(value.get("asset_id") or value.get("asset_ref"))
                reference = store.reference(asset_id, variant=str(value.get("variant") or image_variant))
            elif isinstance(value, str) and value.startswith(("https://", "http://")):
                reference = store.register_reference(value)
            if reference is None:
                # An image-shaped field that was not accepted at UI ingress is
                # unsafe to forward. Fail closed instead of allowing a short
                # or malformed base64 value to leak to Codex/3002.
                if value not in (None, ""):
                    raise InlineImageError(f"UNREGISTERED_IMAGE_INPUT:{key}")
                continue
            if isinstance(value, Mapping):
                # Keep bounded semantic results with the reference; never
                # carry arbitrary provider response blobs into history.
                for field in ("summary", "analysis", "analysis_result", "caption"):
                    metadata = value.get(field)
                    if isinstance(metadata, (str, int, float, bool)):
                        text = str(metadata)
                        if len(text) <= 4000:
                            reference[field] = metadata
            reference["variant"] = str(reference.get("variant") or image_variant)
            reference["projection"] = "asset_reference"
            message[key] = reference
            identity = str(reference.get("asset_id") or reference.get("asset_ref"))
            duplicate = identity in unique_assets
            unique_assets.setdefault(identity, reference)
            asset_references.append({
                "asset_id": reference.get("asset_id"),
                "asset_ref": reference.get("asset_ref"),
                "original_bytes": reference.get("original_bytes"),
                "projected_bytes": 0,
                "variant": reference.get("variant"),
                "message_role": message.get("role"),
                "deduplicated": duplicate,
            })
    # Image bytes are intentionally zero after the boundary conversion. The
    # caps remain in the API for compatibility and telemetry, but are no
    # longer used to decide whether inline binary may enter a model request.
    image_bytes = 0
    return {
        "schema": "ace.media.projection.v1",
        "messages": selected,
        "dropped_messages": dropped,
        "history_cap": MAX_STABLE_HEAD + MAX_DYNAMIC_TAIL,
        "images": len(unique_assets),
        "inline_images": inline_images,
        "image_bytes": image_bytes,
        "image_cap": image_cap,
        "aggregate_cap": aggregate_cap,
        "within_budget": True,
        "protected_conclusions": len(protected),
        "asset_references": asset_references,
        "unique_asset_ids": sorted(unique_assets),
        "visuals_deferred": visual_deferred,
        "status": "ASSET_REFERENCES" if visual_deferred else "PROJECTED",
        "projection_blocked": False,
        "budget_failure": None,
        "model_boundary": "asset_reference_only",
    }


def prepare_model_request(
    messages: list[Mapping[str, Any]],
    *,
    asset_store: AssetStore | str | Path | None = None,
    image_variant: str = "thumbnail",
    stable_head: int = 16,
    dynamic_tail: int = 8,
) -> dict[str, Any]:
    """Build the only request shape allowed to cross into Codex/OneAPI/3002.

    The returned payload is intentionally small and contains references only;
    callers must resolve a selected variant at the provider edge when vision
    input is actually needed.
    """
    projection = project_messages(
        messages,
        asset_store=asset_store,
        image_variant=image_variant,
        stable_head=stable_head,
        dynamic_tail=dynamic_tail,
    )
    payload = {
        "messages": projection["messages"],
        "asset_ids": projection["unique_asset_ids"],
        "projection": {
            "schema": projection["schema"],
            "dropped_messages": projection["dropped_messages"],
            "history_cap": projection["history_cap"],
            "inline_images": projection["inline_images"],
            "visuals_deferred": projection["visuals_deferred"],
            "model_boundary": projection["model_boundary"],
        },
    }
    assert_model_boundary(payload)
    return payload


__all__ = ["project_messages", "prepare_model_request"]
