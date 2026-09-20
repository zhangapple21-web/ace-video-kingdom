"""Validate the canonical line-to-deliverable lineage contract.

The validator is deliberately independent from any provider.  It answers a
simple production question: can every spoken line be followed from the
versioned script to one shot, one character/voice and one generated take,
then to a passed review and the version selected for delivery?
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^[0-9a-f]{64}$")
REF_KEYS = (
    "script", "script_structure", "storyboard", "prompt_contract",
    "asset_manifest", "audio_timeline", "review_record", "generation_receipt",
)
DELIVERY_STATUSES = {"PREVIEW", "DRAFT", "APPROVED_MASTER", "PUBLISH_PACKAGE", "BLOCKED"}
PRODUCTION_DELIVERY_STATUSES = {"APPROVED_MASTER", "PUBLISH_PACKAGE"}
LINE_KEYS = (
    "line_id", "text", "track_type", "shot_id", "character_id", "speaker",
    "voice_id", "audio_track_id", "generation_receipt_id", "video_artifact_path",
    "review_receipt_ids", "take_id", "selected", "delivery_version_id",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _error(errors: list[str], message: str) -> None:
    errors.append(message)


def _validate_ref(name: str, ref: Any, *, base_dir: Path | None, production: bool, errors: list[str], warnings: list[str]) -> None:
    if not isinstance(ref, dict):
        _error(errors, f"{name} must be an artifact reference object")
        return
    path_value = str(ref.get("path") or "").strip()
    digest = str(ref.get("sha256") or "").lower().strip()
    status = str(ref.get("status") or "").upper().strip()
    if not path_value:
        _error(errors if production else warnings, f"{name}.path is missing")
    if not digest or not SHA256.fullmatch(digest):
        _error(errors if production else warnings, f"{name}.sha256 must be a 64-character SHA-256")
    if status not in {"PRESENT", "MISSING", "UNVERIFIED"}:
        _error(errors, f"{name}.status must be PRESENT, MISSING or UNVERIFIED")
    if production and status != "PRESENT":
        _error(errors, f"{name} is not PRESENT")
    if not production or not path_value or path_value.startswith(("http://", "https://", "data:")):
        return
    path = Path(path_value).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = (base_dir / path).resolve()
    if not path.is_file():
        _error(errors, f"{name} file does not exist: {path_value}")
        return
    actual = sha256_file(path)
    if digest and actual != digest:
        _error(errors, f"{name}.sha256 mismatch: expected {digest}, got {actual}")


def validate_lineage(document: dict[str, Any], *, base_dir: Path | None = None, production: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(document, dict):
        return {"status": "BLOCKED", "errors": ["lineage document must be an object"], "warnings": []}
    if document.get("schema") != "ace.video_kingdom.shot_lineage.v1":
        _error(errors, "schema must be ace.video_kingdom.shot_lineage.v1")
    for name in REF_KEYS:
        _validate_ref(name, document.get(name), base_dir=base_dir, production=production, errors=errors, warnings=warnings)

    delivery = document.get("delivery")
    if not isinstance(delivery, dict):
        _error(errors, "delivery must be an object")
        delivery = {}
    delivery_status = str(delivery.get("status") or "").upper().strip()
    if delivery_status not in DELIVERY_STATUSES:
        _error(errors, f"delivery.status must be one of {sorted(DELIVERY_STATUSES)}")
    if production and delivery_status in PRODUCTION_DELIVERY_STATUSES:
        if not str(delivery.get("version_id") or "").strip() or str(delivery.get("version_id")) == "PENDING":
            _error(errors, "approved delivery requires delivery.version_id")
        assembly = str(delivery.get("assembly_path") or "").strip()
        assembly_hash = str(delivery.get("assembly_sha256") or "").lower().strip()
        if not assembly or not SHA256.fullmatch(assembly_hash):
            _error(errors, "approved delivery requires assembly_path and assembly_sha256")
        elif base_dir is not None and not assembly.startswith(("http://", "https://", "data:")):
            assembly_path = Path(assembly).expanduser()
            if not assembly_path.is_absolute():
                assembly_path = (base_dir / assembly_path).resolve()
            if not assembly_path.is_file():
                _error(errors, f"delivery assembly does not exist: {assembly}")
            elif sha256_file(assembly_path) != assembly_hash:
                _error(errors, "delivery.assembly_sha256 mismatch")

    lines = document.get("lines")
    if not isinstance(lines, list) or not lines:
        _error(errors, "lines must be a non-empty array")
        lines = []
    seen_lines: set[str] = set()
    selected_by_line: dict[str, int] = {}
    for index, line in enumerate(lines):
        prefix = f"lines[{index}]"
        if not isinstance(line, dict):
            _error(errors, f"{prefix} must be an object")
            continue
        for key in LINE_KEYS:
            if key not in line or line.get(key) in (None, ""):
                _error(errors if production else warnings, f"{prefix}.{key} is missing")
        line_id = str(line.get("line_id") or "").strip()
        if line_id:
            if line_id in seen_lines:
                _error(errors, f"duplicate line_id: {line_id}")
            seen_lines.add(line_id)
        if not isinstance(line.get("text"), str) or not str(line.get("text") or "").strip():
            _error(errors, f"{prefix}.text must contain the complete original line")
        if str(line.get("track_type") or "").upper() not in {"DIALOGUE", "INNER_MONOLOGUE"}:
            _error(errors, f"{prefix}.track_type must be DIALOGUE or INNER_MONOLOGUE")
        if not isinstance(line.get("review_receipt_ids"), list):
            _error(errors, f"{prefix}.review_receipt_ids must be an array")
        if not isinstance(line.get("selected"), bool):
            _error(errors, f"{prefix}.selected must be boolean")
        if line.get("selected") is True and line_id:
            selected_by_line[line_id] = selected_by_line.get(line_id, 0) + 1
        audio = line.get("audio")
        if not isinstance(audio, dict):
            _error(errors if production else warnings, f"{prefix}.audio must contain measured path/hash/duration")
        else:
            duration = audio.get("duration_seconds")
            if not isinstance(duration, (int, float)) or duration <= 0:
                _error(errors if production else warnings, f"{prefix}.audio.duration_seconds must be positive")
            if not str(audio.get("path") or "").strip() or not SHA256.fullmatch(str(audio.get("sha256") or "").lower()):
                _error(errors if production else warnings, f"{prefix}.audio requires path and SHA-256")
            elif production and base_dir is not None and not str(audio.get("path")).startswith(("http://", "https://", "data:")):
                audio_path = Path(str(audio.get("path"))).expanduser()
                if not audio_path.is_absolute():
                    audio_path = (base_dir / audio_path).resolve()
                if not audio_path.is_file():
                    _error(errors, f"{prefix}.audio file does not exist: {audio.get('path')}")
                elif sha256_file(audio_path) != str(audio.get("sha256")).lower():
                    _error(errors, f"{prefix}.audio.sha256 mismatch")
        artifact = str(line.get("video_artifact_path") or "").strip()
        artifact_hash = str(line.get("video_artifact_sha256") or "").lower().strip()
        if production and (not artifact or not SHA256.fullmatch(artifact_hash)):
            _error(errors, f"{prefix}.video_artifact_path and video_artifact_sha256 are required")
        elif production and base_dir is not None and artifact and not artifact.startswith(("http://", "https://", "data:")):
            artifact_path = Path(artifact).expanduser()
            if not artifact_path.is_absolute():
                artifact_path = (base_dir / artifact_path).resolve()
            if not artifact_path.is_file():
                _error(errors, f"{prefix}.video artifact does not exist: {artifact}")
            elif sha256_file(artifact_path) != artifact_hash:
                _error(errors, f"{prefix}.video_artifact_sha256 mismatch")
        if production:
            if line.get("review_status") != "PASS":
                _error(errors, f"{prefix}.review_status must be PASS for production")
            if not line.get("selected"):
                _error(errors, f"{prefix} is not selected for delivery")
            if str(line.get("delivery_version_id") or "") in {"", "PENDING"}:
                _error(errors, f"{prefix}.delivery_version_id is not bound")
    if production and any(count != 1 for count in selected_by_line.values()):
        _error(errors, "each line must have exactly one selected lineage record")
    status = "BLOCKED" if errors else ("INCOMPLETE" if warnings else "PASS")
    return {"status": status, "errors": errors, "warnings": warnings, "line_count": len(lines)}


def validate_lineage_ref(value: Any, *, base_dir: Path | None = None, production: bool = True) -> dict[str, Any]:
    """Load and validate a contract reference carried by a shot/episode.

    A path-only reference is accepted for compatibility, while the preferred
    form is ``{"path": ..., "sha256": ...}``.  The provider gate never
    accepts an unreadable or hash-mismatched lineage file.
    """
    if isinstance(value, str):
        value = {"path": value}
    if not isinstance(value, dict):
        return {"status": "BLOCKED", "errors": ["lineage_contract must be a path or reference object"]}
    raw_path = str(value.get("path") or "").strip()
    if not raw_path:
        return {"status": "BLOCKED", "errors": ["lineage_contract.path is required"]}
    path = Path(raw_path).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = (base_dir / path).resolve()
    if not path.is_file():
        return {"status": "BLOCKED", "errors": [f"lineage_contract file does not exist: {path}"]}
    expected = str(value.get("sha256") or "").lower().strip()
    if expected and expected != sha256_file(path):
        return {"status": "BLOCKED", "errors": ["lineage_contract.sha256 mismatch"]}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "BLOCKED", "errors": [f"lineage_contract unreadable: {exc}"]}
    result = validate_lineage(document, base_dir=path.parent, production=production)
    result["path"] = str(path)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a video line-to-delivery lineage contract")
    parser.add_argument("document", type=Path)
    parser.add_argument("--production", action="store_true", help="require all refs, hashes, selected takes and approved delivery")
    args = parser.parse_args(argv)
    try:
        document = json.loads(args.document.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "errors": [f"unreadable lineage: {exc}"]}, ensure_ascii=False))
        return 1
    result = validate_lineage(document, base_dir=args.document.parent, production=args.production)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"PASS", "INCOMPLETE"} and not args.production else (0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
