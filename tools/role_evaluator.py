"""Deterministic, provider-agnostic checks for role-room candidate text."""

from __future__ import annotations

import re
from typing import Any

from tools.repetition_sentinel import find_repeated_text_blocks


PLACEHOLDER_RE = re.compile(r"(?:\bTODO\b|\bFIXME\b|<\s*TODO\s*>|\[\s*待补\s*\]|占位符)", re.IGNORECASE)
SUBMISSION_RE = re.compile(r"(?:直接提交(?:图像|视频)|调用(?:图像|视频)接口|绕过验收)")


def evaluate_role_output(role_id: str, text: str) -> dict[str, Any]:
    value = str(text or "").strip()
    if value.casefold() in {"none", "null", "undefined"}:
        value = ""
    repeated_blocks = find_repeated_text_blocks(value)
    checks = [
        {"name": "non_empty", "passed": bool(value)},
        {"name": "no_placeholder", "passed": not bool(PLACEHOLDER_RE.search(value))},
        {"name": "no_provider_submission", "passed": not bool(SUBMISSION_RE.search(value))},
        {"name": "no_repeated_block", "passed": not bool(repeated_blocks)},
    ]
    failed = [item["name"] for item in checks if not item["passed"]]
    return {
        "role_id": role_id,
        "status": "PASS" if not failed else "FAIL",
        "score": round(sum(1 for item in checks if item["passed"]) / len(checks), 3),
        "checks": checks,
        "repetition": {"status": "PASS" if not repeated_blocks else "REVIEW_REQUIRED", "findings": repeated_blocks},
        "failure_class": failed[0] if failed else None,
        "repair_hint": "重新生成候选稿并去除占位符/接口提交动作/重复大段" if failed else None,
    }
