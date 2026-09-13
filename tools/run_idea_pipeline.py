"""Turn one story idea into a resumable, evidence-bound short-drama run.

This is the command-line control plane for the existing Video Kingdom runner.
It absorbs the useful DramaAI/FastMovieAI shape (script -> storyboard ->
assets -> render -> QC -> assembly) without depending on either website.  It
does not create a second scheduler: one invocation owns one project and every
stage is recorded in a local receipt so a later invocation can resume safely.

By default the command attempts the whole run.  It stops before provider
submission when real reference assets are not available.  ``--plan-only`` is
the explicit no-network mode; ``--generate-assets`` and ``--run`` remain
backward-compatible aliases for the automatic stages.  No success is claimed
unless the existing deterministic preflight, manifest and media checks pass.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from PIL import Image
from typing import Any

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from measure_tts import measure_dialogue, load_manifest
except ImportError:  # support ``python -m tools.run_idea_pipeline``
    from tools.measure_tts import measure_dialogue, load_manifest

try:
    from content_control import build_episode_dynamic_plan, build_post_diagnostics, classify_route_failure, initial_content_control, validate_beat_shot_mapping
except ImportError:  # support ``python -m tools.run_idea_pipeline``
    from tools.content_control import build_episode_dynamic_plan, build_post_diagnostics, classify_route_failure, initial_content_control, validate_beat_shot_mapping

try:
    from medium_lock import character_performance_lock
except ImportError:  # support ``python -m tools.run_idea_pipeline``
    from tools.medium_lock import character_performance_lock

try:
    from creator_workflow import build_creator_brief, build_publish_recap, load_creator_brief, validate_creator_brief
except ImportError:  # support ``python -m tools.run_idea_pipeline``
    from tools.creator_workflow import build_creator_brief, build_publish_recap, load_creator_brief, validate_creator_brief

try:
    from validate_script_executability import (
        compile_causal_self_check,
        compile_continuity_bridge,
        compile_persona_card,
        compile_shot_prompt,
    )
except ImportError:  # support ``python -m tools.run_idea_pipeline``
    from tools.validate_script_executability import (
        compile_causal_self_check,
        compile_continuity_bridge,
        compile_persona_card,
        compile_shot_prompt,
    )

try:
    from runtime.provider_admission import admit_provider_request, assert_admission, build_canonical_generation_request, delivery_gate
except ImportError:  # support ``python -m tools.run_idea_pipeline``
    from tools.runtime.provider_admission import admit_provider_request, assert_admission, build_canonical_generation_request, delivery_gate  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
ROLE_DIR = ROOT / "roles"
RESEARCH_DIR = ROOT / "research"
IMAGE_MAX_BYTES = 500 * 1024


def _compress_image_bytes(raw: bytes, target: Path) -> Path:
    target = target.with_suffix(".webp")
    with Image.open(io.BytesIO(raw)) as source:
        image = source.convert("RGB")
        for scale in (1.0, 0.85, 0.7, 0.55, 0.4):
            candidate = image.copy()
            if scale != 1.0:
                candidate.thumbnail((max(1, int(image.width * scale)), max(1, int(image.height * scale))))
            for quality in (82, 70, 58, 46, 34):
                buffer = io.BytesIO()
                candidate.save(buffer, format="WEBP", quality=quality, method=6)
                if buffer.tell() < IMAGE_MAX_BYTES:
                    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
                    try:
                        with os.fdopen(fd, "wb") as handle:
                            handle.write(buffer.getvalue())
                            handle.flush()
                            os.fsync(handle.fileno())
                        os.replace(temporary_name, target)
                    finally:
                        Path(temporary_name).unlink(missing_ok=True)
                    return target
    raise RuntimeError(f"image could not be compressed below 500KB: {target.name}")


def _image_reference(path: Path) -> dict[str, object]:
    if path.suffix.lower() != ".webp" or not path.is_file() or path.stat().st_size >= IMAGE_MAX_BYTES:
        path = _compress_image_bytes(path.read_bytes(), path)
    with Image.open(path) as image:
        if image.format != "WEBP":
            raise RuntimeError(f"image is not WebP: {path.name}")
    size = path.stat().st_size
    if size >= IMAGE_MAX_BYTES:
        raise RuntimeError(f"image exceeds 500KB: {path.name}")
    return {"path": str(path.resolve()), "sha256": _sha256(path), "size_bytes": size}


def _is_valid_webp(path: Path) -> bool:
    if path.suffix.lower() != ".webp" or not path.is_file() or path.stat().st_size >= IMAGE_MAX_BYTES:
        return False
    try:
        with Image.open(path) as image:
            return image.format == "WEBP"
    except (OSError, ValueError):
        return False


def _materialize_image_response(result: dict[str, Any], target: Path) -> dict[str, object]:
    item = (result.get("data") or [{}])[0]
    raw = item.get("b64_json")
    if raw:
        decoded = base64.b64decode(raw, validate=True)
    else:
        image_url = item.get("url")
        if not isinstance(image_url, str) or not image_url.startswith(("https://", "http://")):
            raise RuntimeError(f"image provider returned no bounded image data for {target.name}")
        with urllib.request.urlopen(image_url, timeout=180) as response:
            decoded = response.read()
    target.parent.mkdir(parents=True, exist_ok=True)
    return _image_reference(_compress_image_bytes(decoded, target))


def _default_collaboration_context() -> dict[str, Any]:
    """Return the versioned role/hub contract used by every pipeline run.

    Keeping this check local and deterministic makes the default collaboration
    behavior visible in receipts instead of relying on a temporary chat
    agreement between windows.
    """
    planner = ROLE_DIR / "planner.md"
    executor = ROLE_DIR / "executor.md"
    hub = RESEARCH_DIR / "shared_information_hub.v1.json"
    missing = [str(path.relative_to(ROOT)) for path in (planner, executor, hub) if not path.is_file()]
    if missing:
        raise RuntimeError("default collaboration contract is incomplete: " + ", ".join(missing))
    return {
        "mode": "DEFAULT_MULTI_WINDOW",
        "planner": {"role_id": "planner", "contract": "roles/planner.md"},
        "executor": {"role_id": "executor", "contract": "roles/executor.md"},
        "shared_research": {
            "root": "research/",
            "contract": "research/shared_information_hub.v1.json",
        },
        "handoff": ["planner", "research", "executor", "research"],
        "execution_check": "tools/run_idea_pipeline.py::execution_conformance_check",
    }


def _planning_conformance_check(plan: dict[str, Any]) -> dict[str, Any]:
    """Check that a compiled plan satisfies the planner's declared standard."""
    errors: list[str] = []
    required = {"project_id", "scope", "production_integration", "story", "assets", "shots", "acceptance", "six_module_contract", "generation_contract"}
    errors.extend(f"missing plan field: {field}" for field in sorted(required - set(plan)))
    if plan.get("production_integration") is not False:
        errors.append("production_integration must remain false")
    generation_contract = plan.get("generation_contract")
    if not isinstance(generation_contract, dict):
        errors.append("generation_contract must be an object")
    else:
        for field in ("main_generation_instruction", "character_identity_lock", "shot_contract_constraints", "forbidden_behavior", "acceptance_standard"):
            if generation_contract.get(field) in (None, "", []):
                errors.append(f"generation_contract missing {field}")
        constraints = generation_contract.get("shot_contract_constraints", {})
        if constraints.get("camera_autonomy") != "OFF" or constraints.get("scene_transition_autonomy") != "OFF" or constraints.get("secondary_action_autonomy") != "OFF":
            errors.append("generation_contract autonomy locks must be OFF")
    collaboration = plan.get("collaboration")
    if not isinstance(collaboration, dict) or collaboration.get("mode") != "DEFAULT_MULTI_WINDOW":
        errors.append("plan must declare DEFAULT_MULTI_WINDOW collaboration")
    shots = plan.get("shots") if isinstance(plan.get("shots"), list) else []
    if not shots:
        errors.append("plan must contain at least one shot")
    shot_ids: list[str] = []
    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            errors.append(f"shot {index} is not an object")
            continue
        shot_id = shot.get("shot_id")
        if not shot_id:
            errors.append(f"shot {index} is missing shot_id")
        else:
            shot_ids.append(str(shot_id))
        for field in (
            "prompt", "camera", "continuity_bridge", "render", "shot_contract",
            "required_asset_ids", "first_state", "action", "last_state",
            "dramatic_function", "information_gain", "emotion_change", "quality_gate",
        ):
            if not shot.get(field):
                errors.append(f"{shot_id or index} is missing {field}")
        beats = shot.get("action_beats")
        if not isinstance(beats, list) or len(beats) != 3 or any(not str(item).strip() for item in beats):
            errors.append(f"{shot_id or index} must declare exactly three action_beats")
        contract = shot.get("shot_contract") if isinstance(shot.get("shot_contract"), dict) else {}
        if contract.get("single_action") is not True or contract.get("max_primary_actions") != 1 or contract.get("internal_cuts_allowed") != 0:
            errors.append(f"{shot_id or index} violates single-action shot contract")
    dynamic = plan.get("dynamic_content_plan")
    if not isinstance(dynamic, dict):
        errors.append("dynamic_content_plan must be an object")
    else:
        mapping = validate_beat_shot_mapping(dynamic, shots)
        errors.extend(f"beat_shot_mapping: {item}" for item in mapping["errors"])
        if dynamic.get("pacing_profile", {}).get("dialogue", {}).get("role") != "diagnostic":
            errors.append("dialogue pacing must remain diagnostic")
    duplicates = sorted({item for item in shot_ids if shot_ids.count(item) > 1})
    errors.extend(f"duplicate shot_id: {item}" for item in duplicates)
    return {
        "schema": "ace.video_kingdom.planning_conformance.v1",
        "status": "PASS" if not errors else "FAIL",
        "verdict": "PASS" if not errors else "BLOCKED",
        "project_id": plan.get("project_id"),
        "shot_count": len(shots),
        "shot_ids": shot_ids,
        "checks": ["default roles present", "shared research hub declared", "formal shot contract fields"],
        "errors": errors,
    }


def execution_conformance_check(plan: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    """Verify execution receipts and media match the immutable plan.

    This deliberately reads only local receipts and hashes.  It is the final
    cross-window gate: a successful subprocess alone cannot promote a run when
    its artifacts do not correspond to the planner's shot list.
    """
    errors: list[str] = []
    manifest_path = project_dir / "manifest.json"
    acceptance_path = project_dir / "acceptance_receipt.json"
    expected = [str(shot.get("shot_id")) for shot in plan.get("shots", []) if isinstance(shot, dict) and shot.get("shot_id")]
    records: list[dict[str, Any]] = []
    if not manifest_path.is_file():
        errors.append("manifest.json is missing")
    else:
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            records = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) else [])
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"manifest.json is unreadable: {type(exc).__name__}")
    record_ids = [str(row.get("shot_id")) for row in records if isinstance(row, dict) and row.get("shot_id")]
    duplicate_records = sorted({item for item in record_ids if record_ids.count(item) > 1})
    errors.extend(f"duplicate execution receipt for {shot_id}" for shot_id in duplicate_records)
    by_id = {str(row.get("shot_id")): row for row in records if isinstance(row, dict) and row.get("shot_id")}
    actual = sorted(by_id)
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    errors.extend(f"missing execution receipt for {shot_id}" for shot_id in missing)
    errors.extend(f"plan-external execution receipt for {shot_id}" for shot_id in extra)
    for shot_id in expected:
        row = by_id.get(shot_id)
        if not row:
            continue
        if row.get("status") != "COMPLETED":
            errors.append(f"{shot_id} status is not COMPLETED")
        if not row.get("video_id"):
            errors.append(f"{shot_id} is missing durable video_id")
        artifact = _resolve_execution_path(project_dir, row.get("artifact_path"))
        if not artifact.is_file():
            errors.append(f"{shot_id} artifact is missing")
            continue
        recorded_hash = row.get("artifact_sha256")
        actual_hash = _sha256(artifact)
        if not recorded_hash or recorded_hash != actual_hash:
            errors.append(f"{shot_id} artifact SHA-256 mismatch")
    acceptance: dict[str, Any] = {}
    if not acceptance_path.is_file():
        errors.append("acceptance_receipt.json is missing")
    else:
        try:
            acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"acceptance_receipt.json is unreadable: {type(exc).__name__}")
        if acceptance.get("status") != "PASS":
            errors.append(f"final acceptance status is {acceptance.get('status')!r}, expected 'PASS'")
        if acceptance.get("delivery_approved") is not True:
            errors.append("delivery_approved must be true for execution conformance")
        for lane in ("continuity", "subtitle", "audio", "creative"):
            value = acceptance.get(lane)
            if isinstance(value, dict):
                value = value.get("status")
            if value != "PASS":
                errors.append(f"delivery lane {lane} is {value!r}, expected 'PASS'")
        delivery_gate_receipt = acceptance.get("delivery_gate")
        if not isinstance(delivery_gate_receipt, dict):
            errors.append("canonical delivery gate receipt is missing")
        else:
            if delivery_gate_receipt.get("delivery_approved") is not True:
                errors.append("delivery gate receipt is not approved")
            gate_statuses = delivery_gate_receipt.get("statuses")
            if not isinstance(gate_statuses, dict):
                errors.append("canonical delivery gate statuses are missing")
            else:
                recomputed_gate = delivery_gate(gate_statuses)
                if recomputed_gate["delivery_approved"] is not True:
                    errors.append("canonical delivery gate statuses are not all PASS")
                if delivery_gate_receipt.get("status") != recomputed_gate["status"]:
                    errors.append("canonical delivery gate status is inconsistent")
        output = _resolve_execution_path(project_dir, acceptance.get("output"))
        if not output.is_file():
            errors.append("accepted output artifact is missing")
    return {
        "schema": "ace.video_kingdom.execution_conformance.v1",
        "status": "PASS" if not errors else "FAIL",
        "verdict": "PASS" if not errors else "BLOCKED",
        "project_id": plan.get("project_id"),
        "expected_shot_ids": expected,
        "actual_shot_ids": actual,
        "manifest": str(manifest_path),
        "acceptance_receipt": str(acceptance_path),
        "errors": errors,
    }


def generation_conformance_check(plan: dict[str, Any]) -> dict[str, Any]:
    """Fail closed when the five hard generation sections are not in requests."""
    errors: list[str] = []
    contract = plan.get("generation_contract")
    required = ("main_generation_instruction", "character_identity_lock", "shot_contract_constraints", "forbidden_behavior", "acceptance_standard")
    if not isinstance(contract, dict):
        errors.append("generation_contract is missing")
        contract = {}
    for field in required:
        if contract.get(field) in (None, "", []):
            errors.append(f"generation_contract missing {field}")
    shots = plan.get("shots") if isinstance(plan.get("shots"), list) else []
    for shot in shots:
        if not isinstance(shot, dict):
            errors.append("shot is not an object")
            continue
        shot_id = str(shot.get("shot_id", "unknown"))
        request = shot.get("generation_request")
        if not isinstance(request, dict):
            errors.append(f"{shot_id} missing generation_request")
            continue
        for field in required:
            if request.get(field) in (None, "", []):
                errors.append(f"{shot_id} generation_request missing {field}")
        if not isinstance(request.get("allowed_characters"), list) or not request.get("allowed_characters"):
            errors.append(f"{shot_id} generation_request.allowed_characters is missing")
        if "required_on_screen_text" not in request:
            errors.append(f"{shot_id} generation_request.required_on_screen_text is missing")
        request_contract = request.get("shot_contract") if isinstance(request.get("shot_contract"), dict) else {}
        shot_contract = shot.get("shot_contract") if isinstance(shot.get("shot_contract"), dict) else {}
        for field in ("single_action", "max_primary_actions", "internal_cuts_allowed", "camera_autonomy", "scene_transition_autonomy", "secondary_action_autonomy"):
            if request_contract.get(field) != shot_contract.get(field):
                errors.append(f"{shot_id} request/shot contract mismatch: {field}")
        prompt = str(shot.get("prompt", ""))
        if "主生成指令" not in prompt or "禁止行为" not in prompt:
            errors.append(f"{shot_id} prompt does not contain compiled hard sections")
        render = shot.get("render") if isinstance(shot.get("render"), dict) else {}
        if not str(render.get("negative_prompt", "")).strip():
            errors.append(f"{shot_id} render.negative_prompt is missing")
    return {
        "schema": "ace.video_kingdom.generation_conformance.v1",
        "status": "PASS" if not errors else "FAIL",
        "verdict": "PASS" if not errors else "BLOCKED",
        "project_id": plan.get("project_id"),
        "shot_count": len(shots),
        "errors": errors,
    }


# Private spelling kept for callers/tests that prefer the validation naming.
_validate_execution_result = execution_conformance_check
_validate_execution_against_plan = execution_conformance_check
_auto_check_execution = execution_conformance_check


def _resolve_execution_path(project_dir: Path, raw: Any) -> Path:
    """Resolve repository-relative and project-relative receipt paths."""
    candidate = Path(str(raw or ""))
    if candidate.is_absolute():
        return candidate
    repo_relative = (ROOT / candidate).resolve()
    project_relative = (project_dir / candidate).resolve()
    if repo_relative.is_file():
        return repo_relative
    return project_relative


def _slug(value: str) -> str:
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", value).strip("-").lower()
    return (text[:48] or "idea")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _duration_estimate(text: str) -> float:
    # Display-only estimate for pending plans. Never write this as measured TTS.
    han = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z0-9]", text))
    return round(max(1.4, min(10.0, han * 0.22 + latin * 0.07)), 3)


def _make_dossier(character_id: str, name: str, role: str, anchor_hash: str) -> dict[str, Any]:
    return {
        "schema": "video_kingdom.character_dossier.v1",
        "character_id": character_id,
        "name": name,
        "role": role,
        "fictional_character": True,
        "production_integration": False,
        "rights_and_provenance": {"source": "user_idea_compiler", "disallowed_sources": ["UNAUTHORIZED_REAL_PERSON_LIKENESS"]},
        "persona_card": compile_persona_card(character_id, name, role),
        "identity_invariants": {
            "visual": f"原创虚构角色 {name}；服装和年龄段在本项目内固定",
            "negative_constraints": ["不使用现实人物肖像", "不加入品牌标识", "不改变角色身份"],
            "behavioral": "行为由当前镜头动作弧驱动，不靠口号代替表演",
            "relational": f"{name} 的关系位置保持为 {role}",
        },
        "allowed_evolution": {"may_change": ["情绪", "姿态", "道具状态"], "requires_new_dossier_version": True},
        "visual_assets": [{"anchor_id": f"{character_id}_reference", "sha256": anchor_hash}],
    }


def _build_generation_contract(*, idea: str, setting: str, characters: list[dict[str, Any]],
                               forbidden: list[str]) -> dict[str, Any]:
    """Compile the five hard generation sections into machine-readable data.

    These fields are intentionally repeated into every shot request below. A
    reviewer can therefore compare the request that reached the provider with
    the director's contract instead of trusting a free-form prompt summary.
    """
    identity_lock = {
        "characters": characters,
        "visual_invariants": [
            "中国审美写实短剧摄影",
            "东亚面部比例自然，五官、发型、服装在镜头间保持一致",
            "服装无品牌、无文字、无现实人物肖像",
        ],
        "relationship_invariants": "人物关系、视线方向和空间位置不得被模型重写",
    }
    acceptance = {
        "per_shot": [
            "audit_video_pacing status=PASS",
            "internal_scene_cut_count=0",
            "TTS 时长 + 0.6 秒 recovery hold 被覆盖",
            "shot contract single_action=true, max_primary_actions=1",
            "首态/动作/末态可在抽帧中复核，人物身份与关系连续",
        ],
        "episode": [
            "全部镜头逐镜 PASS 后才允许合成",
            "媒体完整性、连续性和导演语义审阅同时通过",
            "技术 PASS 不得覆盖 REWORK/REVIEW_REQUIRED",
        ],
    }
    return {
        "schema": "ace.video_kingdom.generation_contract.v1",
        "main_generation_instruction": (
            f"严格还原可核对的故事场景：{idea[:240]}；地点为{setting}。"
            "只执行当前镜头的一个主要视觉事件，保持自然表演和中国短剧电影质感。"
        ),
        "character_identity_lock": identity_lock,
        "shot_contract_constraints": {
            "single_action": True,
            "max_primary_actions": 1,
            "internal_cuts_allowed": 0,
            "camera_autonomy": "OFF",
            "scene_transition_autonomy": "OFF",
            "secondary_action_autonomy": "OFF",
            "requires_first_state": True,
            "requires_last_state": True,
            "allowed_characters_required": True,
            "screen_text_policy": "source_bound",
        },
        "forbidden_behavior": forbidden,
        "acceptance_standard": acceptance,
    }


def _compile(
    idea: str,
    project_dir: Path,
    project_id: str,
    target_seconds: int | None = None,
    tts_measurements: dict[str, dict[str, Any]] | None = None,
    creator_brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile a safe, small six-shot plan from free text."""
    title = idea.splitlines()[0].strip()[:42] or "未命名短剧"
    chars = [
        ("CHAR_MAIN", "主角", "观察者与行动者"),
        ("CHAR_COUNTER", "对手", "规则受益者"),
    ]
    code_rescue = bool(re.search(r"程序员|代码|求救|编程|服务器|日志", idea))
    revenge_return = bool(re.search(r"孤坟|墓|祭父|复仇|仇家|车灯|退役战士|退伍军人|海外归来", idea))
    scenes = [
        ("SC01", "建立处境"), ("SC02", "发现异常"), ("SC03", "尝试验证"),
        ("SC04", "代价出现"), ("SC05", "做出选择"), ("SC06", "留下证据"),
    ]
    props = [("PROP_PHONE", "手机或记录设备"), ("PROP_TOKEN", "代表规则的关键物件")]
    for asset_id, name, _ in chars:
        ref = project_dir / "assets" / f"{asset_id.lower()}_reference.webp"
        ref.parent.mkdir(parents=True, exist_ok=True)
        dossier = project_dir / "assets" / f"{asset_id.lower()}_dossier.json"
        reference_hash = _image_reference(ref)["sha256"] if ref.is_file() else "PENDING_PROVIDER_ASSET"
        _write_json(dossier, _make_dossier(asset_id, name, chars[0][2] if asset_id == "CHAR_MAIN" else chars[1][2], str(reference_hash)))
    for asset_id, _ in scenes + props:
        ref = project_dir / "assets" / f"{asset_id.lower()}_anchor.webp"
        ref.parent.mkdir(parents=True, exist_ok=True)

    if code_rescue:
        dialogue = [
            "凌晨两点，服务器还在跑。",
            "这不是注释，是求救。",
            "时间戳对上了。有人在里面。",
            "别查了。它醒了。",
            "我不删。",
            "我把求救带出去。",
        ]
        actions = [
            "主角按下回车唤醒深夜服务器终端",
            "主角把光标停在一行异常注释上",
            "主角把日志时间戳与提交记录并排对照",
            "主角拔掉终端网线",
            "主角将可疑提交标记为保留",
            "主角按下离线硬盘的加密保存键",
        ]
        scene_titles = ["深夜值守", "隐藏注释", "时间戳核对", "异常唤醒", "保留证据", "离线求救"]
        scenes = [(scene_id, scene_titles[i]) for i, (scene_id, _) in enumerate(scenes)]
    elif revenge_return:
        # Originalized mechanism adaptation: preserve only the broad dramatic
        # engine (return -> memorial clue -> approaching threat), never lift
        # source prose, names, places, or proprietary setting details.
        dialogue = [
            "我回来了，爸。",
            "墓碑被人动过。",
            "这不是意外。",
            "车灯来了。",
            "证据先带走。",
            "我会查到底。",
        ]
        actions = [
            "主角在孤坟前放下旧军牌并站定",
            "主角抚去墓碑上的新土露出刻痕",
            "主角从土中取出折叠的死亡记录",
            "主角回头看向逼近的车灯并握紧证据",
            "主角将记录藏入旧军牌内侧",
            "主角转身离开墓前走入雨幕",
        ]
        scene_titles = ["归来祭父", "新土刻痕", "死亡疑点", "车灯逼近", "藏下证据", "雨中离开"]
        scenes = [(scene_id, scene_titles[i]) for i, (scene_id, _) in enumerate(scenes)]
    else:
        dialogue = [
            "先把事情记下来，别让它被一句话带走。",
            "这里的数字，和刚才看到的不一样。",
            "我只验证一件事：谁在获利，谁在承担代价。",
            "你继续追问，就会失去现在的位置。",
            "位置可以让，证据不能丢。",
            "如果规则不能被复核，它就不该替我们做决定。",
        ]
        actions = [
            "主角打开记录界面",
            "主角停在矛盾数字上",
            "主角拍下关键物件",
            "对手遮住记录",
            "主角标记证据为保留",
            "主角按下第二设备的保存键",
        ]
    shot_seconds = 6 if target_seconds is None else max(4, min(12, round(target_seconds / 6)))
    shot_frames = shot_seconds * 8 + 1
    generation_contract = _build_generation_contract(
        idea=idea,
        setting=("深夜值守机房" if code_rescue else ("荒山孤坟与冷雨" if revenge_return else "深夜室内记录台")),
        characters=[
            {"asset_id": "CHAR_MAIN", "identity": "主角；年龄、脸型、发型、服装固定", "role": "观察者与行动者"},
            {"asset_id": "CHAR_COUNTER", "identity": "对手；仅在剧本明确要求时出现", "role": "关系中的另一方"},
        ],
        forbidden=[
            "不得新增人物、改变人物关系或替换角色身份",
            "不得改变地点、时间、天气、服装、道具状态或屏幕轴线",
            "不得推拉摇移、自动转场、内部切镜或插入第二个主要动作",
            "不得生成可读字幕、logo、品牌、现实机构标识或宣传/MV画面",
            "不得美化、补写小说未给出的动作、对白、因果或情绪",
        ],
    )
    shots: list[dict[str, Any]] = []
    sidecar_shots: list[dict[str, Any]] = []
    for index, (scene_id, scene_name) in enumerate(scenes, start=1):
        shot_id = f"S{index:02d}A"
        measurement = (tts_measurements or {}).get(shot_id)
        tts = measurement.get("duration_seconds") if isinstance(measurement, dict) else None
        if isinstance(tts, (int, float)) and tts > 0:
            tts = round(float(tts), 3)
            # Keep the measured-TTS lower bound while honoring an explicit
            # episode target.  Six-shot pilots should not silently collapse
            # to 24s just because short lines have short WAVs; the target
            # provides the editorial floor and the TTS+recovery value remains
            # the hard minimum for each shot.
            target_floor = (float(target_seconds) / 6.0) if target_seconds else 2.5
            duration = round(max(2.5, target_floor, tts + 0.6), 3)
            render_seconds = max(4, min(12, math.ceil(duration)))
            audio_status = "MEASURED"
            duration_source = "tts_measured_plus_recovery_hold"
        else:
            tts = None
            duration = None
            render_seconds = shot_seconds
            audio_status = "AUDIO_PENDING"
            duration_source = "PENDING_TTS"
        anchor = f"assets/{scene_id.lower()}_anchor.webp"
        identity = "assets/char_main_reference.webp"
        # Dialogue is locked and measured separately.  Keeping it out of the
        # visual prompt prevents the video model from attempting to render
        # multiple beats, subtitles, or a second scene inside one clip.
        visual_hint = "抽象求救标记但不生成可读文字" if code_rescue else ("墓碑刻痕与折叠记录但不生成可读文字" if revenge_return else "抽象记录标记但不生成可读文字")
        setting_hint = "深夜值守机房" if code_rescue else ("荒山孤坟、冷雨与远处车灯" if revenge_return else "深夜室内记录台")
        shot_contract = {
            "version": "ace.video_kingdom.single_action_shot_contract.v1",
            "single_action": True,
            "action_unit": actions[index - 1],
            "max_primary_actions": 1,
            "internal_cuts_allowed": 0,
            "camera_autonomy": "OFF",
            "scene_transition_autonomy": "OFF",
            "secondary_action_autonomy": "OFF",
            "cut_policy": "cut only after action completion and recovery hold",
        }
        shot_request = {
            "main_generation_instruction": generation_contract["main_generation_instruction"],
            "character_identity_lock": generation_contract["character_identity_lock"],
            "allowed_characters": ["CHAR_MAIN"],
            "required_on_screen_text": [],
            "shot_contract_constraints": generation_contract["shot_contract_constraints"],
            "shot_contract": shot_contract | {
                "first_state": f"{scene_name}前的稳定构图与角色身份",
                "primary_visual_event": actions[index - 1],
                "last_state": "动作完成后保留反应与留白",
            },
            "forbidden_behavior": generation_contract["forbidden_behavior"],
            "acceptance_standard": generation_contract["acceptance_standard"]["per_shot"],
        }
        # Keep a human-readable compiler trace in the actual request. The
        # provider still receives one prompt, but no longer has to infer the
        # identity/forbidden-action contract from vague adjectives.
        first_state = f"{scene_name}前的稳定构图与角色身份"
        last_state = "动作完成后保留反应与留白"
        next_scene = scenes[index][1] if index < 6 else "证据留存"
        next_shot_id = f"S{index + 1:02d}A" if index < 6 else None
        camera_fixed = index in (1, 2, 6)
        style_baseline = "竖屏9:16，中国审美写实短剧摄影，东亚面部比例自然，服装无品牌无文字"
        opening_space = f"{setting_hint}；主体=CHAR_MAIN；首态={first_state}；中近景；{'固定机位' if camera_fixed else '一次目的性运镜'}"
        underscore = "环境底噪与单次道具动作音；对白不渲染为画面文字"
        timed_action = f"0-1s保持首态；唯一主要视觉事件={actions[index - 1]}；收势后内部切镜=0"
        aftertaste = f"{last_state}；末帧交给{next_shot_id or '终章留存'}"
        txt_prompt_elements = {
            "subject": "CHAR_MAIN",
            "action": actions[index - 1],
            "environment": setting_hint,
            "lighting": "克制的电影实用光",
            "camera": "medium close-up, FIXED_DIALOGUE" if camera_fixed else "medium close-up, ONE_PURPOSEFUL_MOVE",
            "style": "写实短剧，竖屏9:16",
        }
        prompt, shot_prompt = compile_shot_prompt(
            main_generation_instruction=shot_request["main_generation_instruction"],
            identity_lock="主角身份与服装固定，关系不可改写",
            first_state=first_state,
            action=actions[index - 1],
            last_state=last_state,
            forbidden=generation_contract["forbidden_behavior"],
            setting_hint=setting_hint,
            visual_hint=visual_hint,
            style_baseline=style_baseline,
            opening_space=opening_space,
            underscore=underscore,
            timed_action=timed_action,
            aftertaste=aftertaste,
            txt_prompt_elements=txt_prompt_elements,
        )
        continuity_bridge = compile_continuity_bridge(
            from_shot=shot_id,
            to_shot=next_shot_id,
            label=f"{scene_id} -> {next_shot_id}" if next_shot_id else "证据留存",
            previous_end_frame_state=last_state,
            next_initial_state=f"{next_scene}前的稳定构图与角色身份" if next_shot_id else "证据留存",
            exit_direction="hold" if next_shot_id else "none",
            enter_direction="hold",
            inherited_state_items=[
                {"key": "costume", "value": "深色无品牌无文字层装", "source_shot": shot_id},
                {"key": "identity", "value": "CHAR_MAIN 身份与年龄段固定", "source_shot": shot_id},
                {"key": "spatial_position", "value": setting_hint, "source_shot": shot_id},
            ],
            terminal=next_shot_id is None,
        )
        shots.append({
            "shot_id": shot_id, "scene_id": scene_id, "prompt": prompt,
            "shot_prompt": shot_prompt,
            "action_beats": [f"首态：{scene_name}前的稳定构图", f"动作：{actions[index - 1]}", "末态：动作完成后保留反应与留白"],
            "required_asset_ids": ["CHAR_MAIN", "PROP_PHONE", "PROP_TOKEN", scene_id],
            "first_state": first_state,
            "action": actions[index - 1],
            "last_state": last_state,
            "continuity_bridge_to_next": continuity_bridge["label"],
            "quality_gate": "抽帧无内部切镜、身份连续、动作完成、对白不截断",
            "camera": {"shot_type": "dialogue" if camera_fixed else "action", "scale": "medium close-up", "movement": "FIXED_DIALOGUE" if camera_fixed else "ONE_PURPOSEFUL_MOVE", "axis": "screen-left facing screen-right", "movement_count": 0 if camera_fixed else 1},
            "dramatic_function": scene_name, "information_gain": dialogue[index - 1], "emotion_change": "由迟疑走向可验证的选择",
            "continuity_bridge": continuity_bridge,
            "anchor_reuse_allowed": False,
            "shot_contract": shot_contract,
            "generation_request": shot_request,
            "render": {"model": "agnes-video-2.5-flash", "seconds": render_seconds, "width": 704, "height": 1280, "num_frames": render_seconds * 8 + 1, "frame_rate": 8, "image": anchor, "fallback_image": anchor,
                       "negative_prompt": "; ".join(generation_contract["forbidden_behavior"])},
        })
        sidecar_shots.append({
            "shot_id": shot_id, "source_scene": f"{scene_name}：{actions[index - 1]}", "anchor_reuse_allowed": False,
            "shot_contract": shot_contract,
            "generation_request": shot_request,
            "script": {"scene_id": scene_id, "speaker": "CHAR_MAIN", "dialogue_text": dialogue[index - 1], "emotion": "focused", "line_locked": True, "tts_duration_seconds": tts, "audio_status": audio_status},
            "camera": shots[-1]["camera"] | {"first_frame_kind": "scene_action_anchor"},
            "edit": {"duration_seconds": duration, "render_seconds": render_seconds, "duration_source": duration_source, "cut_after_performance": True, "transition_reason": "cut after performance and 0.6s reaction hold", "rhythm_phase": "investigation"},
            "performance": {"emotion_goal": "由迟疑走向可验证的选择", "action_beats": shots[-1]["action_beats"], "sound_cues": ["dialogue or room tone", "single prop foley"]},
            "assets": {"identity_reference": identity, "scene_action_anchor": anchor, "costume": "project identity invariant", "props": ["PROP_PHONE", "PROP_TOKEN"], "lighting": "restrained cinematic practical light", "space": "same night-shift coding room"},
            "recovery": {"max_attempts": 2, "retry_delay_policy": "Retry-After first; otherwise >=60s provider cooldown", "degrade_order": ["retry with seed offset", "manual replacement marker retaining failure evidence"]},
        })

    asset_entries: dict[str, list[dict[str, Any]]] = {"characters": [], "scenes": [], "props": []}
    for group, rows in (("characters", chars), ("scenes", scenes), ("props", props)):
        for asset_id, name, *role in rows:
            suffix = "reference" if group == "characters" else "anchor"
            path = project_dir / "assets" / f"{asset_id.lower()}_{suffix}.webp"
            item = {"asset_id": asset_id, "name": name, "status": "APPROVED_REFERENCE_SHEET" if path.is_file() else "PENDING_PROVIDER_ASSET", "reference_path": f"assets/{path.name}"}
            if path.is_file():
                item["reference"] = _image_reference(path)
            if group == "characters":
                item["dossier_path"] = f"assets/{asset_id.lower()}_dossier.json"
                item["persona_card"] = compile_persona_card(asset_id, name, role[0] if role else "未标明关系")
            asset_entries[group].append(item)

    contract = {
        "contract_version": "video_kingdom.six_module_shot_contract.idea_compiler.v2", "production_boundary": "RESEARCH_ONLY", "project_id": project_id,
        "quality_mode": "FORMAL", "premise": idea, "causal_chain": ["处境建立", "异常显现", "验证行动", "代价出现", "选择", "证据留存"],
        "plants": ["矛盾记录", "关键物件"], "payoffs": ["规则被复核", "证据脱离单一席位"], "viewer_knowledge_checkpoints": ["观众知道记录存在矛盾", "观众看到验证动作", "结尾保留可复核证据"], "shots": sidecar_shots,
        "timing_policy": "tts_first; measured dialogue plus 0.6s recovery hold; no character-count timing",
        "generation_contract": generation_contract,
    }
    brief = creator_brief or build_creator_brief(title=title, target_seconds=target_seconds)
    plan = {
        "schema": "video_kingdom.idea_pipeline_plan.v1", "project_id": project_id, "status": "COMPILED", "title": title, "scope": "FREE_ZONE_RESEARCH_ONLY", "production_integration": False, "medium_lock": character_performance_lock(source_kind="ORIGINAL_STORY", signed_by="idea_pipeline"),
        "collaboration": _default_collaboration_context(),
        "source_rights_note": "由用户提供的原创想法编译；未读取私密材料，未使用现实人物肖像。", "quality_mode": "FORMAL", "story": {"root_brief": {"theme": "规则、位置与可验证证据", "relationship_and_conflict": "行动者与规则受益者之间的验证冲突", "mainline_events": contract["causal_chain"], "source_rights_note": "user_idea_only", "semantic_anchor_type": "rule_and_evidence"}, "scene_nodes": [{"scene_id": s[0], "title": s[1]} for s in scenes]},
        "assets": asset_entries, "six_module_contract": "six_module_contract.json", "generation_contract": generation_contract, "render_defaults": {"model": "agnes-video-2.5-flash", "seconds": shot_seconds, "width": 704, "height": 1280, "num_frames": shot_frames, "frame_rate": 8, "duration_source": "per_shot_tts_measurement"},
        "shots": shots, "acceptance": {"duration_window_seconds": ([15, 70] if target_seconds is None else [max(15, target_seconds - 2), target_seconds + 2]), "must_have_receipts": True, "must_pass_media_integrity": True},
        "renderer_routing": {"mainline_identity_requires": "VERIFIED_REFERENCE_CONTROLLED_RENDERER", "agnes_video_2_5_flash": "PRIMARY_FREE_REFERENCE_CONTROLLED_RENDERER"},
        "premise": contract["premise"],
        "causal_chain": contract["causal_chain"],
        "plants": contract["plants"],
        "payoffs": contract["payoffs"],
        "viewer_knowledge_checkpoints": contract["viewer_knowledge_checkpoints"],
        "creator_brief": brief,
        "publish_recap": build_publish_recap(project_id=project_id, brief=brief),
    }
    dynamic_plan = build_episode_dynamic_plan(idea=idea, plan=plan, target_seconds=target_seconds)
    plan["dynamic_content_plan"] = dynamic_plan
    plan["content_control"] = initial_content_control()
    plan["content_control"]["run_id"] = project_id
    plan["content_control"]["canonical_story_immutable"] = True
    beat_ids_by_shot = {
        str(beat["mapped_shots"][0]): [beat["beat_id"]]
        for beat in dynamic_plan["beats"] if beat.get("mapped_shots")
    }
    for shot in shots:
        shot["beat_ids"] = beat_ids_by_shot.get(str(shot.get("shot_id")), [])
        shot["content_state"] = "R0"
        shot["content_lineage_ref"] = "content_control.v1.json"
        shot["medium_lock"] = plan["medium_lock"]
    for shot in sidecar_shots:
        shot["beat_ids"] = beat_ids_by_shot.get(str(shot.get("shot_id")), [])
        shot["content_state"] = "R0"
        shot["content_lineage_ref"] = "content_control.v1.json"
    contract["dynamic_content_plan_ref"] = "episode_dynamic_plan.json"
    contract["content_control_ref"] = "content_control.v1.json"
    plan["narrative_causal_self_check"] = compile_causal_self_check(plan)
    contract["narrative_causal_self_check"] = plan["narrative_causal_self_check"]
    _write_json(project_dir / "six_module_contract.json", contract)
    _write_json(project_dir / "episode_dynamic_plan.json", dynamic_plan)
    _write_json(project_dir / "content_control.v1.json", plan["content_control"])
    _write_json(project_dir / "episode_plan.json", plan)
    return plan


def _generate_assets(project_dir: Path, idea: str, *, force: bool = False) -> tuple[bool, str]:
    """Generate anchors through the configured OpenAI-compatible image lane.

    The key is read only in memory and is never included in receipts or
    command output.  If the lane is unavailable we fail closed and retain the
    compiled placeholders for inspection.
    """
    # Resume runs should reuse already-approved anchors.  The image lane is
    # only needed when a placeholder remains (or when the caller explicitly
    # asks for a refresh); this keeps the pipeline resumable and avoids
    # silently replacing the identity graph on every invocation.
    key = os.getenv("SHENWEN_IMAGE_API_KEY") or os.getenv("SHENWEN_API_KEY")
    base = os.getenv("SHENWEN_IMAGE_BASE_URL", "https://api.shenwenai.com/v1").rstrip("/")
    assets_dir = project_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    try:
        compiled_plan = json.loads((project_dir / "episode_plan.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        compiled_plan = {}
    expected_assets = [
        assets_dir / str(item["reference_path"]).removeprefix("assets/")
        for group in compiled_plan.get("assets", {}).values()
        if isinstance(group, list)
        for item in group
        if isinstance(item, dict) and item.get("reference_path")
    ]
    assets = sorted(set(expected_assets))
    pending = [path for path in assets if force or not _is_valid_webp(path)]
    if not pending:
        return True, "reused existing approved assets"
    if not key:
        return False, "SHENWEN_IMAGE_API_KEY/SHENWEN_API_KEY is unavailable for placeholder assets"
    try:
        compiled_plan = json.loads((project_dir / "episode_plan.json").read_text(encoding="utf-8"))
        generation_contract = compiled_plan.get("generation_contract", {})
    except (OSError, json.JSONDecodeError):
        generation_contract = {}
    identity_text = "主角身份、脸型、发型、服装固定；人物关系不可改写"
    forbidden_text = "不新增人物、不改地点时间、不加文字logo、不自动导演、不生成第二动作"
    if isinstance(generation_contract, dict):
        lock = generation_contract.get("character_identity_lock", {})
        if isinstance(lock, dict) and lock.get("visual_invariants"):
            identity_text = "；".join(str(item) for item in lock["visual_invariants"])
        forbidden = generation_contract.get("forbidden_behavior")
        if isinstance(forbidden, list) and forbidden:
            forbidden_text = "；".join(str(item) for item in forbidden)
    for path in pending:
        kind = "character reference sheet" if "char_" in path.name else "scene action anchor"
        prompt = f"主生成指令：{idea[:260]}。素材类型：{kind}。角色身份锁：{identity_text}。禁止行为：{forbidden_text}。中国审美写实短剧摄影，竖屏9:16；只生成当前资产，不补写剧情，不做宣传风/MV风。"
        payload = {"model": "gpt-image-2", "prompt": prompt, "size": "1024x1536", "quality": "medium", "n": 1}
        asset_shot = {
            "episode_id": project_dir.name,
            "shot_id": f"ASSET_{path.stem}",
            "prompt": prompt,
            "action": kind,
            "camera": {"framing": "asset_reference_sheet", "movement": "NONE"},
            "visible_entities": [path.stem],
            "audio_contract": {"status": "NOT_APPLICABLE"},
            "reference_assets": [],
            "duration": None,
            "medium_lock": compiled_plan.get("medium_lock"),
        }
        canonical_request = build_canonical_generation_request(
            asset_shot, payload, provider="shenwen-image", endpoint=f"{base}/images/generations",
            payload_schema="openai.images.generations.v1", model="gpt-image-2", scope="research", request_kind="asset",
        )
        admission_path = project_dir / "admission_receipts" / f"{path.stem}.json"
        admission = admit_provider_request(canonical_request, contract_status="CONTRACT_VALID", receipt_path=admission_path)
        if admission["status"] != "ADMITTED":
            return False, "provider admission blocked for asset: " + ";".join(admission["preflight"]["errors"])
        request = urllib.request.Request(f"{base}/images/generations", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
        try:
            assert_admission(admission, admission["request_hash"], provider_payload=payload)
            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.load(response)
        except Exception as exc:
            return False, f"image provider failed: {type(exc).__name__}: {exc}"
        try:
            _materialize_image_response(result, path)
        except (OSError, RuntimeError, ValueError) as exc:
            return False, f"image provider returned unusable image for {path.name}: {type(exc).__name__}: {exc}"
    # Refresh character dossier hashes after replacement.
    for path in sorted((project_dir / "assets").glob("*_dossier.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        anchor = project_dir / "assets" / (path.stem.replace("_dossier", "_reference") + ".webp")
        reference = _image_reference(anchor)
        doc["visual_assets"] = [{"anchor_id": f"{doc['character_id']}_reference", "reference": reference, "sha256": reference["sha256"]}]
        _write_json(path, doc)
    return True, "completed"


def _measure_plan_tts(plan: dict[str, Any], project_dir: Path, manifest_path: Path | None, *, synthesize: bool) -> tuple[dict[str, dict[str, Any]], Path]:
    """Measure every line before provider admission and persist its receipt."""
    dialogue = [(str(shot["shot_id"]), str(shot.get("dialogue_text") or "")) for shot in plan.get("shots", [])]
    # The compiled plan keeps dialogue in the linked six-module contract.
    contract_path = project_dir / str(plan.get("six_module_contract", "six_module_contract.json"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    dialogue = [
        (str(shot["shot_id"]), str(shot.get("script", {}).get("dialogue_text", "")))
        for shot in contract.get("shots", []) if isinstance(shot, dict)
    ]
    if not dialogue or any(not text for _, text in dialogue):
        raise RuntimeError("every shot must have locked dialogue before TTS measurement")
    receipt = project_dir / "tts_measurements.json"
    measured, document = measure_dialogue(
        dialogue,
        audio_dir=project_dir / "audio",
        manifest_path=manifest_path,
        synthesize=synthesize,
    )
    _write_json(receipt, document)
    return measured, receipt


def _run(cmd: list[str], cwd: Path, output: Path | None = None) -> int:
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if output:
        _write_json(output, {"returncode": result.returncode, "stdout": result.stdout[-8000:], "stderr": result.stderr[-8000:], "command": cmd})
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--idea", required=True, help="one-sentence or short-paragraph story idea")
    parser.add_argument("--project-id", help="stable id used for resume; defaults to a slug of the idea")
    parser.add_argument("--output-root", type=Path, default=ROOT / "episodes" / "generated")
    parser.add_argument("--generate-assets", action="store_true", help="explicitly request provider asset generation (also implied by default auto mode)")
    parser.add_argument("--run", action="store_true", help="legacy alias; default auto mode already submits leaf shots")
    parser.add_argument("--plan-only", action="store_true", help="compile and preflight without provider calls")
    parser.add_argument("--resume", action="store_true", help="reuse an existing project directory")
    parser.add_argument("--tts-manifest", type=Path, help="existing measured TTS manifest; rows may be keyed by shot_id or cue")
    parser.add_argument("--no-local-tts", action="store_true", help="do not synthesize local research WAVs when no measured manifest is supplied")
    parser.add_argument("--target-seconds", type=int, choices=range(24, 73), metavar="N",
                        help="target assembled duration; six shots are sized evenly (24..72 seconds)")
    parser.add_argument("--creator-brief", type=Path,
                        help="optional JSON creator brief; audience/hook/ending_hook/style are required when supplied")
    args = parser.parse_args()
    project_id = args.project_id or f"idea_{_slug(args.idea)}"
    project_dir = (args.output_root / project_id).resolve()
    if project_dir.exists() and not args.resume:
        raise SystemExit(f"project exists; pass --resume to continue: {project_dir}")
    project_dir.mkdir(parents=True, exist_ok=True)
    creator_brief: dict[str, Any] | None = None
    if args.creator_brief:
        try:
            creator_brief = load_creator_brief(args.creator_brief)
            brief_check = validate_creator_brief(creator_brief, require_ready=True)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if brief_check["status"] != "PASS":
            raise SystemExit("creator brief is incomplete: " + "; ".join(brief_check["errors"]))
    collaboration = _default_collaboration_context()
    project_research_dir = project_dir / "research"
    project_research_dir.mkdir(parents=True, exist_ok=True)
    collaboration_snapshot = {
        "schema": "ace.video_kingdom.collaboration_context.v1",
        "project_id": project_id,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "READY",
        "evidence": {
            "planner_role": {"path": "roles/planner.md", "sha256": _sha256(ROLE_DIR / "planner.md")},
            "executor_role": {"path": "roles/executor.md", "sha256": _sha256(ROLE_DIR / "executor.md")},
            "shared_hub": {"path": "research/shared_information_hub.v1.json", "sha256": _sha256(RESEARCH_DIR / "shared_information_hub.v1.json")},
        },
        "handoff": collaboration["handoff"],
    }
    collaboration_snapshot_path = project_research_dir / "collaboration_context.v1.json"
    _write_json(collaboration_snapshot_path, collaboration_snapshot)
    collaboration["snapshot"] = str(collaboration_snapshot_path)
    receipt_path = project_dir / "pipeline_receipt.json"
    receipt = {"schema": "video_kingdom.idea_pipeline_receipt.v1", "project_id": project_id, "idea": args.idea, "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stages": []}
    receipt["collaboration"] = collaboration
    plan_path = project_dir / "episode_plan.json"
    if plan_path.exists() and args.resume:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if not isinstance(plan.get("dynamic_content_plan"), dict):
            plan["dynamic_content_plan"] = build_episode_dynamic_plan(idea=args.idea, plan=plan, target_seconds=args.target_seconds)
            plan.setdefault("content_control", initial_content_control())
            _write_json(project_dir / "episode_dynamic_plan.json", plan["dynamic_content_plan"])
            _write_json(project_dir / "content_control.v1.json", plan["content_control"])
            _write_json(plan_path, plan)
    else:
        plan = _compile(args.idea, project_dir, project_id, args.target_seconds, creator_brief=creator_brief)
    receipt["stages"].append({"name": "script_and_storyboard", "status": "COMPLETED", "artifacts": [str(plan_path), str(project_dir / "six_module_contract.json")]})
    brief = plan.get("creator_brief") if isinstance(plan.get("creator_brief"), dict) else build_creator_brief(title=plan.get("title", ""), target_seconds=args.target_seconds)
    brief_path = project_dir / "creator_brief.v1.json"
    _write_json(brief_path, brief)
    recap_path = project_dir / "publish_recap.v1.json"
    if not recap_path.exists():
        _write_json(recap_path, build_publish_recap(project_id=project_id, brief=brief))
    receipt["stages"].append({"name": "creator_layer", "status": "READY" if brief.get("status") == "READY" else "PENDING", "artifacts": [str(brief_path), str(recap_path)], "authority": "planning_and_next_iteration_only"})

    planning_check = _planning_conformance_check(plan)
    planning_check["recorded_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    planning_check["evidence"] = {
        "plan": str(plan_path),
        "roles": ["roles/planner.md", "roles/executor.md"],
        "shared_research": "research/shared_information_hub.v1.json",
    }
    planning_check_path = project_research_dir / "planning_conformance.v1.json"
    _write_json(planning_check_path, planning_check)
    receipt["stages"].append({"name": "planning_conformance", "status": planning_check["status"], "artifact": str(planning_check_path)})
    if planning_check["status"] != "PASS":
        receipt["status"] = "BLOCKED_BEFORE_PROVIDER"
        receipt["blocking_reason"] = "compiled plan does not satisfy the default planner contract"
        _write_json(receipt_path, receipt)
        print(json.dumps({"status": receipt["status"], "project": str(project_dir), "receipt": str(receipt_path), "planning_check": str(planning_check_path)}, ensure_ascii=False))
        return 1

    dynamic_path = project_dir / "episode_dynamic_plan.json"
    if not dynamic_path.is_file():
        _write_json(dynamic_path, plan["dynamic_content_plan"])
    receipt["content_control"] = plan.get("content_control", initial_content_control())
    receipt["stages"].append({
        "name": "content_feasibility_plan",
        "status": "COMPLETED",
        "artifacts": [str(dynamic_path)],
        "content_state": receipt["content_control"].get("content_state", "R0"),
        "tech_route": receipt["content_control"].get("tech_route", "NORMAL"),
        "ratio_policy": "diagnostic_only",
    })

    generation_check = generation_conformance_check(plan)
    generation_check["recorded_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    generation_check_path = project_research_dir / "generation_conformance.v1.json"
    _write_json(generation_check_path, generation_check)
    receipt["stages"].append({"name": "generation_conformance", "status": generation_check["status"], "artifact": str(generation_check_path), "errors": generation_check["errors"]})
    if generation_check["status"] != "PASS":
        receipt["status"] = "BLOCKED_BEFORE_PROVIDER"
        receipt["blocking_reason"] = "five-section generation contract is not embedded in every provider request"
        _write_json(receipt_path, receipt)
        print(json.dumps({"status": receipt["status"], "project": str(project_dir), "receipt": str(receipt_path), "generation_check": str(generation_check_path)}, ensure_ascii=False))
        return 1

    tts_status = "PENDING_PLAN_ONLY"
    tts_receipt = project_dir / "tts_measurements.json"
    tts_measurements: dict[str, dict[str, Any]] = {}
    if not args.plan_only:
        try:
            tts_measurements, tts_receipt = _measure_plan_tts(
                plan, project_dir, args.tts_manifest, synthesize=not args.no_local_tts,
            )
            tts_status = "COMPLETED"
            plan = _compile(args.idea, project_dir, project_id, args.target_seconds, tts_measurements, creator_brief=creator_brief or plan.get("creator_brief"))
            _write_json(plan_path, plan)
        except Exception as exc:
            tts_status = "BLOCKED"
            receipt["tts_provider_detail"] = f"{type(exc).__name__}: {exc}"
    receipt["stages"].append({"name": "tts_measurement", "status": tts_status, "artifact": str(tts_receipt)})
    if tts_status == "BLOCKED":
        receipt["status"] = "BLOCKED_BEFORE_PROVIDER"
        receipt["blocking_reason"] = "every shot requires measured TTS before duration can be locked"
        _write_json(receipt_path, receipt)
        print(json.dumps({"status": receipt["status"], "project": str(project_dir), "receipt": str(receipt_path), "next": "provide --tts-manifest or enable local TTS"}, ensure_ascii=False))
        return 1

    asset_status = "PLACEHOLDER_PENDING_PROVIDER"
    auto_execute = not args.plan_only
    if args.generate_assets or auto_execute:
        ok, detail = _generate_assets(project_dir, args.idea, force=args.generate_assets)
        asset_status = "COMPLETED" if ok else "BLOCKED"
        receipt["asset_provider_detail"] = detail
        if ok:
            # Provider replacement changes hashes, so rewrite the compiled
            # plan and keep the contract/manifest lineage self-consistent.
            plan = _compile(args.idea, project_dir, project_id, args.target_seconds, tts_measurements, creator_brief=creator_brief or plan.get("creator_brief"))
            _write_json(plan_path, plan)
    receipt["stages"].append({"name": "assets", "status": asset_status, "artifacts": [str(project_dir / "assets")]})

    preflight_path = project_dir / "preflight.json"
    preflight_command = [sys.executable, "tools/preflight_episode.py", "--episode", str(plan_path), "--output", str(preflight_path), "--require-formal"]
    if not args.plan_only:
        preflight_command.append("--require-measured-tts")
    preflight_rc = _run(preflight_command, ROOT)
    receipt["stages"].append({"name": "deterministic_preflight", "status": "PASSED" if preflight_rc == 0 else "BLOCKED", "artifact": str(preflight_path)})
    if preflight_rc or asset_status != "COMPLETED":
        receipt["status"] = "BLOCKED_BEFORE_PROVIDER"
        receipt["blocking_reason"] = "real character/scene assets and measured TTS are required before provider submission; placeholder anchors are retained only for plan validation"
        _write_json(receipt_path, receipt)
        print(json.dumps({"status": receipt["status"], "project": str(project_dir), "preflight": str(preflight_path), "next": "rerun with real assets and measured TTS; no website interaction required"}, ensure_ascii=False))
        return 1

    if args.run or auto_execute:
        manifest = project_dir / "manifest.json"
        media_dir = project_dir / "media"
        output = project_dir / f"{project_id}.mp4"
        rc = _run([sys.executable, "tools/run_comedy_episode.py", "--episode", str(plan_path), "--identity-contract", str(plan_path), "--manifest", str(manifest), "--media-dir", str(media_dir), "--output", str(output), "--preflight-output", str(preflight_path), "--review-output", str(project_dir / "media_review.json"), "--pacing-audit-dir", str(project_dir / "pacing_audits")], ROOT)
        pacing_dir = project_dir / "pacing_audits"
        final_pacing = pacing_dir / "final.json"
        pacing_status = None
        actual_duration = None
        if final_pacing.is_file():
            try:
                pacing_report = json.loads(final_pacing.read_text(encoding="utf-8"))
                pacing_status = pacing_report.get("status")
                media = pacing_report.get("media") if isinstance(pacing_report, dict) else None
                if isinstance(media, dict) and isinstance(media.get("duration_seconds"), (int, float)):
                    actual_duration = float(media["duration_seconds"])
            except (OSError, json.JSONDecodeError):
                pacing_status = "INVALID_RECEIPT"
        continuity_dir = project_dir / "continuity_audits"
        continuity_status = None
        final_continuity = continuity_dir / "final.json"
        if final_continuity.is_file():
            try:
                continuity_status = json.loads(final_continuity.read_text(encoding="utf-8")).get("status")
            except (OSError, json.JSONDecodeError):
                continuity_status = "INVALID_RECEIPT"
        acceptance_path = project_dir / "acceptance_receipt.json"
        acceptance_status = None
        if acceptance_path.is_file():
            try:
                acceptance_status = json.loads(acceptance_path.read_text(encoding="utf-8")).get("status")
            except (OSError, json.JSONDecodeError):
                acceptance_status = "INVALID_RECEIPT"
        execution_check = execution_conformance_check(plan, project_dir)
        execution_check["recorded_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        execution_check["evidence"] = {"plan": str(plan_path), "manifest": str(manifest), "acceptance": str(acceptance_path)}
        execution_check_path = project_research_dir / "execution_conformance.v1.json"
        _write_json(execution_check_path, execution_check)
        receipt["stages"].append({"name": "execution_conformance", "status": execution_check["status"], "artifact": str(execution_check_path), "errors": execution_check["errors"]})
        # Post-production diagnostics are evidence only.  A render/provider
        # error is classified on the technical/provider lane and never bumps
        # the content state automatically.
        failure_class = None
        if rc != 0:
            provider_evidence = any("provider" in str(item).lower() or "quota" in str(item).lower() for item in execution_check.get("errors", []))
            if manifest.is_file():
                try:
                    manifest_rows = json.loads(manifest.read_text(encoding="utf-8"))
                    manifest_rows = manifest_rows if isinstance(manifest_rows, list) else [manifest_rows]
                    provider_evidence = provider_evidence or any(
                        "provider" in str(row.get("error_class", "")).lower()
                        or "http_create" in str(row.get("error_class", "")).lower()
                        or "quota" in str(row.get("error", "")).lower()
                        for row in manifest_rows if isinstance(row, dict)
                    )
                except (OSError, json.JSONDecodeError):
                    pass
            failure_class = classify_route_failure("PROVIDER" if provider_evidence else "TECHNICAL_FAILURE")
        diagnostics = build_post_diagnostics(
            plan.get("dynamic_content_plan", {}),
            actual_duration=actual_duration,
            failure_class=failure_class,
        )
        diagnostics_path = project_research_dir / "post_production_diagnostics.v1.json"
        _write_json(diagnostics_path, diagnostics)
        receipt["stages"].append({"name": "post_production_diagnostics", "status": diagnostics["classification"], "artifact": str(diagnostics_path), "content_state": plan.get("content_control", {}).get("content_state", "R0"), "tech_route": plan.get("content_control", {}).get("tech_route", "NORMAL")})
        stage_status = "COMPLETED" if rc == 0 and acceptance_status == "PASS" and execution_check["status"] == "PASS" else ("CONTINUITY_REVIEW_REQUIRED" if acceptance_status == "CONTINUITY_REVIEW_REQUIRED" else "FAILED")
        receipt["stages"].append({"name": "leaf_render_and_assembly", "status": stage_status, "output": str(output), "manifest": str(manifest), "pacing_audits": str(pacing_dir), "continuity_audits": str(continuity_dir), "acceptance_receipt": str(acceptance_path), "execution_conformance": str(execution_check_path), "final_pacing_status": pacing_status, "final_continuity_status": continuity_status})
        receipt["status"] = "COMPLETED" if stage_status == "COMPLETED" else stage_status
    else:
        receipt["status"] = "READY_FOR_PROVIDER"
    receipt["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _write_json(receipt_path, receipt)
    print(json.dumps({"status": receipt["status"], "project": str(project_dir), "receipt": str(receipt_path)}, ensure_ascii=False))
    return 0 if receipt["status"] in {"READY_FOR_PROVIDER", "COMPLETED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
