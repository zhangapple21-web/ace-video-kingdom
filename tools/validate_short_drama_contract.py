"""Validate the minimum asset and continuity contract before a short-drama run."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_short_drama_contract.py CONTRACT.json")
        return 2
    document = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    required = {"project_id", "status", "assets", "shots", "acceptance"}
    missing = sorted(required - set(document))
    failures: list[str] = []
    if missing:
        failures.append("missing top-level keys: " + ", ".join(missing))
    assets = document.get("assets", {})
    for group in ("characters", "scenes", "props"):
        if not assets.get(group):
            failures.append(f"missing {group} reference assets")
    for shot in document.get("shots", []):
        for field in ("required_asset_ids", "first_state", "action", "last_state", "continuity_bridge_to_next", "quality_gate"):
            if not shot.get(field):
                failures.append(f"{shot.get('shot_id', 'unknown')} missing {field}")
    if document.get("production_integration") is not False:
        failures.append("production_integration must remain false")
    if failures:
        print("INVALID")
        print("\n".join(failures))
        return 1
    print(f"VALID project={document['project_id']} shots={len(document['shots'])} production_integration=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
