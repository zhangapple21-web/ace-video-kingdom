"""Deterministic project discovery and manifest hashing."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_CANONICAL_ROOT = Path(r"D:\视频创作\ace-video-kingdom")
DEFAULT_COMPAT_ROOT = Path(r"D:\tmp\ace-video-kingdom")


def _load_manifest(root: Path) -> dict[str, Any]:
    path = root / "project_manifest.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("project_id") != "ace-video-kingdom":
        raise ValueError(f"PROJECT_MANIFEST_INVALID:{path}")
    return data


def manifest_hash(root: Path) -> str:
    data = _load_manifest(root)
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def discover_project(start: str | Path | None = None) -> dict[str, Any]:
    """Resolve one canonical project; never silently treats CWD as project root."""
    requested = Path(start).resolve() if start else None
    env_root = os.environ.get("ACE_PROJECT_ROOT")
    candidates: list[Path] = []
    if env_root:
        candidates.append(Path(env_root).resolve())
    if requested:
        current = requested if requested.is_dir() else requested.parent
        for parent in (current, *current.parents):
            if (parent / "project_manifest.v1.json").is_file():
                candidates.append(parent)
                break
    candidates.extend([DEFAULT_CANONICAL_ROOT, DEFAULT_COMPAT_ROOT])
    seen: set[str] = set()
    for root in candidates:
        key = str(root).lower()
        if key in seen or not root.is_dir() or not (root / "project_manifest.v1.json").is_file():
            continue
        seen.add(key)
        data = _load_manifest(root)
        canonical = Path(str(data.get("canonical_root", root))).resolve()
        if canonical.is_dir() and (canonical / "project_manifest.v1.json").is_file():
            source_root = canonical
        else:
            source_root = root
        return {
            "project_id": data["project_id"],
            "root": str(source_root),
            "requested_root": str(root),
            "canonical_root": str(canonical),
            "compatibility_roots": [str(Path(value).resolve()) for value in (data.get("compatibility_roots") or [])],
            "paths": dict(data.get("paths") or {}),
            "manifest": str((source_root / "project_manifest.v1.json").resolve()),
            "manifest_sha256": manifest_hash(source_root),
            "source_of_truth": "canonical_root",
        }
    raise FileNotFoundError("PROJECT_MANIFEST_NOT_FOUND")
