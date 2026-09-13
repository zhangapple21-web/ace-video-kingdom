"""Deterministic, bounded conversation projection for media tasks."""
from __future__ import annotations

import base64
import hashlib
import io
import re
from typing import Any, Mapping

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional at import time
    Image = None


IMAGE_KEYS = ("image", "image_url", "data", "b64_json")
IMPORTANT_RE = re.compile(r"(结论|决定|下一步|验收|失败|原因|状态|next action|decision|conclusion|acceptance)", re.I)


def _image_bytes(value: Any) -> bytes | None:
    if isinstance(value, Mapping):
        for key in IMAGE_KEYS:
            if key in value:
                return _image_bytes(value[key])
        return None
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        return base64.b64decode(raw, validate=False)
    except Exception:
        return None


def _encode_image(raw: bytes, cap: int) -> bytes:
    if len(raw) <= cap:
        return raw
    if Image is None:
        return raw[:cap]
    with Image.open(io.BytesIO(raw)) as source:
        image = source.convert("RGB")
        # Resize before quality search so a large PNG cannot dominate the
        # aggregate budget even when its quality is already low.
        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        best = b""
        for quality in (82, 72, 62, 52, 42, 32, 22):
            out = io.BytesIO()
            image.save(out, format="WEBP", quality=quality, method=6)
            candidate = out.getvalue()
            if len(candidate) <= cap:
                best = candidate
                break
            best = candidate
        while len(best) > cap and image.width > 320 and image.height > 320:
            image.thumbnail((max(320, int(image.width * 0.8)), max(320, int(image.height * 0.8))), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            image.save(out, format="WEBP", quality=28, method=6)
            best = out.getvalue()
        return best[:cap]


def project_messages(
    messages: list[Mapping[str, Any]],
    *,
    image_cap: int = 512 * 1024,
    aggregate_cap: int = 2 * 1024 * 1024,
    stable_head: int = 16,
    dynamic_tail: int = 8,
) -> dict[str, Any]:
    """Project messages without exceeding per-image or aggregate limits.

    Image payloads are re-encoded and low-priority history is dropped before
    protected conclusions/decisions. The function is pure and never calls a
    provider.
    """
    if image_cap <= 0 or aggregate_cap <= 0:
        raise ValueError("PROJECTION_BUDGET_INVALID")
    # The public contract is a hard 1 MiB single-image ceiling.  Callers may
    # request a stricter cap (for example 64 KiB in tests), but never loosen
    # the production ceiling accidentally.
    image_cap = min(int(image_cap), 1024 * 1024)
    indexed = list(enumerate(messages))
    protected = [item for item in indexed if IMPORTANT_RE.search(str(item[1].get("text") or item[1].get("content") or ""))]
    selected_indices = {i for i, _ in indexed[:stable_head]}
    selected_indices.update(i for i, _ in indexed[-dynamic_tail:])
    selected_indices.update(i for i, _ in protected)
    # Keep the latest messages first when the history is very long.
    selected = [dict(msg) for i, msg in indexed if i in selected_indices]
    dropped = len(messages) - len(selected)
    image_bytes = 0
    asset_references: list[dict[str, Any]] = []
    for message in selected:
        for key in IMAGE_KEYS:
            if key not in message:
                continue
            raw = _image_bytes(message[key])
            if raw is None:
                continue
            encoded = _encode_image(raw, image_cap)
            if isinstance(message[key], Mapping):
                nested = dict(message[key])
                nested["b64_json"] = base64.b64encode(encoded).decode("ascii")
                message[key] = nested
            else:
                message[key] = base64.b64encode(encoded).decode("ascii")
            image_bytes += len(encoded)
            asset_references.append({
                "asset_sha256": hashlib.sha256(raw).hexdigest(),
                "original_bytes": len(raw),
                "projected_bytes": len(encoded),
                "message_role": message.get("role"),
            })
    # Enforce the aggregate cap by removing unprotected image-bearing messages
    # first, then non-protected text. Never drop the protected conclusion set.
    while image_bytes > aggregate_cap and selected:
        removable = next((m for m in selected if not IMPORTANT_RE.search(str(m.get("text") or m.get("content") or "")) and any(k in m for k in IMAGE_KEYS)), None)
        if removable is None:
            break
        selected.remove(removable)
        dropped += 1
        image_bytes = sum(len(_image_bytes(m[k]) or b"") for m in selected for k in IMAGE_KEYS)
    visual_deferred = False
    if image_bytes > aggregate_cap:
        # Never leave a protected conclusion carrying an oversized inline blob.
        # Preserve the semantic message and replace only the visual payload by
        # a deterministic asset reference; replay can resolve it from Asset
        # Store without copying the original bytes into conversation context.
        for message in selected:
            for key in IMAGE_KEYS:
                raw = _image_bytes(message.get(key))
                if raw is None:
                    continue
                reference = {
                    "asset_ref": "sha256:" + hashlib.sha256(raw).hexdigest(),
                    "original_bytes": len(raw),
                    "projection": "deferred_visual",
                }
                message[key] = reference
                visual_deferred = True
        image_bytes = sum(len(_image_bytes(m[k]) or b"") for m in selected for k in IMAGE_KEYS if k in m)

    encoded_images = sum(
        1 for message in selected for key in IMAGE_KEYS
        if key in message and _image_bytes(message[key]) is not None
    )
    projected_within_budget = image_bytes <= aggregate_cap and all(
        len(_image_bytes(m[k]) or b"") <= image_cap
        for m in selected for k in IMAGE_KEYS if k in m
    )
    return {
        "schema": "ace.media.projection.v1",
        "messages": selected,
        "dropped_messages": dropped,
        "images": encoded_images,
        "image_bytes": image_bytes,
        "image_cap": image_cap,
        "aggregate_cap": aggregate_cap,
        "within_budget": image_bytes <= aggregate_cap and all(
            len(_image_bytes(m[k]) or b"") <= image_cap for m in selected for k in IMAGE_KEYS if k in m
        ),
        "protected_conclusions": len(protected),
        "asset_references": asset_references,
        "visuals_deferred": visual_deferred,
        "status": "DEGRADED_VISUALS" if visual_deferred else "PROJECTED",
        "projection_blocked": not projected_within_budget,
        "budget_failure": ({
            "budget": aggregate_cap,
            "actual_size": image_bytes,
            "protected_size": sum(
                len(_image_bytes(m[k]) or b"")
                for m in selected
                if IMPORTANT_RE.search(str(m.get("text") or m.get("content") or ""))
                for k in IMAGE_KEYS if k in m
            ),
            "largest_items": sorted((item["projected_bytes"] for item in asset_references), reverse=True)[:5],
            "reason": "aggregate_image_budget_exceeded",
            "recovery_strategy": "resolve asset_ref from Asset Store",
        } if not projected_within_budget else None),
    }
