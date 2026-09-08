"""Fail-closed validation for a task-level shot asset package.

This validator only reads local files.  It proves that referenced files still
exist and match their recorded SHA-256, then applies the task package's
blocking checklist.  It never calls a provider.  A package may be READY for
one new submission when no compatible legacy video_id exists; an incompatible
legacy id must never be treated as resumable evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_ref(repo_root: Path, ref: dict[str, Any], errors: list[dict[str, Any]], checked: list[dict[str, Any]]) -> None:
    path_text = ref.get("path")
    expected = ref.get("sha256")
    if not path_text:
        return
    source = (repo_root / str(path_text)).resolve()
    try:
        source.relative_to(repo_root.resolve())
    except ValueError:
        errors.append({"reason": "PATH_ESCAPE", "path": path_text})
        return
    if not source.exists():
        errors.append({"reason": "SOURCE_NOT_FOUND", "path": path_text})
        return
    actual = _sha256(source)
    checked.append({"path": str(path_text).replace("\\", "/"), "sha256": actual})
    if expected and actual != expected:
        errors.append({"reason": "SHA256_MISMATCH", "path": path_text, "expected": expected, "actual": actual})


def validate(repo_root: Path, package_path: Path) -> dict[str, Any]:
    package = _load(package_path)
    errors: list[dict[str, Any]] = []
    checked: list[dict[str, Any]] = []

    # Prove the package files and every required child asset, not only the
    # legacy continuity clips. This prevents a logical JSON package from
    # passing while its new visual boards are missing or hash-drifted.
    for anchor in package.get("locked_anchors", {}).values():
        if isinstance(anchor, dict):
            package_path_text = anchor.get("package_path")
            if package_path_text:
                _check_ref(repo_root, {"path": package_path_text}, errors, checked)
            child_package = (repo_root / str(package_path_text)).resolve() if package_path_text else None
            if child_package and child_package.exists():
                try:
                    child = _load(child_package)
                except (OSError, ValueError, json.JSONDecodeError):
                    child = {}
                for key in ("visual_assets", "views", "required_assets"):
                    for child_ref in child.get(key, []):
                        if isinstance(child_ref, dict) and child_ref.get("path"):
                            _check_ref(repo_root, child_ref, errors, checked)
        elif isinstance(anchor, list):
            for item in anchor:
                if not isinstance(item, dict):
                    continue
                package_path_text = item.get("package_path")
                if package_path_text:
                    _check_ref(repo_root, {"path": package_path_text}, errors, checked)
                    child_package = (repo_root / str(package_path_text)).resolve()
                    if child_package.exists():
                        try:
                            child = _load(child_package)
                        except (OSError, ValueError, json.JSONDecodeError):
                            child = {}
                        for child_ref in child.get("required_assets", []):
                            if isinstance(child_ref, dict) and child_ref.get("path"):
                                _check_ref(repo_root, child_ref, errors, checked)

    for ref in package.get("locked_anchors", {}).get("props", []):
        if isinstance(ref, dict):
            _check_ref(repo_root, ref, errors, checked)
    continuity = package.get("continuity", {})
    for bridge in continuity.values():
        if isinstance(bridge, dict):
            _check_ref(repo_root, bridge.get("existing_reference", {}), errors, checked)
            if bridge.get("bridge_asset"):
                _check_ref(repo_root, {"path": bridge.get("bridge_asset"), "sha256": bridge.get("bridge_sha256")}, errors, checked)

    blocking_items = [
        item for item in package.get("audit_items", [])
        if item.get("blocking") and item.get("status") != "PASS"
    ]
    package_status = package.get("package_status", "UNKNOWN")
    compatible_video_status = package.get("existing_video_id_check", {}).get("status", "UNKNOWN")
    gaps = [
        {
            "id": item.get("id"),
            "label": item.get("label"),
            "status": item.get("status"),
            "change_status": item.get("change_status"),
        }
        for item in blocking_items
    ]
    release_status = package.get("release_decision", {}).get("status")
    new_submission_allowed = release_status == "READY_FOR_ONE_TIME_GENERATION"
    video_id_ok = compatible_video_status == "COMPATIBLE_VIDEO_ID_FOUND" or (
        compatible_video_status == "NO_COMPATIBLE_VIDEO_ID_FOUND" and new_submission_allowed
    )
    status = "BLOCKED" if errors or package_status != "READY" or blocking_items or not video_id_ok else "READY"
    admission_mode = "RESUME_EXISTING_VIDEO_ID" if compatible_video_status == "COMPATIBLE_VIDEO_ID_FOUND" else "NEW_ONE_TIME_SUBMISSION" if status == "READY" else "BLOCKED"
    return {
        "schema": "video_kingdom.shot_asset_gate_receipt.v1",
        "task_id": package.get("task_id"),
        "shot_id": package.get("shot_id"),
        "package_path": package_path.relative_to(repo_root).as_posix(),
        "status": status,
        "package_status": package_status,
        "compatible_video_id_status": compatible_video_status,
        "admission_mode": admission_mode,
        "post_generation_gate": "PENDING" if status == "READY" else None,
        "error_count": len(errors),
        "gap_count": len(gaps),
        "errors": errors,
        "blocking_items": gaps,
        "checked_paths": checked,
        "rule": "A task cannot enter provider admission until every blocking asset checklist item is PASS and either a compatible resumable video_id or an explicitly approved one-time new-submission policy is proven.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--package",
        type=Path,
        default=Path("assets/library/shots/E_S05/asset_package.v1.json"),
    )
    parser.add_argument("--write-receipt", action="store_true")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    package_path = (args.package if args.package.is_absolute() else repo_root / args.package).resolve()
    receipt = validate(repo_root, package_path)
    if args.write_receipt:
        output = repo_root / "research" / "admission_receipts" / "E_S05_asset_gate_receipt.v1.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"receipt={output}")
    print(f"status={receipt['status']} gaps={receipt['gap_count']} errors={receipt['error_count']} video_id={receipt['compatible_video_id_status']}")
    return 0 if receipt["status"] == "READY" else 2


if __name__ == "__main__":
    sys.exit(main())
