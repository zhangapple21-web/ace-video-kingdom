"""Check the local Video Kingdom runtime before a media task is dispatched."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "AGENTS.md",
    "research/REFERENCE_MINES.md",
    "research/oneapi_role_room.v1.json",
    "research/capability_registry.v2.json",
    "tools/creator_workflow.py",
)
REQUIRED_DIRS = ("assets", "research", "production_control", "runtime")
VOICE_RUNTIME_ROOT = Path(r"D:\视频创作\runtimes")


def check_environment(*, project_root: Path = PROJECT_ROOT) -> dict:
    project_root = project_root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    missing_files = [item for item in REQUIRED_FILES if not (project_root / item).is_file()]
    missing_dirs = [item for item in REQUIRED_DIRS if not (project_root / item).is_dir()]
    if missing_files:
        errors.append("missing_files:" + ",".join(missing_files))
    if missing_dirs:
        errors.append("missing_dirs:" + ",".join(missing_dirs))
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg:
        errors.append("ffmpeg_not_found")
    if not ffprobe:
        errors.append("ffprobe_not_found")
    cosy_python = VOICE_RUNTIME_ROOT / "cosyvoice3" / ".venv" / "Scripts" / "python.exe"
    cosy_model = VOICE_RUNTIME_ROOT / "cosyvoice3" / "model_cache" / "FunAudioLLM" / "Fun-CosyVoice3-0___5B-2512"
    edge_package = VOICE_RUNTIME_ROOT / "edge-tts" / "site-packages" / "edge_tts"
    if not cosy_python.is_file():
        errors.append("cosyvoice3_python_not_found")
    if not cosy_model.is_dir():
        errors.append("cosyvoice3_model_not_found")
    if not edge_package.is_dir():
        warnings.append("edge_tts_runtime_not_found")
    if not project_root.exists():
        errors.append("project_root_not_found")
        free_bytes = None
    else:
        free_bytes = shutil.disk_usage(project_root).free
        if free_bytes < 10 * 1024**3:
            warnings.append("disk_free_below_10GiB")
    try:
        probe = project_root / "research" / "REFERENCE_MINES.md"
        if probe.exists() and not probe.read_text(encoding="utf-8").strip():
            errors.append("reference_mines_empty")
    except OSError:
        errors.append("reference_mines_unreadable")
    return {
        "schema": "ace.video_kingdom.environment_preflight.v1",
        "status": "BLOCKED_ENVIRONMENT" if errors else "PASS",
        "project_root": str(project_root),
        "required_files": list(REQUIRED_FILES),
        "missing_files": missing_files,
        "missing_dirs": missing_dirs,
        "executables": {"ffmpeg": ffmpeg, "ffprobe": ffprobe},
        "voice_runtimes": {"cosyvoice3_python": str(cosy_python), "cosyvoice3_model": str(cosy_model), "edge_tts_package": str(edge_package)},
        "disk_free_bytes": free_bytes,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check_environment(project_root=args.project_root)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 1 if result["status"] == "BLOCKED_ENVIRONMENT" else 0


if __name__ == "__main__":
    raise SystemExit(main())
