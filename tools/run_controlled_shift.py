"""Execute one explicitly authorized Video Kingdom shift.

This is an entrypoint, not a scheduler or daemon.  It validates the bridge
contract, runs exactly one episode plan through the existing durable runner,
and writes no external publication state.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _validate(plan: dict, bridge: dict) -> None:
    if plan.get("scope") != "FREE_ZONE_RESEARCH_ONLY":
        raise ValueError("shift rejected: plan scope is not FREE_ZONE_RESEARCH_ONLY")
    if plan.get("production_integration") is not False:
        raise ValueError("shift rejected: production_integration must be false")
    if not isinstance(plan.get("shots"), list) or not plan["shots"]:
        raise ValueError("shift rejected: episode has no shots")
    required = bridge.get("rules", {}).get("required_plan_fields", [])
    missing = [field for field in required if field not in plan]
    if missing:
        raise ValueError(f"shift rejected: missing plan fields: {', '.join(missing)}")
    for shot in plan["shots"]:
        render = shot.get("render") if isinstance(shot, dict) else None
        if not isinstance(render, dict):
            raise ValueError(f"shift rejected: shot lacks render contract: {shot}")
        refs = render.get("reference_image_urls")
        if not isinstance(refs, list) or len(refs) != 1 or not str(refs[0]).startswith(("https://", "http://")):
            raise ValueError(f"shift rejected: shot lacks one public scene anchor: {shot.get('shot_id')}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--identity-contract", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--media-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-output", type=Path)
    parser.add_argument("--bridge", type=Path, default=Path("bridges/ace_dedicated_shift_contract.v1.json"))
    args = parser.parse_args()
    try:
        plan = _load(args.episode)
        bridge = _load(args.bridge)
        _validate(plan, bridge)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"status": "SHIFT_REJECTED", "reason": str(error)}, ensure_ascii=False))
        return 2
    command = [sys.executable, "tools/run_comedy_episode.py", "--episode", str(args.episode), "--identity-contract", str(args.identity_contract), "--manifest", str(args.manifest), "--media-dir", str(args.media_dir), "--output", str(args.output)]
    if args.review_output:
        command.extend(["--review-output", str(args.review_output)])
    result = subprocess.run(command)
    print(json.dumps({"status": "SHIFT_COMPLETED" if result.returncode == 0 else "SHIFT_FAILED", "returncode": result.returncode, "episode": str(args.episode)}, ensure_ascii=False))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
