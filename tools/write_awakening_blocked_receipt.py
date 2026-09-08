from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    run_path = root / ".control" / "production_run.json"
    provider_manifest = root / "provider_execution" / "manifest.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    manifest = json.loads(provider_manifest.read_text(encoding="utf-8"))
    receipt = {
        "schema": "video_kingdom.handoff_recovery_receipt.v1",
        "status": "BLOCKED",
        "run_id": run["run_id"],
        "episode_id": run.get("episode_id"),
        "request_id": run.get("request_id"),
        "request_hash": run.get("request_hash"),
        "executor_thread_id": run.get("executor_thread_id"),
        "current_stage": run.get("stage"),
        "asset_gate": run.get("asset_gate", {}).get("status"),
        "confirmed_facts": [
            "new asset-first package exists before this Run",
            "asset gate READY with four hashed non-placeholder anchors",
            "five continuity bridges READY",
            "six shots locked and six generation requests admitted",
            "S01 and S02 each have one real Provider COMPLETED receipt and video_id",
            "S01/S02 media are playable vertical MP4 with audio and artifact hashes",
        ],
        "unconfirmed_facts": [
            "full six-shot continuity",
            "director-level creative acceptance",
            "selected take and assembly",
            "final acceptance and delivery authorization",
        ],
        "provider_evidence": [
            {"shot_id": row.get("shot_id"), "status": row.get("status"), "video_id": row.get("video_id"), "request_hash": row.get("request_hash"), "artifact_sha256": row.get("artifact_sha256"), "manifest_sha256": digest(provider_manifest)}
            for row in manifest if isinstance(row, dict)
        ],
        "blocking_point": "QC_BLOCKED: continuity and director layers remain UNKNOWN for S01/S02; no downstream promotion is permitted.",
        "visual_qc_observations": [
            "S01 frame spot-check: female Shenqi identity, dark teal jacket, cream shirt, archive aisle stable; media probe PASS.",
            "S02 frame spot-check: generated subject presents as a different male identity and framing, so continuity/director cannot be promoted; this is a confirmed creative continuity failure, not a transport failure.",
        ],
        "next_action": "Resolve the single provider-reference boundary: provide an approved public reference/upload adapter for the hashed character and prop anchors, then create a new bounded S02 repair admission; do not generate S03-S06 until identity continuity is proven.",
        "retry_policy": "No duplicate S01/S02 create; resume only by existing video_id or proceed to ungenerated shot IDs.",
    }
    out = root / ".control" / "handoff_recovery_receipt.v1.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "BLOCKED", "path": str(out), "run_id": run["run_id"], "next_action": receipt["next_action"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
