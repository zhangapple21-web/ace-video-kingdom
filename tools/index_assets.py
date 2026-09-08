"""Build a deterministic, hash-bound asset index without moving source files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CANONICAL_NAME_RE = re.compile(
    r"^(?P<kind>CHAR|SCN|PROP|SHOT|AUDIO|BOARD|STYLE)_[A-Z0-9]+(?:_[A-Z0-9]+)*_V(?P<version>\d+)\.[A-Z0-9]+$",
    re.IGNORECASE,
)
MEDIA_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
METADATA_EXTENSIONS = {".json"}


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as image:
            return image.width, image.height
    except Exception:
        return None, None


def _normalise_rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _matches_exclude(path: Path, root: Path, patterns: Iterable[str]) -> bool:
    rel = _normalise_rel(path, root)
    return any(path.match(pattern) or Path(rel).match(pattern) for pattern in patterns)


def _infer_type(path: Path, root_kind: str) -> str:
    name = path.name.lower()
    if path.suffix.lower() == ".json":
        return "metadata"
    if name.startswith(("char_", "character_")) or "char_" in name or "character" in name:
        return "character"
    if name.startswith(("scn_", "scene_", "sc")) or "scene" in name:
        return "scene"
    if name.startswith(("prop_", "prop")) or "prop" in name:
        return "prop"
    if name.startswith(("shot_", "s")) or "shot" in name:
        return "shot"
    if path.suffix.lower() in {".wav", ".mp3", ".m4a"}:
        return "audio"
    if root_kind == "shared_anchors":
        return "unknown"
    return "display"


def _infer_usage(path: Path, asset_type: str) -> str:
    name = path.name.lower()
    if asset_type == "metadata":
        return "unknown"
    if any(token in name for token in ("montage", "sheet", "board", "dossier", "contact")):
        return "display_asset"
    if "anchor" in name or "first_frame" in name or "last_frame" in name:
        return "video_asset"
    if any(token in name for token in ("three_view", "turnaround", "emotion", "emo_", "reverse_180", "wide")):
        return "consistency_asset"
    return "unknown"


def _infer_evidence(path: Path) -> tuple[str, str]:
    lower = path.as_posix().lower()
    if "user_reference" in lower:
        return "USER_SUPPLIED_RESTRICTED", "USER_AUTHORIZED"
    if "public" in lower:
        return "PUBLIC_REFERENCE_ONLY", "PUBLIC_REFERENCE"
    if path.suffix.lower() == ".json" and ("dossier" in lower or "manifest" in lower):
        return "DOSSIER_BOUND", "UNVERIFIED"
    return "LOCAL_HASHED", "UNVERIFIED"


def _suggested_id(path: Path, asset_type: str) -> str | None:
    if asset_type == "metadata":
        return None
    stem = re.sub(r"[^A-Za-z0-9]+", "_", path.stem).strip("_").upper()
    if not stem:
        return None
    if re.search(r"_V\d+$", stem):
        return stem
    return f"{stem}_V1"


def _iter_files(root: Path, patterns: list[str], excludes: list[str], allowed: set[str]) -> Iterable[Path]:
    seen: set[Path] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            if path.suffix.lower() not in allowed:
                continue
            if _matches_exclude(path, root, excludes):
                continue
            yield path


def build_index(repo_root: Path, config_path: Path) -> dict[str, Any]:
    config = _json(config_path)
    excludes = list(config.get("exclude_globs", []))
    allowed = {str(ext).lower() for ext in config.get("allowed_extensions", [])}
    entries: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    registry_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    registry_path = repo_root / "assets" / "library" / "asset_registry.v1.json"
    if registry_path.exists():
        try:
            registry = _json(registry_path)
            for record in registry.get("records", []):
                source_path = str(record.get("source_path", "")).replace("\\", "/")
                digest = str(record.get("sha256", ""))
                if not source_path or len(digest) != 64:
                    warnings.append({"code": "REGISTRY_RECORD_INVALID", "record": record})
                    continue
                source = (repo_root / source_path).resolve()
                try:
                    source.relative_to(repo_root.resolve())
                except ValueError:
                    warnings.append({"code": "REGISTRY_PATH_ESCAPE", "path": source_path})
                    continue
                if not source.exists():
                    warnings.append({"code": "REGISTRY_SOURCE_MISSING", "path": source_path})
                    continue
                actual = _sha256(source)
                if actual != digest:
                    warnings.append({"code": "REGISTRY_HASH_MISMATCH", "path": source_path, "expected": digest, "actual": actual})
                    continue
                registry_by_key[(source_path, digest)] = record
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            warnings.append({"code": "REGISTRY_READ_FAILED", "path": str(registry_path), "error": str(exc)})

    for root_spec in config.get("roots", []):
        root = (repo_root / root_spec["path"]).resolve()
        if not root.exists():
            warnings.append({"code": "ROOT_MISSING", "root": root_spec["path"]})
            continue
        patterns = list(root_spec.get("patterns", ["**/*"]))
        for path in _iter_files(root, patterns, excludes, allowed):
            try:
                rel = path.relative_to(repo_root).as_posix()
                digest = _sha256(path)
                asset_type = _infer_type(path, root_spec.get("kind", "unknown"))
                usage = _infer_usage(path, asset_type)
                evidence_status, rights_status = _infer_evidence(path)
                match = CANONICAL_NAME_RE.match(path.name)
                naming_status = "CANONICAL" if match else ("LEGACY" if root_spec.get("legacy") else "INVALID")
                width, height = _dimensions(path) if path.suffix.lower() in MEDIA_EXTENSIONS else (None, None)
                if asset_type == "metadata":
                    asset_state = "METADATA"
                elif width is None or height is None:
                    asset_state = "UNREADABLE"
                elif width <= 2 and height <= 2 or path.stat().st_size < 1024:
                    asset_state = "PLACEHOLDER"
                else:
                    asset_state = "MEDIA_CANDIDATE"
                entry = {
                    "record_id": f"ASSET_{digest[:16].upper()}",
                    "asset_id": path.stem.upper() if match else None,
                    "suggested_asset_id": _suggested_id(path, asset_type),
                    "asset_type": asset_type,
                    "source_root_kind": root_spec.get("kind", "unknown"),
                    "source_path": rel,
                    "sha256": digest,
                    "bytes": path.stat().st_size,
                    "format": path.suffix.lower().lstrip("."),
                    "mime_type": mimetypes.guess_type(path.name)[0],
                    "width": width,
                    "height": height,
                    "asset_state": asset_state,
                    "usage": usage,
                    "registry_status": None,
                    "naming_status": naming_status,
                    "evidence_status": evidence_status,
                    "rights_status": rights_status,
                    "legacy_source": bool(root_spec.get("legacy")),
                }
                binding = registry_by_key.get((rel, digest))
                if binding:
                    entry["asset_id"] = binding.get("asset_id") or entry["asset_id"]
                    entry["usage"] = binding.get("usage") or entry["usage"]
                    entry["rights_status"] = binding.get("rights_status") or entry["rights_status"]
                    entry["registry_status"] = binding.get("status")
                    entry["evidence_status"] = "DOSSIER_BOUND" if binding.get("evidence") else entry["evidence_status"]
                entries.append(entry)
                if naming_status != "CANONICAL" and asset_type != "metadata":
                    warnings.append({"code": "LEGACY_OR_INVALID_NAME", "path": rel, "suggested_asset_id": entry["suggested_asset_id"]})
                if asset_state == "PLACEHOLDER":
                    warnings.append({"code": "PLACEHOLDER_MEDIA", "path": rel, "bytes": path.stat().st_size, "width": width, "height": height})
            except (OSError, ValueError) as exc:
                warnings.append({"code": "READ_FAILED", "path": str(path), "error": str(exc)})

    entries.sort(key=lambda item: item["source_path"])
    by_hash: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        by_hash[entry["sha256"]].append(entry["source_path"])
    duplicate_groups = [
        {"sha256": digest, "paths": sorted(paths)}
        for digest, paths in sorted(by_hash.items())
        if len(paths) > 1
    ]
    canonical_invalid = [
        warning for warning in warnings if warning.get("code") == "LEGACY_OR_INVALID_NAME" and str(warning.get("path", "")).startswith("assets/library/")
    ]
    return {
        "schema": "video_kingdom.asset_index.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": repo_root.as_posix(),
        "config": config_path.relative_to(repo_root).as_posix(),
        "stats": {
            "entry_count": len(entries),
            "media_count": sum(1 for entry in entries if entry["asset_type"] != "metadata"),
            "metadata_count": sum(1 for entry in entries if entry["asset_type"] == "metadata"),
            "media_candidate_count": sum(1 for entry in entries if entry["asset_state"] == "MEDIA_CANDIDATE"),
            "placeholder_count": sum(1 for entry in entries if entry["asset_state"] == "PLACEHOLDER"),
            "registry_bound_count": sum(1 for entry in entries if entry["registry_status"]),
            "usable_media_by_usage": {
                usage: sum(1 for entry in entries if entry["asset_state"] == "MEDIA_CANDIDATE" and entry["usage"] == usage)
                for usage in ("video_asset", "consistency_asset", "display_asset", "marketing_asset", "unknown")
            },
            "duplicate_group_count": len(duplicate_groups),
            "warning_count": len(warnings),
            "canonical_invalid_count": len(canonical_invalid),
        },
        "entries": entries,
        "duplicate_groups": duplicate_groups,
        "warnings": warnings,
    }


def write_outputs(repo_root: Path, index: dict[str, Any]) -> tuple[Path, Path]:
    out_dir = repo_root / "assets" / "index"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "asset_index.v1.json"
    csv_path = out_dir / "asset_index.csv"
    json_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ["record_id", "asset_id", "suggested_asset_id", "asset_type", "asset_state", "usage", "naming_status", "evidence_status", "rights_status", "source_path", "sha256", "bytes", "width", "height"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field) for field in fields} for row in index["entries"])
    return json_path, csv_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--check", action="store_true", help="build outputs and fail on read errors")
    parser.add_argument("--strict-canonical", action="store_true", help="also fail if assets/library contains non-canonical names")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    config_path = (args.config or repo_root / "assets" / "asset_roots.v1.json").resolve()
    index = build_index(repo_root, config_path)
    json_path, csv_path = write_outputs(repo_root, index)
    stats = index["stats"]
    print(f"indexed={stats['entry_count']} media={stats['media_count']} metadata={stats['metadata_count']} duplicates={stats['duplicate_group_count']} warnings={stats['warning_count']}")
    print(f"json={json_path}")
    print(f"csv={csv_path}")
    if args.check and any(w.get("code") == "READ_FAILED" for w in index["warnings"]):
        return 2
    if args.strict_canonical and stats["canonical_invalid_count"]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
