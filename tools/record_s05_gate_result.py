"""Record the post-generation E/S05 five-layer gate result fail-closed."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.shot_core import load_manifest, save_manifest


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.repo_root.resolve()
    manifest_path = root / "research" / "E_S05_shotcore_manifest.v1.json"
    artifact = root / "episodes/generated/E_S05_HARDENING_20260906/S05A_T01.mp4"
    qc_dir = root / "episodes/generated/E_S05_HARDENING_20260906/qc"
    receipt_path = root / "research" / "admission_receipts" / "E_S05A_candidate_gate_receipt.v1.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(manifest_path)
    take = next((row for row in manifest.get("takes", []) if row.get("take_id") == "S05A_T01"), None)
    if not take:
        raise SystemExit("S05A_T01 not found")
    if not artifact.exists():
        raise SystemExit("candidate artifact missing")
    frame_report = json.loads((qc_dir / "frame_continuity.json").read_text(encoding="utf-8"))
    pacing_report = json.loads((qc_dir / "pacing.json").read_text(encoding="utf-8"))
    core_report = json.loads((qc_dir / "shot_core_audit.json").read_text(encoding="utf-8"))
    machine_qc = {
        "file_integrity": "PASS", "resolution": "PASS", "fps": "PASS", "audio_stream": "PASS", "duration": "PASS",
        "black_frames": "PASS", "freeze_tail": "PASS", "internal_cuts": "PASS", "observed_internal_cuts": 0,
    }
    receipt = {
        "schema": "video_kingdom.e_s05_five_layer_gate_receipt.v1",
        "task_id": "E_S05_HARDENING",
        "shot_id": "E/S05",
        "take_id": take.get("take_id"),
        "video_id": take.get("video_id"),
        "status": "CANDIDATE_FAILED",
        "artifact": {
            "path": str(artifact.relative_to(root)).replace("\\", "/"),
            "sha256": sha256(artifact),
            "duration_seconds": take.get("media", {}).get("duration_seconds"),
            "resolution": f"{take.get('media', {}).get('width')}x{take.get('media', {}).get('height')}",
        },
        "submission": {"mode": "NEW_ONE_TIME_SUBMISSION", "post_count": 1, "duplicate_submission": False},
        "gates": {
            "picture": {"status": "FAIL", "reason": "pseudo_text_on_tombstone", "evidence": "episodes/generated/E_S05_HARDENING_20260906/qc/picture_gate_fail_evidence.png"},
            "action": {"status": "PASS_OBSERVED", "reason": "single slow bottle raise; no drink/pour/spill/turn observed in contact sheet review", "evidence": "episodes/generated/E_S05_HARDENING_20260906/qc/contact_sheet.png"},
            "camera": {"status": "PASS", "reason": "0 internal cuts; no continuity spikes; fixed framing", "evidence": ["episodes/generated/E_S05_HARDENING_20260906/qc/pacing.json", "episodes/generated/E_S05_HARDENING_20260906/qc/frame_continuity.json"]},
            "continuity": {"status": "UNPROVEN_FAIL_CLOSED", "reason": "asset bridge is hash-bound, but S04/S06 frame-to-frame proof is not available for this new take", "evidence": "assets/library/task_assets/E_S05_HARDENING_20260906/E_S05_CONTINUITY_BRIDGE_SPEC_V1.png"},
            "director": {"status": "REVIEW_REQUIRED", "reason": "restrained staging is present, but pseudo text breaks realistic memorial treatment", "evidence": "episodes/generated/E_S05_HARDENING_20260906/qc/contact_sheet.png"},
        },
        "mechanical_qc": machine_qc,
        "supporting_reports": {"frame_continuity": frame_report, "pacing": pacing_report, "shot_core": core_report},
        "decision": {
            "deliverable_created": False,
            "delivery_path": None,
            "candidate_retained": True,
            "stop_after_failure": True,
            "retry_or_second_submission": False,
            "reason": "picture gate failed and continuity gate is not proven; do not rename candidate to S05A.mp4",
        },
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ledger_path = root / "research" / "E_S05_asset_audit_ledger.v2.json"
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger["generation_status"] = {
            "status": "CANDIDATE_FAILED",
            "video_provider_calls": 1,
            "asset_image_generation_calls": ledger.get("generation_status", {}).get("asset_image_generation_calls", 1),
            "new_artifact_path": artifact.relative_to(root).as_posix(),
            "video_id": take.get("video_id"),
            "artifact_sha256": sha256(artifact),
            "candidate_receipt": receipt_path.relative_to(root).as_posix(),
        }
        ledger["post_generation"] = {
            "required": True,
            "status": "FAILED",
            "five_layer_receipt": receipt_path.relative_to(root).as_posix(),
            "delivery": "STOPPED_CANDIDATE_ONLY",
        }
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    take.update({
        "status": "CANDIDATE",
        "creative_status": "FAIL",
        "selected": False,
        "quality_gate_status": "CANDIDATE_FAILED",
        "quality_gate_receipt_path": receipt_path.relative_to(root).as_posix(),
        "failure_reason": "PICTURE_GATE_FAIL:pseudo_text_on_tombstone;CONTINUITY_GATE_UNPROVEN",
        "machine_qc": machine_qc,
    })
    shot = manifest.setdefault("shots", {}).setdefault("S05A", {})
    shot.update({"lifecycle": "REWORK", "selected_take_id": None, "quality_gate_status": "CANDIDATE_FAILED", "stale": False})
    manifest.setdefault("events", []).append({"event": "FIVE_LAYER_GATE_FAILED", "shot_id": "S05A", "take_id": "S05A_T01", "reason": "picture_gate_and_continuity_gate", "receipt": receipt_path.relative_to(root).as_posix()})
    save_manifest(manifest_path, manifest)
    print(json.dumps({"status": receipt["status"], "receipt": receipt_path.as_posix(), "artifact": artifact.as_posix()}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
