from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import ProductionControl, WorkflowError
from .workflow import bootstrap, lock_plan_shots, preflight_plan


def _scope_from_args(args: argparse.Namespace) -> dict | list[str] | None:
    if getattr(args, "scope_file", None):
        try:
            value = json.loads(args.scope_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"JSON_INPUT_INVALID:{args.scope_file}:{exc}") from exc
        if not isinstance(value, (dict, list)):
            raise WorkflowError(f"JSON_SCOPE_INPUT_INVALID:{args.scope_file}")
        return value
    shot_ids = list(getattr(args, "shot_id", None) or [])
    if shot_ids:
        return {
            "kind": "SHOT_SUBSET",
            "shot_ids": shot_ids,
            "active_shot_id": args.active_shot or shot_ids[0],
        }
    return None


def _add_scope_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scope-file", type=Path)
    parser.add_argument("--shot-id", action="append")
    parser.add_argument("--active-shot")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed video production control plane")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("run_path", type=Path)
    init.add_argument("--run-id")
    init.add_argument("--mode", choices=("PRODUCTION", "SANDBOX"), default="PRODUCTION")
    init.add_argument("--root", type=Path)
    _add_scope_args(init)
    preflight = sub.add_parser("preflight")
    preflight.add_argument("plan_path", type=Path)
    preflight.add_argument("--mode", choices=("PRODUCTION", "SANDBOX"), default="PRODUCTION")
    _add_scope_args(preflight)
    bootstrap_cmd = sub.add_parser("bootstrap")
    bootstrap_cmd.add_argument("plan_path", type=Path)
    bootstrap_cmd.add_argument("run_path", type=Path)
    bootstrap_cmd.add_argument("--mode", choices=("PRODUCTION", "SANDBOX"), default="PRODUCTION")
    _add_scope_args(bootstrap_cmd)
    lock_plan = sub.add_parser("lock-plan-shots")
    lock_plan.add_argument("run_path", type=Path)
    lock_plan.add_argument("plan_path", type=Path)
    _add_scope_args(lock_plan)
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
    close = sub.add_parser("close")
    close.add_argument("run_path", type=Path)
    close.add_argument("manifest", type=Path, help="closure manifest JSON; stored in the existing run receipt")
    advance = sub.add_parser("advance-active-shot")
    advance.add_argument("run_path", type=Path)
    advance.add_argument("next_shot_id")
    expand = sub.add_parser("expand-scope")
    expand.add_argument("run_path", type=Path)
    expand.add_argument("next_shot_id")
    verify_frame = sub.add_parser("verify-frame-proof")
    verify_frame.add_argument("run_path", type=Path)
    verify_frame.add_argument("take_id")
    continuity_evidence = sub.add_parser("update-continuity-evidence")
    continuity_evidence.add_argument("run_path", type=Path)
    continuity_evidence.add_argument("edge_id")
    continuity_evidence.add_argument("previous_take_id")
    continuity_evidence.add_argument("current_take_id")
    owner = sub.add_parser("assign-owner")
    owner.add_argument("run_path", type=Path)
    owner.add_argument("owner")
    owner.add_argument("action_id")
    owner.add_argument("--executor-kind", default="external_provider")
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight_plan(
                args.plan_path,
                mode=args.mode,
                scope=_scope_from_args(args),
            )
        elif args.command == "bootstrap":
            result = bootstrap(
                args.plan_path,
                args.run_path,
                mode=args.mode,
                scope=_scope_from_args(args),
            )
        elif args.command == "init":
            scope = _scope_from_args(args)
            run = ProductionControl.create(
                args.run_path,
                run_id=args.run_id,
                mode=args.mode,
                root=args.root,
                scope=scope if isinstance(scope, dict) else None,
            )
            result = run.snapshot()
        else:
            run = ProductionControl(args.run_path)
            if args.command == "lock-plan-shots":
                result = lock_plan_shots(
                    args.run_path,
                    args.plan_path,
                    scope=_scope_from_args(args),
                )
            elif args.command == "advance-active-shot":
                result = run.advance_active_shot(args.next_shot_id)
            elif args.command == "expand-scope":
                result = run.expand_scope(args.next_shot_id)
            elif args.command == "verify-frame-proof":
                result = run.verify_frame_proof(args.take_id)
            elif args.command == "update-continuity-evidence":
                result = run.update_continuity_evidence(
                    args.edge_id,
                    previous_take_id=args.previous_take_id,
                    current_take_id=args.current_take_id,
                )
            elif args.command == "assign-owner":
                result = run.assign_execution_owner(
                    owner=args.owner,
                    action_id=args.action_id,
                    executor_kind=args.executor_kind,
                )
            elif args.command == "status":
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
            elif args.command == "close":
                result = run.close_run(manifest=_json_file(args.manifest))
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
