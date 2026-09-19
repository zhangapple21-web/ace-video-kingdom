"""Fail-closed validation for the logical asset registry and package templates."""

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


def validate(repo_root: Path, index_path: Path) -> dict[str, Any]:
    index = _load(index_path)
    by_path = {row["source_path"]: row for row in index.get("entries", [])}
    errors: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    package_count = 0

    for package_path in sorted((repo_root / "assets" / "library").glob("**/asset_package.v1.json")):
        package_count += 1
        package = _load(package_path)
        schema = package.get("schema", "")
        if "character_asset_package" in schema:
            kind = "character"
            items = package.get("visual_assets", [])
        elif "scene_asset_package" in schema:
            kind = "scene"
            items = package.get("views") or package.get("visual_assets") or []
        elif "prop_asset_package" in schema:
            kind = "prop"
            items = package.get("visual_assets") or package.get("views") or []
        else:
            kind = "unknown"
            items = []
        for item in items:
            if not item.get("required"):
                continue
            asset_id = item.get("asset_id")
            path_text = item.get("path")
            status = item.get("status")
            if not path_text:
                gaps.append({"package": package_path.relative_to(repo_root).as_posix(), "asset_id": asset_id, "reason": "REQUIRED_ASSET_MISSING", "status": status})
                continue
            source = (repo_root / path_text).resolve()
            try:
                source.relative_to(repo_root.resolve())
            except ValueError:
                errors.append({"package": str(package_path), "asset_id": asset_id, "reason": "PATH_ESCAPE"})
                continue
            if not source.exists():
                errors.append({"package": str(package_path), "asset_id": asset_id, "reason": "SOURCE_NOT_FOUND", "path": path_text})
                continue
            actual = _sha256(source)
            expected = item.get("sha256")
            if expected and actual != expected:
                errors.append({"package": str(package_path), "asset_id": asset_id, "reason": "SHA256_MISMATCH", "path": path_text, "expected": expected, "actual": actual})
            row = by_path.get(path_text.replace("\\", "/"))
            if row and row.get("asset_state") == "PLACEHOLDER":
                errors.append({"package": str(package_path), "asset_id": asset_id, "reason": "PLACEHOLDER_ASSET", "path": path_text})

    status = "BLOCKED" if errors else "CONDITIONAL" if gaps else "READY"
    return {
        "schema": "video_kingdom.asset_gate_receipt.v1",
        "status": status,
        "index_path": index_path.relative_to(repo_root).as_posix(),
        "package_count": package_count,
        "error_count": len(errors),
        "gap_count": len(gaps),
        "errors": errors,
        "gaps": gaps,
        "rule": "Required assets, source hashes, and non-placeholder state must be proven before provider admission.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--index", type=Path, default=None)
    parser.add_argument("--write-receipt", action="store_true")
    parser.add_argument("--fail-on-gap", action="store_true")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    index_path = (args.index or repo_root / "assets" / "index" / "asset_index.v1.json").resolve()
    receipt = validate(repo_root, index_path)
    if args.write_receipt:
        output = repo_root / "assets" / "index" / "asset_gate_receipt.v1.json"
        output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"receipt={output}")
    print(f"status={receipt['status']} packages={receipt['package_count']} gaps={receipt['gap_count']} errors={receipt['error_count']}")
    if receipt["status"] == "BLOCKED":
        return 3
    if args.fail_on_gap and receipt["status"] == "CONDITIONAL":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
