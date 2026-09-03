"""Inspect all durable Video Kingdom media jobs without creating work.

This is a local diagnostic/repair-preparation tool, not a scheduler or a
provider client. It scans every task manifest, verifies completed artifacts,
and distinguishes resumable provider work from terminal failures so a later
Free Zone shift has evidence rather than guesswork.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ACTIVE = {"CREATING", "SUBMITTED_IN_PROGRESS", "IN_PROGRESS", "POLL_TIMEOUT", "DOWNLOAD_FAILED"}
TERMINAL = {"CREATE_FAILED", "FAILED", "REJECTED_VISUAL_ROTATION"}


def _records(path: Path) -> list[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload if isinstance(payload, list) else [payload]
    return [row for row in rows if isinstance(row, dict) and row.get("shot_id")]


def _artifact_path(root: Path, value: object) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def inspect(root: Path) -> dict:
    report: dict = {
        "contract_version": "ace.video_kingdom.patrol.v2",
        "at": datetime.now(timezone.utc).isoformat(),
        "status": "PATROL_OK",
        "provider_calls": 0,
        "repairs": [],
        "warnings": [],
        "active_jobs": [],
        "resumable_jobs": [],
        "terminal_failures": [],
        "completed_jobs": [],
        "manifests": [],
    }
    # A shot ID is intentionally reused when a later render replaces a rejected
    # take.  Historical completed takes are evidence, not concurrent work.  A
    # collision is operationally dangerous only when two non-terminal jobs for
    # the same shot can still submit or poll independently.
    seen_nonterminal_shots: dict[str, str] = {}
    for manifest in sorted((root / "experiments").glob("*tasks*.json")):
        rows = _records(manifest)
        if not rows:
            continue
        report["manifests"].append(str(manifest.relative_to(root)))
        for row in rows:
            shot_id = str(row["shot_id"])
            manifest_name = str(manifest.relative_to(root))
            status = str(row.get("status", "UNKNOWN")).upper()
            entry = {"manifest": manifest_name, "shot_id": shot_id, "status": status, "model_id": row.get("model_id")}
            if status != "COMPLETED" and status not in TERMINAL:
                prior_manifest = seen_nonterminal_shots.get(shot_id)
                if prior_manifest and prior_manifest != manifest_name:
                    report["warnings"].append({"shot_id": shot_id, "issue": "DUPLICATE_SHOT_ID_ACROSS_MANIFESTS", "manifests": [prior_manifest, manifest_name]})
                else:
                    seen_nonterminal_shots[shot_id] = manifest_name
            if status == "COMPLETED":
                artifact = _artifact_path(root, row.get("artifact_path"))
                expected = row.get("artifact_sha256")
                if not artifact or not artifact.is_file():
                    report["warnings"].append({**entry, "issue": "COMPLETED_ARTIFACT_MISSING"})
                    continue
                actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
                if not expected or actual != expected:
                    report["warnings"].append({**entry, "issue": "COMPLETED_ARTIFACT_HASH_MISMATCH"})
                    continue
                report["completed_jobs"].append({**entry, "artifact": str(artifact), "sha256": actual})
            elif status in ACTIVE:
                report["active_jobs"].append(entry)
                if row.get("video_id"):
                    report["resumable_jobs"].append({**entry, "action": "RESUME_POLL_ONLY"})
                else:
                    report["warnings"].append({**entry, "issue": "ACTIVE_WITHOUT_VIDEO_ID"})
            elif status in TERMINAL:
                reason = str(row.get("error_body_excerpt") or row.get("quality_reason") or "")[:300]
                report["terminal_failures"].append({**entry, "reason": reason})
            elif status not in {"COMPLETED"}:
                report["warnings"].append({**entry, "issue": "UNKNOWN_JOB_STATUS"})
    if report["warnings"]:
        report["status"] = "PATROL_ATTENTION_REQUIRED"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path, help="optional local JSON report path")
    args = parser.parse_args()
    report = inspect(args.root.resolve())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
