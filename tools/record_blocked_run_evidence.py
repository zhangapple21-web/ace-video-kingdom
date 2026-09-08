from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.provider_admission import admit_provider_request, build_canonical_generation_request, canonical_hash, delivery_gate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--run-path", type=Path, required=True)
    parser.add_argument("--executor-thread-id", required=True)
    args = parser.parse_args()

    project = args.project_dir.resolve()
    run_path = args.run_path.resolve()
    plan_path = project / "episode_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    run = json.loads(run_path.read_text(encoding="utf-8"))
    pipeline_receipt_path = project / "pipeline_receipt.json"
    pipeline_receipt = json.loads(pipeline_receipt_path.read_text(encoding="utf-8")) if pipeline_receipt_path.is_file() else {}
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    run_id = str(run["run_id"])
    project_id = str(plan.get("project_id") or project.name)
    episode_id = f"{project_id}-episode-001"
    shot_ids = [str(row.get("shot_id")) for row in plan.get("shots", []) if isinstance(row, dict) and row.get("shot_id")]
    demand = {
        "goal": "PRODUCE",
        "idea": pipeline_receipt.get("idea") or plan.get("title"),
        "project_id": project_id,
        "episode_id": episode_id,
        "target_seconds": plan.get("dynamic_content_plan", {}).get("target_seconds"),
        "plan_sha256": sha256_file(plan_path),
    }
    request_hash = canonical_hash(demand)
    request_id = f"req_{request_hash[:24]}"
    idempotency_key = f"{run_id}:{request_hash[:20]}"
    control_dir = project / ".control"

    identity = {
        "schema": "video_kingdom.production_run_identity_receipt.v1",
        "status": "BOUND",
        "run_id": run_id,
        "episode_id": episode_id,
        "project_id": project_id,
        "shot_ids": shot_ids,
        "request_id": request_id,
        "request_hash": request_hash,
        "executor_thread_id": args.executor_thread_id,
        "executor_role": "short_drama_production_executor",
        "control_plane_version": run.get("schema"),
        "created_at": now,
        "parent_run_id": None,
        "idempotency_key": idempotency_key,
        "root": str(project),
        "production_run_sha256_at_binding": sha256_file(run_path),
        "stage_at_binding": run.get("stage"),
        "identity_rule": "new_run_only; no historical artifact reuse",
    }
    write_json(control_dir / "run_identity_receipt.v1.json", identity)

    first = next((row for row in plan.get("shots", []) if isinstance(row, dict) and row.get("shot_id")), None)
    if first is None:
        raise SystemExit("no shot in plan")
    render = first.get("render") if isinstance(first.get("render"), dict) else {}
    payload = {
        "model": render.get("model", "agnes-video-v2.0"),
        "prompt": first.get("prompt", ""),
        "negative_prompt": render.get("negative_prompt", ""),
        "duration": render.get("seconds"),
        "size": f"{render.get('width', 704)}x{render.get('height', 1280)}",
        "image": render.get("image"),
        "request_id": request_id,
        "idempotency_key": idempotency_key,
    }
    shot = dict(first)
    shot["episode_id"] = episode_id
    shot["reference_assets"] = list(first.get("required_asset_ids") or [])
    canonical = build_canonical_generation_request(
        shot,
        payload,
        provider="agnes",
        endpoint="https://apihub.agnes-ai.com/v1/videos",
        payload_schema="agnes-video-cli.v1",
        model=str(payload["model"]),
        scope="production",
        request_kind="shot",
    )
    canonical_path = control_dir / "canonical_generation_request_S01A.v1.json"
    write_json(canonical_path, {
        "schema": "video_kingdom.pending_generation_request_receipt.v1",
        "status": "PENDING_NOT_ADMITTED",
        "run_id": run_id,
        "episode_id": episode_id,
        "shot_id": first.get("shot_id"),
        "request_id": request_id,
        "request_hash": canonical_hash(canonical),
        "canonical_request": canonical,
        "created_at": now,
        "provider_post": "NOT_CALLED_ASSET_GATE_BLOCKED",
    })
    admission = admit_provider_request(
        canonical,
        contract_status="ASSET_GATE_BLOCKED",
        contract_errors=["ASSET_GATE_BLOCKED", "CONTINUITY_GATE_BLOCKED", "SHOT_LOCK_NOT_RUN"],
        receipt_path=control_dir / "admission_receipt_S01A.v1.json",
    )
    admission["run_id"] = run_id
    admission["episode_id"] = episode_id
    admission["request_id"] = request_id
    admission["provider_post"] = "NOT_CALLED"
    write_json(control_dir / "admission_receipt_S01A.v1.json", admission)

    blocked_reason = "ASSET_GATE_BLOCKED: 10 placeholder assets and 5 missing continuity edges"
    write_json(control_dir / "artifact_manifest.v1.json", {
        "schema": "video_kingdom.artifact_manifest.v1",
        "status": "BLOCKED",
        "run_id": run_id,
        "episode_id": episode_id,
        "artifacts": [],
        "reason": blocked_reason,
        "provider_called": False,
        "created_at": now,
    })
    write_json(control_dir / "qc_receipt.v1.json", {
        "schema": "video_kingdom.qc_receipt.v1",
        "status": "NOT_RUN",
        "run_id": run_id,
        "reason": blocked_reason,
        "layers": {"picture": "NOT_RUN", "motion": "NOT_RUN", "camera": "NOT_RUN", "continuity": "BLOCKED", "director": "NOT_RUN"},
        "created_at": now,
    })
    write_json(control_dir / "selected_take_receipt.v1.json", {"schema": "video_kingdom.selected_take_receipt.v1", "status": "NOT_RUN", "run_id": run_id, "selected_take": None, "reason": blocked_reason, "created_at": now})
    write_json(control_dir / "assembly_receipt.v1.json", {"schema": "video_kingdom.assembly_receipt.v1", "status": "NOT_RUN", "run_id": run_id, "artifact": None, "reason": blocked_reason, "created_at": now})
    write_json(control_dir / "final_acceptance_receipt.v1.json", {"schema": "video_kingdom.final_acceptance_receipt.v1", "status": "BLOCKED", "run_id": run_id, "delivery_approved": False, "reason": blocked_reason, "created_at": now})

    gate = delivery_gate({
        "asset_gate": "BLOCKED",
        "continuity_gate": "BLOCKED",
        "shot_lock": "NOT_RUN",
        "admission": "REJECTED",
        "provider": "NOT_CALLED",
        "artifact": "NOT_PROVEN",
        "qc": "NOT_RUN",
        "selected_take": "NOT_RUN",
        "assembly": "NOT_RUN",
        "acceptance": "BLOCKED",
    })
    write_json(control_dir / "delivery_gate.v1.json", {"schema": "video_kingdom.delivery_gate_receipt.v1", "run_id": run_id, "episode_id": episode_id, "request_id": request_id, "created_at": now, **gate})

    write_json(control_dir / "handoff_recovery_receipt.v1.json", {
        "schema": "video_kingdom.handoff_recovery_receipt.v1",
        "status": "BLOCKED",
        "run_id": run_id,
        "episode_id": episode_id,
        "request_id": request_id,
        "request_hash": request_hash,
        "executor_thread_id": args.executor_thread_id,
        "handoff_from": args.executor_thread_id,
        "handoff_to": "next_authorized_executor",
        "handoff_at": now,
        "committed_event": run.get("events", [])[-1] if run.get("events") else None,
        "current_state": run.get("stage"),
        "completed_stages": ["demand_parse", "episode_plan", "asset_preflight", "continuity_preflight"],
        "incomplete_stages": ["asset_gate_ready", "shot_lock", "provider_admission", "provider_execution", "artifact", "qc", "selected_take", "assembly", "final_acceptance", "delivery_gate_pass"],
        "last_provider_call": {"status": "NOT_CALLED", "side_effect_possible": False},
        "generated_artifacts": [],
        "locks_and_leases": run.get("execution"),
        "confirmed_facts": ["run_id is unique for this new project root", "event chain is valid", "all required generated assets are placeholders", "five continuity edges have no evidence files", "no Provider POST was made"],
        "unconfirmed_facts": ["Provider behavior", "video_id", "artifact hash", "QC", "assembly", "acceptance"],
        "next_action": "supply fresh non-placeholder assets and five continuity bridge evidence files, then rerun the formal asset-gate; do not submit a Provider request before READY",
        "recoverable": True,
        "retry_allowed": False,
        "human_confirmation_required": "only if fresh asset generation requires a new external Provider call",
    })
    print(json.dumps({"status": "BLOCKED", "run_id": run_id, "episode_id": episode_id, "request_id": request_id, "request_hash": request_hash, "control_dir": str(control_dir)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
