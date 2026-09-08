"""Check that a short-drama shot plan contains distinct visual actions.

The provider can preserve a character while still producing the same sigh or
head turn in every clip.  This deterministic gate requires each shot to state
an action arc (start/action/end) and flags near-duplicate arcs before any API
call.  It is a planning check, not a claim about rendered visual quality.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

WORD_RE = re.compile(r"[A-Za-z0-9_\u4e00-\u9fff]+")
GENERIC = {"wenji", "vertical", "cinematic", "natural", "motion", "preserve", "same", "exact", "one", "person", "scene", "anchor"}


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in WORD_RE.findall(text) if token.lower() not in GENERIC and len(token) > 1}


def validate(plan: dict, *, duplicate_threshold: float = 0.7) -> dict:
    shots = plan.get("shots") if isinstance(plan.get("shots"), list) else []
    errors: list[str] = []
    warnings: list[str] = []
    signatures: list[tuple[str, set[str]]] = []
    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            errors.append(f"shot {index}: must be an object")
            continue
        shot_id = str(shot.get("shot_id") or f"shot_{index}")
        beats = shot.get("action_beats")
        if not isinstance(beats, list) or len(beats) != 3 or not all(isinstance(item, str) and item.strip() for item in beats):
            errors.append(f"{shot_id}: declare exactly three action_beats [start, action, end]")
            continue
        signature_text = " | ".join(beats)
        tokens = _tokens(signature_text)
        if len(tokens) < 2:
            errors.append(f"{shot_id}: action_beats are too vague to distinguish motion")
        signatures.append((shot_id, tokens))
    for index, (left_id, left) in enumerate(signatures):
        for right_id, right in signatures[index + 1:]:
            union = left | right
            similarity = len(left & right) / len(union) if union else 1.0
            if similarity >= duplicate_threshold:
                warnings.append(f"{left_id} and {right_id}: action signatures overlap {similarity:.2f}; vary movement, prop or camera purpose")
    return {"status": "VALID" if not errors else "INVALID", "shot_count": len(shots),
            "errors": errors, "warnings": warnings, "duplicate_threshold": duplicate_threshold}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        result = validate(plan)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        result = {"status": "INVALID", "shot_count": 0, "errors": [str(exc)], "warnings": []}
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["status"] == "VALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
