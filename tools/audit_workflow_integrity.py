"""Audit the video-kingdom workflow without calling any provider.

The audit checks the executable boundary and the contracts that can cause a
real production mistake. Historical experiment manifests are reported as
warnings and are never treated as active production routes.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validate_state_contract import validate_state_contract


REGISTRY = ROOT / "research" / "capability_registry.v2.json"
ROLE_REGISTRY = ROOT / "research" / "oneapi_role_room.v1.json"
EPISODE_CONTRACTS = Path(r"D:\视频创作\projects\张铁铁的沙雕日常\张铁铁的沙雕日常\项目文件\EP01_EP01_20260918T171515Z_CONTRACTS")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def audit() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    required = [
        ROOT / "tools" / "video_kingdom_entry.py",
        ROOT / "tools" / "production_shot_gate.py",
        ROOT / "tools" / "run_short_clip.py",
        ROOT / "tools" / "imagegen_shenwen.ps1",
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"missing executable: {path}")

    # A dirty worktree can make imports look healthy even when the same commit
    # cannot recover after a restart. Keep the production import closure
    # explicit and verify that each module is actually tracked when Git
    # metadata is available.
    required_runtime = [
        ROOT / "production_control" / "model_transport.py",
        ROOT / "production_control" / "image_assets.py",
        ROOT / "production_control" / "projection.py",
        ROOT / "tools" / "validate_script_prompt_review.py",
        ROOT / "tools" / "validate_new_drama_semantics.py",
    ]
    for path in required_runtime:
        if not path.is_file():
            errors.append(f"missing production runtime dependency: {path}")
    try:
        git_probe = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if git_probe.returncode == 0:
            for path in required_runtime:
                relative = path.relative_to(ROOT).as_posix()
                tracked = subprocess.run(
                    ["git", "ls-files", "--error-unmatch", "--", relative],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if tracked.returncode != 0:
                    errors.append(f"production runtime dependency is not tracked: {relative}")
        else:
            warnings.append("git metadata unavailable; tracked dependency closure could not be checked")
    except OSError:
        warnings.append("git metadata unavailable; tracked dependency closure could not be checked")
    projection_text = (ROOT / "production_control" / "projection.py").read_text(encoding="utf-8", errors="ignore") if (ROOT / "production_control" / "projection.py").is_file() else ""
    if "def prepare_model_request" not in projection_text:
        errors.append("production_control.projection missing prepare_model_request")

    registry = _load(REGISTRY)
    capabilities = {item.get("id"): item for item in registry.get("capabilities", []) if isinstance(item, dict)}
    video = capabilities.get("video.generate", {})
    if video.get("model") != "agnes-video-2.5-flash":
        errors.append("capability registry video route is not agnes-video-2.5-flash")
    image = capabilities.get("image.generate", {})
    if image.get("model") != "gpt-image-2":
        errors.append("capability registry image default is not gpt-image-2")
    for item in (video, image):
        executable = str(item.get("executable") or "").replace("/", "\\")
        if executable and not Path(executable).is_file():
            errors.append(f"registry executable missing: {executable}")

    runner = (ROOT / "tools" / "run_short_clip.py").read_text(encoding="utf-8")
    if 'args.admission_scope == "production" and args.model != "agnes-video-2.5-flash"' not in runner:
        errors.append("production runner does not hard-lock the Agnes Flash model")
    if "validate_production_shot" not in runner:
        errors.append("production runner bypasses production_shot_gate")

    template = _load(ROOT / "assets" / "templates" / "state_contract.v1.json")
    scene = template.get("scene_state", {})
    for field in ("location", "time", "lighting", "space", "physical_layout", "interaction_surface", "scene_mode"):
        if field not in scene:
            errors.append(f"state contract template missing scene field: {field}")
    sample = {
        "schema": "video_kingdom.state_contract.v1",
        "identity_ref": "sample",
        "episode_state": {"costume": "sample"},
        "scene_state": {"location": "room", "time": "night", "lighting": "lamp", "space": "room", "physical_layout": "floor desk chair", "interaction_surface": "desk", "scene_mode": "LIVE_DIEGETIC_SPACE"},
        "shot_state": {"start_pose": "standing", "primary_action": "pick up cup", "emotion_start_end": "calm to alert", "camera": "medium shot", "end_state": "holds cup"},
        "approved_for_next_shot": False,
    }
    if validate_state_contract(sample)["status"] != "PASS":
        errors.append("state contract validator rejects its own concrete baseline")

    role_registry = _load(ROLE_REGISTRY)
    role_ids = [str(role.get("role_id")) for role in role_registry.get("roles", []) if isinstance(role, dict)]
    if len(role_ids) != len(set(role_ids)):
        errors.append("role registry contains duplicate role ids")
    if any(str(role.get("model") or "") == "grok-4.5" for role in role_registry.get("roles", [])):
        warnings.append("role registry still contains historical grok-4.5; verify it is not selected")

    hardcoded_tmp = []
    for path in (ROOT / "tests").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"D:/tmp/ace-video-kingdom|D:\\\\tmp\\\\ace-video-kingdom", text):
            hardcoded_tmp.append(str(path))
    if hardcoded_tmp:
        errors.append("tests reference the historical D:/tmp clone: " + ", ".join(hardcoded_tmp))

    if EPISODE_CONTRACTS.is_dir():
        for path in EPISODE_CONTRACTS.glob("SHOT_*.json"):
            if any(token in path.name for token in ("RECEIPT", "SCRIPT_PROMPT", "FIVE_GATE")):
                continue
            try:
                data = _load(path)
            except Exception as exc:
                errors.append(f"invalid episode contract {path.name}: {exc}")
                continue
            if data.get("generation_allowed") is True:
                errors.append(f"stale episode contract still generation-enabled: {path.name}")
            if data.get("status") != "REWORK_REQUIRED":
                warnings.append(f"episode contract status is {data.get('status')!r}: {path.name}")
        warnings.append("historical episode receipts remain on disk but are excluded from production selection")

    return {"schema": "ace.video_kingdom.workflow_integrity_audit.v1", "status": "PASS" if not errors else "BLOCKED", "errors": errors, "warnings": warnings, "checked": {"entrypoint": True, "provider_gate": True, "model_registry": True, "state_contract": True, "episode_contracts": EPISODE_CONTRACTS.is_dir()}}


def main() -> int:
    result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
