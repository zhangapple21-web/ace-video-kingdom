"""Deterministic secret/PII scan used before prompts and media submission."""
from __future__ import annotations

import re
from typing import Any


_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("private_key", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "HIGH"),
    ("bearer_token", r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}", "HIGH"),
    ("api_key_assignment", r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|cookie)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=:-]{12,}", "HIGH"),
    ("openai_key", r"\bsk-(?:or-v1-)?[A-Za-z0-9_-]{20,}", "HIGH"),
    ("github_token", r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}", "HIGH"),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b", "HIGH"),
    ("email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "MEDIUM"),
    ("phone_cn", r"(?<!\d)1[3-9]\d{9}(?!\d)", "MEDIUM"),
    ("id_cn", r"(?<!\d)\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?!\d)", "HIGH"),
)
_COMPILED = tuple((kind, re.compile(pattern), severity) for kind, pattern, severity in _PATTERNS)


def _redact(value: str) -> str:
    value = value.strip().replace("\n", " ")
    if len(value) <= 8:
        return "<redacted>"
    return f"{value[:3]}…{value[-3:]}"


def _walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def scan_value(value: Any) -> dict[str, Any]:
    """Return findings without returning raw secrets or PII."""
    findings: list[dict[str, Any]] = []
    for path, text in _walk(value):
        for kind, pattern, severity in _COMPILED:
            for match in pattern.finditer(text):
                findings.append({
                    "kind": kind,
                    "severity": severity,
                    "path": path,
                    "redacted": _redact(match.group(0)),
                })
    # One finding per kind/path/value keeps receipts deterministic and avoids
    # leaking repeated copies of the same sensitive string.
    unique = {(item["kind"], item["path"], item["redacted"]): item for item in findings}
    findings = list(unique.values())
    findings.sort(key=lambda item: (item["path"], item["kind"]))
    return {
        "schema": "ace.video_kingdom.privacy_scan.v1",
        "status": "BLOCKED_PRIVACY" if findings else "PASS",
        "finding_count": len(findings),
        "findings": findings,
    }
