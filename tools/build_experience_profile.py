"""Build a deterministic capability/failure profile from existing shot receipts.

No provider is called. The profile is evidence, not an automatic routing or
production decision.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def _rows(root: Path):
    for path in sorted((root / "experiments").glob("*tasks*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for row in (value if isinstance(value, list) else [value]):
            if isinstance(row, dict) and row.get("shot_id"):
                yield path.name, row


def _cause(row: dict) -> str:
    text = " ".join(str(row.get(k, "")) for k in ("error_body_excerpt", "quality_reason", "error"))
    low = text.lower()
    if re.search(r"face|hand|drift|visual|artifact|render|provider|timeout|503|429", low):
        return "generation_or_provider"
    if re.search(r"subtitle|audio|caption|sync|edit|concat", low):
        return "edit_or_audio"
    if re.search(r"continuity|prop|state|scene|causal|story|prompt", low):
        return "planning_or_continuity"
    return "unknown"


def build(root: Path) -> dict:
    models = defaultdict(Counter)
    failures = Counter()
    total = 0
    for _, row in _rows(root):
        total += 1
        model = str(row.get("model_id") or "unknown")
        status = str(row.get("status") or "UNKNOWN").upper()
        models[model]["completed" if status == "COMPLETED" else "non_completed"] += 1
        if status != "COMPLETED":
            failures[_cause(row)] += 1
    return {
        "contract_version": "ace.video_kingdom.experience_profile.v1",
        "scope": "FREE_ZONE_RESEARCH_ONLY",
        "production_integration": False,
        "evidence_basis": "existing task manifests only",
        "shot_receipt_count": total,
        "model_summary": {k: dict(v) for k, v in sorted(models.items())},
        "failure_attribution": dict(sorted(failures.items())),
        "promotion": "NONE_AUTOMATIC",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"profiled={result['shot_receipt_count']} promotion=NONE_AUTOMATIC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
