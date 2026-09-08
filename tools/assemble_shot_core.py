"""Assemble only Creative-PASS selected Shot Core Takes.

The command is intentionally provider-free.  It reads the existing pilot
manifest, rejects stale/unselected shots, and writes a local assembly receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.shot_core import _probe, audit_manifest, load_manifest, resolve_artifact_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--shot-ids", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    audit = audit_manifest(args.manifest)
    if audit["status"] != "PASS":
        raise SystemExit("manifest audit failed: " + ";".join(audit["errors"][:8]))
    if len(set(args.shot_ids)) != len(args.shot_ids):
        raise SystemExit("duplicate shot ids are not allowed in assembly")
    clips: list[Path] = []
    sources: list[dict] = []
    for shot_id in args.shot_ids:
        shot = manifest.get("shots", {}).get(shot_id, {})
        selected_id = shot.get("selected_take_id")
        if shot.get("stale") or not selected_id or shot.get("lifecycle") != "SELECTED":
            raise SystemExit(f"shot {shot_id} is not SELECTED or is stale")
        take = next((row for row in manifest.get("takes", []) if row.get("take_id") == selected_id), None)
        if not take or take.get("provider_status") != "SUCCESS" or take.get("technical_status") != "PASS" or take.get("creative_status") != "PASS" or not take.get("selected"):
            raise SystemExit(f"selected take is not fully passed: {shot_id}/{selected_id}")
        path = resolve_artifact_path(args.manifest, take.get("artifact_path", ""))
        if not path.is_file():
            raise SystemExit(f"selected artifact missing: {shot_id}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != take.get("artifact_hash"):
            raise SystemExit(f"selected artifact hash mismatch: {shot_id}")
        machine_qc = take.get("machine_qc") if isinstance(take.get("machine_qc"), dict) else {}
        if any(machine_qc.get(key) != "PASS" for key in ("file_integrity", "resolution", "fps", "duration", "black_frames", "freeze_tail", "internal_cuts")):
            raise SystemExit(f"selected machine QC incomplete: {shot_id}")
        clips.append(path.resolve())
        sources.append({"shot_id": shot_id, "take_id": selected_id, "path": str(path.resolve()), "artifact_hash": digest, "contract_fingerprint": shot.get("contract_fingerprint"), "dependency_snapshot": shot.get("dependency_snapshot", {})})
    if args.output.resolve() in clips:
        raise SystemExit("assembly output must not overwrite a selected source artifact")
    if args.output.exists():
        raise SystemExit(f"assembly output already exists; refusing overwrite: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    concat = args.output.with_suffix(".concat.txt")
    concat.write_text("\n".join("file '" + str(path).replace("'", "'\\''") + "'" for path in clips) + "\n", encoding="utf-8")
    try:
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(args.output)], check=True)
    finally:
        concat.unlink(missing_ok=True)
    try:
        output_media = _probe(args.output)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        args.output.unlink(missing_ok=True)
        raise SystemExit(f"assembled output failed media probe: {exc}")
    receipt = {"schema": "video_kingdom.shot_core.assembly_receipt.v1", "status": "ASSEMBLY_SELECTED_ONLY", "output": str(args.output), "output_hash": hashlib.sha256(args.output.read_bytes()).hexdigest(), "media": output_media, "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(), "shots": sources}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
