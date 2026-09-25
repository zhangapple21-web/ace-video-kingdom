"""Validate the small creative slice required before episode expansion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_BEATS = ("goal", "obstacle", "reversal")


def validate_creative_slice(value: Any, *, base_dir: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return {"schema": "video_kingdom.creative_slice_validation.v1", "status": "BLOCKED", "errors": ["receipt must be an object"]}
    if value.get("schema") != "video_kingdom.creative_slice.v1":
        errors.append("schema must be video_kingdom.creative_slice.v1")
    if value.get("status") != "PASS":
        errors.append("creative slice status must be PASS before batch expansion")
    beats = value.get("beats") if isinstance(value.get("beats"), dict) else {}
    for field in REQUIRED_BEATS:
        if not str(beats.get(field) or "").strip():
            errors.append(f"beats.{field} is required")
    if not str(value.get("viewer_change") or "").strip():
        errors.append("viewer_change is required")
    evidence = value.get("evidence") if isinstance(value.get("evidence"), dict) else {}
    video = str(evidence.get("video_path") or "").strip()
    if not video:
        errors.append("evidence.video_path is required")
    elif base_dir is not None and not Path(video).is_absolute() and not (base_dir / video).is_file():
        errors.append("evidence.video_path does not exist")
    return {
        "schema": "video_kingdom.creative_slice_validation.v1",
        "status": "PASS" if not errors else "BLOCKED",
        "errors": errors,
        "production_authority": "NONE",
        "batch_expansion_allowed": not errors,
    }


def load_and_validate(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_creative_slice(payload, base_dir=path.parent)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    report = load_and_validate(args.input)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 2)
