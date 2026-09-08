from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import ProductionControl, WorkflowError
from .workflow import preflight_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed video production control plane")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("run_path", type=Path)
    init.add_argument("--run-id")
    init.add_argument("--mode", choices=("PRODUCTION", "SANDBOX"), default="PRODUCTION")
    init.add_argument("--root", type=Path)
    preflight = sub.add_parser("preflight")
    preflight.add_argument("plan_path", type=Path)
    preflight.add_argument("--mode", choices=("PRODUCTION", "SANDBOX"), default="PRODUCTION")
    status = sub.add_parser("status")
    status.add_argument("run_path", type=Path)
    verify = sub.add_parser("verify")
    verify.add_argument("run_path", type=Path)
    asset = sub.add_parser("asset")
    asset.add_argument("run_path", type=Path)
    asset.add_argument("asset_id")
    asset.add_argument("path")
    asset.add_argument("--sha256")
    asset.add_argument("--role", default="")
    asset.add_argument("--optional", action="store_true")
    continuity = sub.add_parser("continuity")
    continuity.add_argument("run_path", type=Path)
    continuity.add_argument("edge_id")
    continuity.add_argument("from_shot")
    continuity.add_argument("to_shot")
    continuity.add_argument("evidence_path")
    continuity.add_argument("--sha256")
    gate = sub.add_parser("asset-gate")
    gate.add_argument("run_path", type=Path)
    bind = sub.add_parser("bind-receipt")
    bind.add_argument("run_path", type=Path)
    bind.add_argument("receipt_path")
    shot = sub.add_parser("lock-shot")
    shot.add_argument("run_path", type=Path)
    shot.add_argument("shot_id")
    shot.add_argument("contract", type=Path)
    admit = sub.add_parser("admit")
    admit.add_argument("run_path", type=Path)
    admit.add_argument("shot_id")
    admit.add_argument("request", type=Path)
    admit.add_argument("--resume-video-id")
    admit.add_argument("--revision-of", help="prior request_hash; required when changing an admitted request")
    generation = sub.add_parser("generation")
    generation.add_argument("run_path", type=Path)
    generation.add_argument("shot_id")
    generation.add_argument("take_id")
    generation.add_argument("video_id")
    generation.add_argument("artifact_path")
    generation.add_argument("--metadata", type=Path)
    qc = sub.add_parser("qc")
    qc.add_argument("run_path", type=Path)
    qc.add_argument("take_id")
    qc.add_argument("layers", type=Path)
    qc.add_argument("--notes", default="")
    select = sub.add_parser("select")
    select.add_argument("run_path", type=Path)
    select.add_argument("shot_id")
    select.add_argument("take_id")
    assembly = sub.add_parser("assembly")
    assembly.add_argument("run_path", type=Path)
    assembly.add_argument("artifact_path")
    assembly.add_argument("ordered_shots", nargs="+")
    delivery = sub.add_parser("delivery")
    delivery.add_argument("run_path", type=Path)
    delivery.add_argument("--path")
    delivered = sub.add_parser("delivered")
    delivered.add_argument("run_path", type=Path)
    delivered.add_argument("destination")
    delivered.add_argument("--authorized", action="store_true", help="explicitly confirm the destination is authorized")
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight_plan(args.plan_path, mode=args.mode)
        elif args.command == "init":
            run = ProductionControl.create(args.run_path, run_id=args.run_id, mode=args.mode, root=args.root)
            result = run.snapshot()
        else:
            run = ProductionControl(args.run_path)
            if args.command == "status":
                result = run.snapshot()
            elif args.command == "verify":
                result = run.verify_event_chain()
            elif args.command == "asset":
                result = run.register_asset(args.asset_id, args.path, required=not args.optional, expected_sha256=args.sha256, role=args.role)
            elif args.command == "continuity":
                result = run.register_continuity(args.edge_id, from_shot=args.from_shot, to_shot=args.to_shot, evidence_path=args.evidence_path, expected_sha256=args.sha256)
            elif args.command == "asset-gate":
                result = run.evaluate_asset_gate()
            elif args.command == "bind-receipt":
                result = run.bind_asset_gate_receipt(args.receipt_path)
            elif args.command == "lock-shot":
                result = run.lock_shot(args.shot_id, _json_file(args.contract))
            elif args.command == "admit":
                result = run.admit_generation(args.shot_id, _json_file(args.request), resume_video_id=args.resume_video_id, revision_of=args.revision_of)
            elif args.command == "generation":
                result = run.record_generation(args.shot_id, args.take_id, video_id=args.video_id, artifact_path=args.artifact_path, metadata=_json_file(args.metadata) if args.metadata else {})
            elif args.command == "qc":
                result = run.record_qc(args.take_id, _json_file(args.layers), notes=args.notes)
            elif args.command == "select":
                result = run.select_take(args.shot_id, args.take_id)
            elif args.command == "assembly":
                result = run.record_assembly(args.artifact_path, ordered_shots=args.ordered_shots)
            elif args.command == "delivery":
                result = run.promote_delivery(args.path)
            else:
                result = run.mark_delivered(destination=args.destination, authorized=args.authorized)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except WorkflowError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


def _json_file(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"JSON_INPUT_INVALID:{path}:{exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"JSON_INPUT_MUST_BE_OBJECT:{path}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
