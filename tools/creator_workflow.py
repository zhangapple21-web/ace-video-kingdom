"""Creator-layer inputs that complement the Video Kingdom control plane.

The creator brief is an optional planning input.  The publish recap is a
non-authoritative feedback record: it may improve the next story/shot plan,
but it can never approve delivery or change provider routing by itself.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BRIEF_REQUIRED = ("audience", "hook", "ending_hook", "style")


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_creator_brief(
    *,
    title: str,
    audience: str = "",
    hook: str = "",
    ending_hook: str = "",
    style: str = "",
    platform: str = "",
    episode_number: int | None = None,
    episode_count: int | None = None,
    target_seconds: int | None = None,
    publish_goal: str = "",
    source: str = "USER_INPUT",
) -> dict[str, Any]:
    """Build a versioned, provider-independent creative brief."""
    required_values = {"audience": audience, "hook": hook, "ending_hook": ending_hook, "style": style}
    brief = {
        "schema": "ace.video_kingdom.creator_brief.v1",
        "status": "READY" if all(_text(required_values[field]) for field in BRIEF_REQUIRED) else "PENDING",
        "source": _text(source) or "USER_INPUT",
        "title": _text(title) or "未命名短剧",
        "platform": _text(platform) or "UNSPECIFIED",
        "audience": _text(audience),
        "episode_number": episode_number,
        "episode_count": episode_count,
        "target_seconds": target_seconds,
        "hook": _text(hook),
        "ending_hook": _text(ending_hook),
        "style": _text(style),
        "publish_goal": _text(publish_goal),
    }
    return brief


def validate_creator_brief(brief: dict[str, Any], *, require_ready: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(brief, dict):
        errors.append("creator brief must be an object")
        brief = {}
    if brief.get("schema") != "ace.video_kingdom.creator_brief.v1":
        errors.append("creator brief schema is invalid")
    for field in BRIEF_REQUIRED:
        if not _text(brief.get(field)):
            errors.append(f"creator brief missing {field}")
    if brief.get("episode_number") is not None and (not isinstance(brief.get("episode_number"), int) or brief["episode_number"] < 1):
        errors.append("episode_number must be a positive integer")
    if brief.get("episode_count") is not None and (not isinstance(brief.get("episode_count"), int) or brief["episode_count"] < 1):
        errors.append("episode_count must be a positive integer")
    if brief.get("target_seconds") is not None and (not isinstance(brief.get("target_seconds"), int) or brief["target_seconds"] < 1):
        errors.append("target_seconds must be a positive integer")
    if require_ready and errors:
        return {"schema": "ace.video_kingdom.creator_brief_conformance.v1", "status": "FAIL", "verdict": "BLOCKED", "errors": errors}
    return {
        "schema": "ace.video_kingdom.creator_brief_conformance.v1",
        "status": "PASS" if not errors else "PENDING",
        "verdict": "PASS" if not errors else "REVIEW_REQUIRED",
        "errors": errors,
        "required_fields": list(BRIEF_REQUIRED),
    }


def build_publish_recap(*, project_id: str, brief: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a feedback record without granting production authority."""
    return {
        "schema": "ace.video_kingdom.publish_recap.v1",
        "project_id": project_id,
        "status": "PENDING",
        "authority": "NEXT_ITERATION_INPUT_ONLY",
        "delivery_approval": "NOT_AUTHORIZED",
        "brief_snapshot": {
            "title": _text((brief or {}).get("title")),
            "platform": _text((brief or {}).get("platform")),
            "audience": _text((brief or {}).get("audience")),
        },
        "metrics": {
            "impressions": None,
            "views": None,
            "completion_rate": None,
            "average_watch_seconds": None,
            "first_drop_off_seconds": None,
        },
        "qualitative": {
            "hook_verified": None,
            "ending_hook_verified": None,
            "confusing_beats": [],
            "audience_comments": [],
        },
        "next_iteration": {
            "keep": [],
            "change": [],
            "test": [],
        },
    }


def load_creator_brief(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"creator brief is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("creator brief must be a JSON object")
    return value
