"""Conservative repetition signals for role-room candidate text."""

from __future__ import annotations

import re
from typing import Any


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])")


def _canonical_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip().casefold()


def _sentence_units(value: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", str(value or "")).strip()
    return [item.strip() for item in _SENTENCE_SPLIT_RE.split(normalized) if item.strip()]


def find_repeated_text_blocks(value: str, *, min_block_chars: int = 40) -> list[dict[str, Any]]:
    """Find only substantial repeated blocks, not intentional short emphasis."""
    source = str(value or "")
    findings: list[dict[str, Any]] = []
    canonical = _canonical_text(source)
    if len(canonical) >= min_block_chars * 2 and len(canonical) % 2 == 0:
        midpoint = len(canonical) // 2
        if canonical[:midpoint] == canonical[midpoint:]:
            findings.append({"kind": "full_text", "block_chars": midpoint, "occurrences": 2})

    paragraphs = [
        _canonical_text(item)
        for item in re.split(r"\n\s*\n", source)
        if _canonical_text(item)
    ]
    for index in range(len(paragraphs) - 1):
        if len(paragraphs[index]) >= min_block_chars and paragraphs[index] == paragraphs[index + 1]:
            findings.append({"kind": "adjacent_paragraph", "paragraph_index": index, "block_chars": len(paragraphs[index]), "occurrences": 2})

    units = [_canonical_text(item) for item in _sentence_units(source)]
    for block_size in (2, 3):
        for start in range(0, len(units) - block_size * 2 + 1):
            left = units[start:start + block_size]
            right = units[start + block_size:start + block_size * 2]
            block_chars = sum(len(item) for item in left)
            if block_chars >= min_block_chars and left == right:
                findings.append({"kind": "adjacent_sentence_block", "unit_index": start, "unit_count": block_size, "block_chars": block_chars, "occurrences": 2})

    unique: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for finding in findings:
        identity = tuple(sorted(finding.items()))
        if identity not in seen:
            seen.add(identity)
            unique.append(finding)
    return unique


__all__ = ["find_repeated_text_blocks"]
