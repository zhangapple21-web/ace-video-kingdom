"""Validate the project-independent creative constraint envelope.

The envelope separates non-negotiable creative invariants from flexible
preferences and deferred work.  Concrete wording belongs to each episode;
this validator only enforces that every production shot carries the same
complete structure.
"""

from __future__ import annotations

from typing import Any


HARD_CATEGORIES = (
    "identity_reference",
    "narrative_order",
    "spatial_relationship",
    "visibility_and_exclusions",
    "performance_and_audio",
)


def _nonempty(value: Any) -> bool:
    return value not in (None, "", [], {})


def validate_creative_constraints(constraints: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(constraints, dict):
        return {"status": "BLOCKED", "errors": ["creative_constraints envelope is required"], "warnings": warnings}

    hard = constraints.get("hard") if isinstance(constraints.get("hard"), dict) else {}
    for category in HARD_CATEGORIES:
        item = hard.get(category)
        if not isinstance(item, dict):
            errors.append(f"hard.{category} is required")
            continue
        if item.get("status") != "LOCKED":
            errors.append(f"hard.{category}.status must be LOCKED")
        rules = item.get("rules")
        if not isinstance(rules, list) or not any(_nonempty(rule) for rule in rules):
            errors.append(f"hard.{category}.rules must contain a concrete rule")

    flexible = constraints.get("flexible") if isinstance(constraints.get("flexible"), dict) else {}
    for key, value in flexible.items():
        if not _nonempty(value):
            warnings.append(f"flexible.{key} is empty")
    deferred = constraints.get("deferred")
    if deferred is None:
        errors.append("deferred list is required; use [] when nothing is deferred")
    elif not isinstance(deferred, list):
        errors.append("deferred must be a list")

    return {
        "status": "PASS" if not errors else "BLOCKED",
        "errors": errors,
        "warnings": warnings,
        "hard_categories": list(HARD_CATEGORIES),
        "deferred_count": len(deferred) if isinstance(deferred, list) else None,
    }
