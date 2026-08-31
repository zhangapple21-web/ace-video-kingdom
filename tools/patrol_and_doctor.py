"""Safe daily patrol for the existing Free Zone media workspace.

Repairs only deterministic local bookkeeping defects; it never kills arbitrary
processes, submits model calls, or creates a scheduler.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--stale-seconds", type=int, default=900)
    args = parser.parse_args()
    root = args.root.resolve()
    report = {"status": "PATROL_OK", "repairs": [], "warnings": [], "checked": []}
    manifest = root / "experiments" / "agnes_tasks.json"
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        report["checked"].append(str(manifest))
        if isinstance(data, dict):
            records = [data]
        else:
            records = data if isinstance(data, list) else []
        now = time.time()
        for row in records:
            if not isinstance(row, dict):
                continue
            if row.get("status") in {"CREATING", "SUBMITTED_IN_PROGRESS", "in_progress"}:
                updated = row.get("updated_at", row.get("created_at", now))
                if isinstance(updated, (int, float)) and now - updated > args.stale_seconds:
                    row["status"] = "STALE_REQUIRES_RESUME"
                    report["repairs"].append({"shot_id": row.get("shot_id"), "action": "mark_stale_requires_resume"})
            artifact = row.get("artifact_path")
            expected = row.get("artifact_sha256")
            if artifact and expected:
                path = root / artifact if not Path(artifact).is_absolute() else Path(artifact)
                if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    row["status"] = "ARTIFACT_HASH_MISMATCH"
                    report["warnings"].append({"shot_id": row.get("shot_id"), "issue": "artifact_hash_mismatch"})
        manifest.write_text(json.dumps(records if isinstance(data, list) else records[0], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    media = root / "media_staging"
    if media.is_dir():
        for path in media.iterdir():
            if path.is_file():
                report["checked"].append(str(path))
    if report["repairs"] or report["warnings"]:
        report["status"] = "PATROL_REPAIRS_RECORDED"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
