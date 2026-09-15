"""Validate the OneAPI role-room receipt required before production."""

from __future__ import annotations

from typing import Any


STANDARD_ROLES = {
    "primary_writer",
    "storyboarder",
    "contrarian_auditor",
    "continuity_editor",
    "director_convergence",
}
FULL_AUDIT_ROLES = {
    "outline_structurer",
    "ideation_branch",
    "primary_writer",
    "storyboarder",
    "contrarian_auditor",
    "reality_reviewer",
    "continuity_editor",
    "format_editor",
    "director_convergence",
    "arbiter",
}


def validate_role_audit(receipt: dict[str, Any], *, minimum_profile: str = "standard") -> dict[str, Any]:
    """Return PASS only when the required role seats completed successfully."""

    errors: list[str] = []
    if receipt.get("schema") != "video_kingdom.oneapi_role_room.v2":
        errors.append("role audit schema must be video_kingdom.oneapi_role_room.v2")
    profile = str(receipt.get("profile") or "")
    if profile not in {"standard", "full_audit"}:
        errors.append("production requires standard or full_audit role profile")
    if receipt.get("status") != "COMPLETED":
        errors.append(f"role audit status must be COMPLETED, got {receipt.get('status') or 'missing'}")
    if receipt.get("production_submission") != "NOT_PERFORMED":
        errors.append("role audit receipt must prove production_submission=NOT_PERFORMED")

    required = FULL_AUDIT_ROLES if profile == "full_audit" else STANDARD_ROLES
    rows = receipt.get("roles") if isinstance(receipt.get("roles"), list) else []
    by_id = {str(row.get("role_id")): row for row in rows if isinstance(row, dict)}
    for role_id in sorted(required):
        row = by_id.get(role_id)
        if row is None:
            errors.append(f"role audit missing required seat {role_id}")
            continue
        if row.get("status") != "COMPLETED":
            errors.append(f"role audit seat {role_id} is not COMPLETED")
        evaluation = row.get("evaluation") if isinstance(row.get("evaluation"), dict) else {}
        if evaluation and evaluation.get("status") != "PASS":
            errors.append(f"role audit seat {role_id} evaluation is not PASS")
    return {"status": "PASS" if not errors else "BLOCKED", "errors": errors, "profile": profile, "required_roles": sorted(required)}
