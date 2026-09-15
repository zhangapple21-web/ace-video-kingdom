"""Turn role-room failures into reviewable, non-authoritative experience proposals."""

from __future__ import annotations

from typing import Any


def build_feedback_proposals(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    trace_id = receipt.get("trace_id")
    for role in receipt.get("roles", []) if isinstance(receipt.get("roles"), list) else []:
        if not isinstance(role, dict):
            continue
        role_id = str(role.get("role_id") or "unknown")
        for attempt in role.get("attempts", []) if isinstance(role.get("attempts"), list) else []:
            if not isinstance(attempt, dict) or attempt.get("status") == "PASS":
                continue
            evaluation = attempt.get("evaluation") if isinstance(attempt.get("evaluation"), dict) else {}
            failure_class = str(evaluation.get("failure_class") or "provider_failure")
            model = str(attempt.get("actual_model") or attempt.get("model") or "unknown")
            proposals.append(
                {
                    "pattern_id": f"role_room_{role_id}_{failure_class}",
                    "status": "PROPOSED",
                    "authority": "REVIEW_REQUIRED",
                    "role_id": role_id,
                    "model": model,
                    "failure_class": failure_class,
                    "lesson": f"角色 {role_id} 使用 {model} 时出现 {failure_class}；下一轮应先执行同类检查并保留降级记录。",
                    "evidence": {"trace_id": trace_id, "span_id": role.get("span_id")},
                }
            )
    return proposals
