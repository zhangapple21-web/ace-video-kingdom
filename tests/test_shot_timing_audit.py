import json
from pathlib import Path

from tools.audit_shot_timing import build_report


def test_shot_timing_audit_reports_all_measured_values(tmp_path: Path):
    contract = {
        "shots": [
            {
                "shot_id": "S01A",
                "script": {"dialogue_text": "你好", "audio_status": "MEASURED", "tts_duration_seconds": 2.1},
                "edit": {"duration_seconds": 2.7},
            }
        ]
    }
    clip = tmp_path / "S01A.mp4"
    clip.write_bytes(b"placeholder")
    manifest = [{"shot_id": "S01A", "path": str(clip)}]
    contract_path = tmp_path / "contract.json"
    manifest_path = tmp_path / "manifest.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = build_report(contract_path, manifest_path, probe=lambda _: 3.0)

    assert report["status"] == "PASS"
    assert report["coverage"] == {
        "tts_measured": 1,
        "tts_missing": 0,
        "actual_media_duration_measured": 1,
        "actual_media_duration_missing": 0,
    }
    assert report["rows"][0]["tts_fits_actual_media"] is True
    assert report["rows"][0]["actual_media_duration_seconds"] == 3.0


def test_manifest_declaration_without_file_is_not_measured(tmp_path: Path):
    contract_path = tmp_path / "contract.json"
    manifest_path = tmp_path / "manifest.json"
    contract_path.write_text(
        json.dumps({
            "shots": [{"shot_id": "S01A", "script": {"tts_duration_seconds": 2.0}, "edit": {"duration_seconds": 2.6}}]
        }),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps([{"shot_id": "S01A", "path": "missing.mp4", "duration_seconds": 4.0}]),
        encoding="utf-8",
    )
    report = build_report(contract_path, manifest_path, probe=lambda _: 4.0)
    assert report["status"] == "FAIL"
    assert report["coverage"]["actual_media_duration_measured"] == 0
    assert report["missing_actual_duration_shots"] == ["S01A"]


def test_alias_is_explicit_and_preserves_formal_id(tmp_path: Path):
    contract_path = tmp_path / "contract.json"
    manifest_path = tmp_path / "manifest.json"
    clip = tmp_path / "repair.mp4"
    clip.write_bytes(b"placeholder")
    contract_path.write_text(
        json.dumps({"shots": [{"shot_id": "S01D", "script": {"tts_duration_seconds": 2.0}, "edit": {"duration_seconds": 2.6}}]}),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps([{"shot_id": "S01D_REPAIR", "path": str(clip)}]),
        encoding="utf-8",
    )
    report = build_report(contract_path, manifest_path, probe=lambda _: 3.0, aliases={"S01D": "S01D_REPAIR"})
    assert report["status"] == "PASS"
    assert report["rows"][0]["shot_id"] == "S01D"
    assert report["rows"][0]["manifest_shot_id"] == "S01D_REPAIR"
    assert report["orphan_manifest_shot_ids"] == []


def test_manifest_overlay_can_replace_formal_shot(tmp_path: Path):
    contract_path = tmp_path / "contract.json"
    base_path = tmp_path / "base.json"
    overlay_path = tmp_path / "overlay.json"
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"placeholder")
    contract_path.write_text(json.dumps({"shots": [{"shot_id": "S01A", "script": {"tts_duration_seconds": 2.0}, "edit": {"duration_seconds": 2.6}}]}), encoding="utf-8")
    base_path.write_text(json.dumps([{"shot_id": "S01A", "path": "missing.mp4"}]), encoding="utf-8")
    overlay_path.write_text(json.dumps([{"shot_id": "S01A", "path": str(clip)}]), encoding="utf-8")
    report = build_report(contract_path, [base_path, overlay_path], probe=lambda _: 3.0)
    assert report["status"] == "PASS"
    assert report["rows"][0]["actual_duration_source"] == "ffprobe"


def test_path_override_is_explicit_and_hash_bound_to_existing_file(tmp_path: Path):
    contract_path = tmp_path / "contract.json"
    manifest_path = tmp_path / "manifest.json"
    base = tmp_path / "base.mp4"
    repair = tmp_path / "repair.mp4"
    base.write_bytes(b"base")
    repair.write_bytes(b"repair")
    contract_path.write_text(json.dumps({"shots": [{"shot_id": "S01C", "script": {"tts_duration_seconds": 4.0}, "edit": {"duration_seconds": 4.6}}]}), encoding="utf-8")
    manifest_path.write_text(json.dumps([{"shot_id": "S01C", "path": str(base)}]), encoding="utf-8")
    report = build_report(contract_path, manifest_path, probe=lambda path: 5.0 if path == repair.resolve() else 3.0, path_overrides={"S01C": repair})
    assert report["status"] == "PASS"
    assert report["rows"][0]["path_override_applied"] is True
    assert report["expected_hash_overrides"] == []


def test_artifact_path_and_sha256_aliases_are_supported(tmp_path: Path):
    contract_path = tmp_path / "contract.json"
    manifest_path = tmp_path / "manifest.json"
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"artifact")
    import hashlib

    digest = hashlib.sha256(clip.read_bytes()).hexdigest()
    contract_path.write_text(
        json.dumps({
            "shots": [{
                "shot_id": "S01A",
                "script": {"audio_status": "MEASURED", "tts_duration_seconds": 1.0},
                "edit": {"duration_seconds": 1.5},
            }]
        }),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps([{"shot_id": "S01A", "artifact_path": str(clip), "artifact_sha256": digest}]),
        encoding="utf-8",
    )
    report = build_report(contract_path, manifest_path, probe=lambda _: 2.0)
    assert report["status"] == "PASS"
    assert report["rows"][0]["media_sha256_actual"] == digest


def test_no_dialogue_shot_is_explicitly_timing_complete(tmp_path: Path):
    contract_path = tmp_path / "contract.json"
    manifest_path = tmp_path / "manifest.json"
    clip = tmp_path / "silent.mp4"
    clip.write_bytes(b"silent")
    contract_path.write_text(
        json.dumps({
            "shots": [{
                "shot_id": "S03A",
                "script": {"audio_status": "NO_DIALOGUE", "tts_duration_seconds": None},
                "edit": {"duration_seconds": 4.0},
            }]
        }),
        encoding="utf-8",
    )
    manifest_path.write_text(json.dumps([{"shot_id": "S03A", "path": str(clip)}]), encoding="utf-8")
    report = build_report(contract_path, manifest_path, probe=lambda _: 4.0)
    assert report["status"] == "PASS"
    assert report["coverage"]["tts_missing"] == 0
    assert report["rows"][0]["audio_status"] == "NO_DIALOGUE"
