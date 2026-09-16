"""Small, lossless semantic frame for ACE ingress requests.

This is deliberately not a pretend LLM interpreter.  It preserves the user's
wording, extracts only explicit constraints, and marks ambiguity instead of
silently inventing missing story facts.  Provider prompts may be richer, but
the control plane always carries this frame so model selection cannot erase
the request's meaning.
"""
from __future__ import annotations

import re
from typing import Any


_CONSTRAINT_RE = re.compile(r"(?:必须|务必|需要|不要|禁止|不能|不许|仅限|只用|优先|不得)[^，。；;!?！？\n]{1,80}")
_AMBIGUITY_RE = re.compile(r"(?:也许|可能|大概|似乎|等等|之类|什么的|随便|看着办|自行判断|不确定|没说清)")


def build_semantic_context(text: str) -> dict[str, Any]:
    """Build a deterministic, fail-closed context packet from user text."""
    raw = str(text or "").strip()
    normalized = re.sub(r"\s+", " ", raw)
    constraints = [match.group(0).strip() for match in _CONSTRAINT_RE.finditer(normalized)]
    constraints = list(dict.fromkeys(constraints))
    ambiguity_hits = list(dict.fromkeys(_AMBIGUITY_RE.findall(normalized)))
    return {
        "schema": "ace.semantic_context.v1",
        "raw_request": raw,
        "normalized_request": normalized,
        "explicit_constraints": constraints,
        "ambiguity_signals": ambiguity_hits,
        "interpretation_status": "NEEDS_CONTEXT_REVIEW" if ambiguity_hits else "EXPLICIT_ONLY",
        "inferred_facts": [],
        "meaning_policy": "preserve_goal_and_constraints; never promote_inference_to_fact",
    }
