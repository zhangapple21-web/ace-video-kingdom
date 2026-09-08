"""Run one or more controlled Shot Core pilot requests through Agnes Flash."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.shot_core import load_manifest, run_take


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--shot-id", action="append", help="run only these shot IDs; repeat")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--parent-take-id")
    parser.add_argument("--branch-reason")
    parser.add_argument("--prompt-suffix", default="", help="bounded prompt revision for a rework branch")
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    shots = fixture.get("shots", [])
    selected = set(args.shot_id or [shot["shot_id"] for shot in shots])
    results = []
    for shot in shots:
        if shot["shot_id"] not in selected:
            continue
        if args.prompt_suffix:
            shot = {**shot, "prompt": shot.get("prompt", "") + " " + args.prompt_suffix}
        parent = args.parent_take_id if len(selected) == 1 else None
        result = run_take(shot, manifest_path=args.manifest, output_path=args.output_dir / f"{shot['shot_id']}_T{len([t for t in load_manifest(args.manifest).get('takes', []) if t.get('shot_id') == shot['shot_id']]) + 1:02d}.mp4", parent_take_id=parent, branch_reason=args.branch_reason, timeout=args.timeout)
        results.append({k: result.get(k) for k in ("take_id", "shot_id", "video_id", "provider_status", "technical_status", "status", "artifact_path", "artifact_hash", "failure_reason", "media")})
    print(json.dumps({"count": len(results), "results": results}, ensure_ascii=False, indent=2))
    if not results:
        return 2
    # A generated artifact with Creative FAIL is a valid pilot outcome and is
    # intentionally left for director rework. Provider/technical failures are
    # not green: callers must be able to stop a batch or CI run on them.
    if any(row.get("provider_status") != "SUCCESS" or row.get("technical_status") != "PASS" for row in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
