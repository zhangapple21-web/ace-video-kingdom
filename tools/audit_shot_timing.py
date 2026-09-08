"""Audit per-shot TTS and rendered media timing from existing evidence.

This closes a recurring evidence gap in which a full-episode pacing report had
only one aggregate duration and therefore reported all 18 dialogue/TTS values
as missing.  The tool never synthesizes audio or calls a provider: it joins a
measured six-module contract to a real shot manifest and probes each media
file with ffprobe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Callable


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("sources", "shots", "records", "items"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
    raise ValueError("manifest must be a list or contain sources/shots/records/items")


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(manifest_path: Path, raw: Any) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate.resolve()
    # Producers in this workspace persist both project-relative paths and
    # repository-relative paths. Prefer an existing repository-relative path,
    # then fall back to the manifest's directory for ordinary local manifests.
    repo_relative = (Path.cwd() / candidate).resolve()
    manifest_relative = (manifest_path.parent / candidate).resolve()
    if repo_relative.is_file():
        return repo_relative
    return manifest_relative


def build_report(
    contract_path: Path,
    manifest_path: Path | list[Path],
    *,
    probe: Callable[[Path], float] = probe_duration,
    aliases: dict[str, str] | None = None,
    path_overrides: dict[str, Path] | None = None,
) -> dict[str, Any]:
    contract = _load(contract_path)
    manifest_paths = manifest_path if isinstance(manifest_path, list) else [manifest_path]
    manifests = [_load(path) for path in manifest_paths]
    contract_shots = contract.get("shots") if isinstance(contract, dict) else None
    if not isinstance(contract_shots, list):
        raise ValueError("contract must contain a shots list")

    manifest_by_id: dict[str, dict[str, Any]] = {}
    for manifest_value in manifests:
        for item in _records(manifest_value):
            shot_id = item.get("shot_id")
            if isinstance(shot_id, str) and shot_id.strip():
                manifest_by_id[shot_id] = item

    rows: list[dict[str, Any]] = []
    missing_tts: list[str] = []
    missing_actual: list[str] = []
    duration_failures: list[str] = []
    stale_manifest: list[str] = []
    hash_mismatches: list[str] = []
    expected_hash_overrides: list[str] = []
    for shot in contract_shots:
        shot_id = str(shot.get("shot_id", ""))
        script = shot.get("script") if isinstance(shot.get("script"), dict) else {}
        edit = shot.get("edit") if isinstance(shot.get("edit"), dict) else {}
        tts = script.get("tts_duration_seconds")
        contract_duration = edit.get("duration_seconds")
        audio_status = script.get("audio_status")
        is_silent_action = audio_status == "NO_DIALOGUE"
        if is_silent_action:
            # A silent action shot is intentionally measured by its editorial
            # floor and must not be reported as a missing TTS observation.
            tts_value: float | None = None
        elif not isinstance(tts, (int, float)) or tts <= 0:
            missing_tts.append(shot_id)
            tts_value: float | None = None
        else:
            tts_value = float(tts)

        manifest_id = (aliases or {}).get(shot_id, shot_id)
        record = manifest_by_id.get(manifest_id)
        record_source = next(
            (path for path, value in zip(manifest_paths, manifests)
             if record is not None and record in _records(value)),
            manifest_paths[0],
        )
        path = (path_overrides or {}).get(shot_id)
        if path is None:
            raw_path = None
            if record:
                raw_path = record.get("path") or record.get("artifact_path")
            path = _resolve(record_source, raw_path) if record else None
        declared = record.get("duration_seconds") if record else None
        actual: float | None = None
        actual_source = "missing"
        actual_sha256: str | None = None
        if path is not None and path.is_file():
            try:
                actual = round(float(probe(path)), 6)
                actual_source = "ffprobe"
                actual_sha256 = sha256_file(path)
            except (OSError, ValueError, subprocess.CalledProcessError) as exc:
                stale_manifest.append(f"{shot_id}: ffprobe failed for {path} ({exc})")
        elif isinstance(declared, (int, float)) and declared > 0:
            # A declared duration without an existing media path is not enough
            # to claim measured evidence.  Keep it visible but fail closed.
            actual_source = "manifest_declared_only"
        if actual is None:
            missing_actual.append(shot_id)

        contract_value = float(contract_duration) if isinstance(contract_duration, (int, float)) else None
        tts_fits_actual = actual is not None and tts_value is not None and actual + 1e-6 >= tts_value
        contract_covers_tts = contract_value is not None and tts_value is not None and contract_value + 1e-6 >= tts_value
        if tts_value is not None and actual is not None and not tts_fits_actual:
            duration_failures.append(
                f"{shot_id}: actual media {actual:.3f}s is shorter than measured TTS {tts_value:.3f}s"
            )
        if tts_value is not None and contract_value is not None and not contract_covers_tts:
            duration_failures.append(
                f"{shot_id}: contract duration {contract_value:.3f}s is shorter than measured TTS {tts_value:.3f}s"
            )
        declared_sha = (record.get("sha256") or record.get("artifact_sha256")) if record else None
        if declared_sha and actual_sha256 and declared_sha.lower() != actual_sha256.lower():
            if shot_id in (path_overrides or {}):
                expected_hash_overrides.append(shot_id)
            else:
                hash_mismatches.append(f"{shot_id}: declared {declared_sha} != actual {actual_sha256}")
        rows.append(
            {
                "shot_id": shot_id,
                "manifest_shot_id": manifest_id,
                "manifest_id_alias_applied": manifest_id != shot_id,
                "dialogue_text": script.get("dialogue_text"),
                "audio_status": audio_status,
                "tts_duration_seconds": tts_value,
                "contract_duration_seconds": contract_value,
                "actual_media_duration_seconds": actual,
                "actual_duration_source": actual_source,
                "tts_fits_actual_media": tts_fits_actual,
                "contract_covers_tts": contract_covers_tts,
                "actual_minus_contract_seconds": round(actual - contract_value, 6)
                if actual is not None and contract_value is not None
                else None,
                "media_path": str(path) if path is not None else None,
                "path_override_applied": shot_id in (path_overrides or {}),
                "media_sha256_declared": declared_sha,
                "media_sha256_actual": actual_sha256,
            }
        )

    contract_ids = {str(shot.get("shot_id", "")) for shot in contract_shots}
    aliased_manifest_ids = set((aliases or {}).values())
    orphan_manifest_ids = sorted(set(manifest_by_id) - contract_ids - aliased_manifest_ids)
    measured_tts = sum(row["tts_duration_seconds"] is not None for row in rows)
    measured_actual = sum(row["actual_media_duration_seconds"] is not None for row in rows)
    status = "PASS" if not missing_tts and not missing_actual and not duration_failures and not stale_manifest and not hash_mismatches else "FAIL"
    return {
        "contract_version": "ace.video_kingdom.shot_timing_audit.v1",
        "status": status,
        "contract": str(contract_path),
        "manifest": [str(path) for path in manifest_paths],
        "shot_count": len(rows),
        "coverage": {
            "tts_measured": measured_tts,
            "tts_missing": len(missing_tts),
            "actual_media_duration_measured": measured_actual,
            "actual_media_duration_missing": len(missing_actual),
        },
        "missing_tts_shots": missing_tts,
        "missing_actual_duration_shots": missing_actual,
        "duration_failures": duration_failures,
        "stale_manifest": stale_manifest,
        "hash_mismatches": hash_mismatches,
        "expected_hash_overrides": expected_hash_overrides,
        "orphan_manifest_shot_ids": orphan_manifest_ids,
        "explicit_id_aliases": dict(aliases or {}),
        "explicit_path_overrides": {key: str(value) for key, value in (path_overrides or {}).items()},
        "rows": rows,
        "evidence_boundary": {
            "tts": "contract script.tts_duration_seconds; must be positive measured value",
            "actual_media_duration": "ffprobe of existing manifest path; manifest declaration alone is not promoted",
            "provider_audio_content": "not established by this structural timing audit",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--alias", action="append", default=[], metavar="FORMAL=MANIFEST",
        help="explicitly map a formal contract shot ID to a manifest ID; never inferred",
    )
    parser.add_argument(
        "--path-override", action="append", default=[], metavar="SHOT=PATH",
        help="explicitly use a repaired local media path for a formal shot ID",
    )
    args = parser.parse_args()
    aliases: dict[str, str] = {}
    for value in args.alias:
        if "=" not in value:
            parser.error(f"--alias must be FORMAL=MANIFEST, got {value!r}")
        formal, manifest_id = value.split("=", 1)
        if not formal.strip() or not manifest_id.strip():
            parser.error(f"--alias must be FORMAL=MANIFEST, got {value!r}")
        aliases[formal.strip()] = manifest_id.strip()
    path_overrides: dict[str, Path] = {}
    for value in args.path_override:
        if "=" not in value:
            parser.error(f"--path-override must be SHOT=PATH, got {value!r}")
        shot_id, raw_path = value.split("=", 1)
        path = Path(raw_path.strip()).expanduser().resolve()
        if not shot_id.strip() or not path.is_file():
            parser.error(f"--path-override requires an existing file, got {value!r}")
        path_overrides[shot_id.strip()] = path
    report = build_report(args.contract.resolve(), [path.resolve() for path in args.manifest], aliases=aliases, path_overrides=path_overrides)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(args.output), "coverage": report["coverage"]}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
