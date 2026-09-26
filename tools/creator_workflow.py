"""Creator-layer inputs that complement the Video Kingdom control plane.

The creator brief is an optional planning input.  The publish recap is a
non-authoritative feedback record: it may improve the next story/shot plan,
but it can never approve delivery or change provider routing by itself.

The creative-development profile below absorbs the useful part of an
industrial animation workflow (cast inventory, relationships, character
signatures, arcs, visual world rules, episode hook and review checklist).
It is a planning/read-model layer only.  It does not replace the script,
Identity/State/Scene State/Shot State contracts, double review, production
gate or provider routing.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


BRIEF_REQUIRED = ("audience", "hook", "ending_hook", "style")
CREATIVE_MODES = {
    "live_action",
    "chat_ui",
    "cartoon",
    "product_demo",
    "motion_graphics",
    "audit_only",
}
DEVELOPMENT_STATUSES = {"PENDING", "DRAFT", "READY", "LOCKED", "ARCHIVED"}
INPUT_KINDS = {
    "ORIGINAL_STORY",
    "NOVEL",
    "SCRIPT",
    "MANGA_ADAPTATION",
    "WORLD_SETTING",
    "CHARACTER_SETTING",
    "EPISODE_OUTLINE",
    "SHOT_REQUEST",
    "UNKNOWN",
}
SIGNATURE_FIELDS = (
    "signature_action",
    "signature_expression",
    "signature_shot",
    "signature_palette",
    "signature_dialogue_style",
    "signature_costume_element",
    "signature_prop",
    "signature_emotion",
    "signature_entrance",
    "signature_contrast",
)
HOOK_CHECKS = (
    "opening_hook",
    "early_conflict",
    "information_change",
    "emotion_escalation",
    "ending_question",
    "character_memorability",
    "generation_feasibility",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def resolve_renderer_capability(creative_mode: str) -> dict[str, Any]:
    """Report whether a creative mode has a declared execution path.

    This is planning evidence only: it never authorizes a provider submission.
    The mode registry is the source of truth so that a brief cannot silently
    present a research-only compositor as an implemented renderer.
    """
    mode = _text(creative_mode) or "live_action"
    registry_path = Path(__file__).resolve().parents[1] / "research" / "creative_modes.v1.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        registry = None

    modes = registry.get("modes") if isinstance(registry, dict) else None
    row = modes.get(mode) if isinstance(modes, dict) else None
    if not isinstance(row, dict):
        readiness = "UNKNOWN_MODE_OR_REGISTRY"
        renderer = None
        renderer_status = "UNKNOWN"
        reason = "创作模式或模式注册表不可验证；不得据此提交媒体任务。"
    else:
        renderer = _text(row.get("renderer")) or None
        renderer_status = _text(row.get("renderer_status")) or "UNSPECIFIED"
        if mode == "audit_only" or renderer == "none":
            readiness = "NON_RENDERING_MODE"
            reason = "此模式只用于审计，不生成媒体。"
        elif renderer_status == "REFERENCE_BOUNDARY_ONLY":
            readiness = "ADAPTER_NOT_IMPLEMENTED"
            reason = "此模式目前只有参考边界，没有已验证的生产合成器适配器。"
        elif mode == "live_action" and renderer == "agnes-video-2.5-flash":
            readiness = "ROUTE_DECLARED_NOT_SUBMITTED"
            reason = "真人视频路由已登记；本简报不代表审查、准入或 Provider 提交已完成。"
        elif renderer == "provider_or_specialized_compositor":
            readiness = "RENDERER_UNVERIFIED"
            reason = "该模式允许多种执行路径，但当前没有可验证的唯一渲染器。"
        else:
            readiness = "RENDERER_STATUS_UNSPECIFIED"
            reason = "注册表未声明可验证的生产就绪状态。"

    return {
        "schema": "video_kingdom.renderer_capability.v1",
        "creative_mode": mode,
        "renderer": renderer,
        "renderer_status": renderer_status,
        "production_readiness": readiness,
        "creative_planning_allowed": True,
        "provider_submission_authorized": False,
        "source": "research/creative_modes.v1.json",
        "reason": reason,
    }


def classify_creator_input(text: str) -> str:
    """Classify a supplied idea without inventing story facts."""
    value = _text(text)
    if not value:
        return "UNKNOWN"
    rules = (
        ("MANGA_ADAPTATION", ("漫画", "动漫", "改编")),
        ("NOVEL", ("小说", "网文", "原著")),
        ("SCRIPT", ("剧本", "台词", "场次")),
        ("EPISODE_OUTLINE", ("分集", "第1集", "第1话", "大纲")),
        ("WORLD_SETTING", ("世界观", "设定", "阵营", "魔法体系")),
        ("CHARACTER_SETTING", ("人物设定", "角色设定", "人设")),
        ("SHOT_REQUEST", ("分镜", "镜头", "拍摄")),
    )
    for kind, markers in rules:
        if any(marker in value for marker in markers):
            return kind
    return "ORIGINAL_STORY"


def build_creative_development_profile(
    *,
    title: str = "",
    source_text: str = "",
    status: str = "PENDING",
    input_kind: str | None = None,
    requested_outputs: list[str] | None = None,
) -> dict[str, Any]:
    """Build a reusable, provider-independent creator development profile.

    The ten signature slots are prompts for deliberate character design, not
    mandatory assets for every genre.  Empty values remain explicit instead
    of being filled by inference.
    """
    safe_status = status if status in DEVELOPMENT_STATUSES else "PENDING"
    source_value = _text(source_text)
    kind = input_kind if input_kind in INPUT_KINDS else classify_creator_input(source_value)
    return {
        "schema": "ace.video_kingdom.creative_development_profile.v1",
        "status": safe_status,
        "production_integration": False,
        "title": _text(title) or "未命名短剧",
        "input_classification": {
            "kind": kind,
            "source_text_hash": hashlib.sha256(source_value.encode("utf-8")).hexdigest() if source_value else "",
            "facts_only": True,
            "unknown_policy": "未被原文或用户采用决定支持的内容保持 UNKNOWN；候选必须标记 inferred。",
        },
        "requested_outputs": requested_outputs or [
            "character_model",
            "relationship_map",
            "episode_script",
            "shot_plan",
            "visual_assets",
            "audio_plan",
            "quality_review",
        ],
        "character_roster": [],
        "relationship_graph": {"nodes": [], "edges": [], "unknown_edges": []},
        "character_signature_system": {
            "fields": list(SIGNATURE_FIELDS),
            "records": [],
            "policy": "让观众通过轮廓、色彩、动作和语言认出角色；不把十项清单升为每镜硬门。",
        },
        "character_arcs": [],
        "visual_world": {
            "era": "UNKNOWN",
            "geography": "UNKNOWN",
            "architecture": "UNKNOWN",
            "technology_or_magic": "UNKNOWN",
            "palette_rules": [],
            "lighting_rules": [],
            "style_baseline": "继承本项目 creative_mode；不得用风景画替代真实场景表演。",
        },
        "series_plan": {
            "mode": "OPTIONAL",
            "planned_episodes": None,
            "arc_milestones": {"40": None, "60": None, "80": None},
            "anti_filler_policy": "若未启用长线规划，不强制扩写集数；启用后每集必须推动剧情、关系、秘密、冲突、世界观或情绪至少一项。",
        },
        "episode_structure": {
            "opening_hook": "",
            "conflict": "",
            "escalation": "",
            "information_change": "",
            "reversal_or_payoff": "",
            "ending_question": "",
            "target_seconds": None,
        },
        "quality_review": {
            "checks": list(HOOK_CHECKS),
            "status": "PENDING",
            "authority": "CREATIVE_REVIEW_ONLY",
            "source_quality_criteria": {},
            "project_selection_criteria": {},
            "reviewer": "UNKNOWN",
            "evidence_refs": [],
        },
        "production_mapping": {
            "character_identity": "assets/templates/character_asset_package.v1.json",
            "state_layers": ["Identity", "State", "Scene State", "Shot State"],
            "script_review": "script_prompt_review.script_review",
            "shot_review": "script_prompt_review.prompt_review",
            "provider_gate": "production_shot_gate",
            "prompt_language": "zh-CN; English optional, never required",
        },
        "source_policy": {
            "creative_authority": "HUMAN_ADOPTED_DECISIONS",
            "ai_role": ["classify", "structure", "extract", "audit", "propose_labeled_candidates"],
            "forbidden": ["silent_invention", "silent_overwrite", "self_approve", "change_provider_route"],
        },
    }


def validate_creative_development_profile(
    profile: dict[str, Any], *, require_ready: bool = False
) -> dict[str, Any]:
    """Validate the creator layer without turning it into a production bypass."""
    errors: list[str] = []
    if not isinstance(profile, dict):
        errors.append("creative development profile must be an object")
        profile = {}
    if profile.get("schema") != "ace.video_kingdom.creative_development_profile.v1":
        errors.append("creative development profile schema is invalid")
    status = profile.get("status", "PENDING")
    if status not in DEVELOPMENT_STATUSES:
        errors.append("creative development profile status is invalid")
    if profile.get("production_integration") is not False:
        errors.append("creative development profile cannot authorize production integration")
    classification = profile.get("input_classification")
    if not isinstance(classification, dict) or classification.get("kind") not in INPUT_KINDS:
        errors.append("input_classification.kind is invalid")
    signatures = profile.get("character_signature_system")
    if not isinstance(signatures, dict) or not isinstance(signatures.get("fields"), list):
        errors.append("character_signature_system.fields is required")
    roster = profile.get("character_roster")
    if roster is not None and not isinstance(roster, list):
        errors.append("character_roster must be a list")
    graph = profile.get("relationship_graph")
    if not isinstance(graph, dict) or not all(isinstance(graph.get(key), list) for key in ("nodes", "edges", "unknown_edges")):
        errors.append("relationship_graph must declare nodes, edges and unknown_edges lists")
    structure = profile.get("episode_structure")
    if not isinstance(structure, dict):
        errors.append("episode_structure must be an object")
    structural_error_count = len(errors)
    if status in {"READY", "LOCKED"} or require_ready:
        structure_map = structure if isinstance(structure, dict) else {}
        if not roster:
            errors.append("ready creative development profile needs at least one character")
        else:
            for index, character in enumerate(roster, start=1):
                if not isinstance(character, dict) or not _text(character.get("character_id")) or not _text(character.get("name")):
                    errors.append(f"character_roster[{index}] needs character_id and name")
        required_structure = ("opening_hook", "conflict", "information_change", "ending_question")
        for field in required_structure:
            if not _text(structure_map.get(field)):
                errors.append(f"episode_structure missing {field}")
        quality_review = profile.get("quality_review")
        if not isinstance(quality_review, dict) or not isinstance(quality_review.get("checks"), list):
            errors.append("quality_review.checks must be a list")
    structural_errors = errors[:structural_error_count]
    readiness_errors = errors[structural_error_count:]
    failed = bool(structural_errors) or bool(readiness_errors and (require_ready or status in {"READY", "LOCKED"}))
    return {
        "schema": "ace.video_kingdom.creative_development_conformance.v1",
        "status": "FAIL" if failed else ("PASS" if not readiness_errors else "PENDING"),
        "verdict": "BLOCKED" if failed else ("PASS" if not readiness_errors else "REVIEW_REQUIRED"),
        "profile_status": status,
        "errors": errors,
        "structural_errors": structural_errors,
        "readiness_errors": readiness_errors,
        "non_authority": "CREATIVE_PLANNING_ONLY",
    }


def build_creator_brief(
    *,
    title: str,
    audience: str = "",
    hook: str = "",
    ending_hook: str = "",
    style: str = "",
    creative_mode: str = "live_action",
    platform: str = "",
    episode_number: int | None = None,
    episode_count: int | None = None,
    target_seconds: int | None = None,
    publish_goal: str = "",
    source: str = "USER_INPUT",
    creative_development: dict[str, Any] | None = None,
    source_text: str = "",
) -> dict[str, Any]:
    """Build a versioned, provider-independent creative brief."""
    required_values = {"audience": audience, "hook": hook, "ending_hook": ending_hook, "style": style}
    brief = {
        "schema": "ace.video_kingdom.creator_brief.v1",
        "status": "READY" if all(_text(required_values[field]) for field in BRIEF_REQUIRED) else "PENDING",
        "source": _text(source) or "USER_INPUT",
        "title": _text(title) or "未命名短剧",
        "platform": _text(platform) or "UNSPECIFIED",
        "audience": _text(audience),
        "episode_number": episode_number,
        "episode_count": episode_count,
        "target_seconds": target_seconds,
        "hook": _text(hook),
        "ending_hook": _text(ending_hook),
        "style": _text(style),
        "creative_mode": creative_mode if creative_mode in CREATIVE_MODES else "live_action",
        "renderer_capability": resolve_renderer_capability(
            creative_mode if creative_mode in CREATIVE_MODES else "live_action"
        ),
        "publish_goal": _text(publish_goal),
        "creative_development": creative_development or build_creative_development_profile(
            title=title,
            source_text=source_text or title,
        ),
    }
    return brief


def validate_creator_brief(brief: dict[str, Any], *, require_ready: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(brief, dict):
        errors.append("creator brief must be an object")
        brief = {}
    if brief.get("schema") != "ace.video_kingdom.creator_brief.v1":
        errors.append("creator brief schema is invalid")
    for field in BRIEF_REQUIRED:
        if not _text(brief.get(field)):
            errors.append(f"creator brief missing {field}")
    if brief.get("creative_mode", "live_action") not in CREATIVE_MODES:
        errors.append("creative_mode must be one of the registered modes")
    if brief.get("episode_number") is not None and (not isinstance(brief.get("episode_number"), int) or brief["episode_number"] < 1):
        errors.append("episode_number must be a positive integer")
    if brief.get("episode_count") is not None and (not isinstance(brief.get("episode_count"), int) or brief["episode_count"] < 1):
        errors.append("episode_count must be a positive integer")
    if brief.get("target_seconds") is not None and (not isinstance(brief.get("target_seconds"), int) or brief["target_seconds"] < 1):
        errors.append("target_seconds must be a positive integer")
    development = brief.get("creative_development")
    if development is not None:
        development_check = validate_creative_development_profile(development)
        if development_check["status"] == "FAIL":
            errors.extend(f"creative_development: {item}" for item in development_check["errors"])
    renderer_capability = resolve_renderer_capability(str(brief.get("creative_mode", "live_action")))
    if require_ready and errors:
        return {
            "schema": "ace.video_kingdom.creator_brief_conformance.v1",
            "status": "FAIL",
            "verdict": "BLOCKED",
            "errors": errors,
            "renderer_capability": renderer_capability,
        }
    return {
        "schema": "ace.video_kingdom.creator_brief_conformance.v1",
        "status": "PASS" if not errors else "PENDING",
        "verdict": "PASS" if not errors else "REVIEW_REQUIRED",
        "errors": errors,
        "required_fields": list(BRIEF_REQUIRED),
        "renderer_capability": renderer_capability,
        "creative_development": validate_creative_development_profile(brief.get("creative_development") or build_creative_development_profile()),
    }


def build_publish_recap(*, project_id: str, brief: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a feedback record without granting production authority."""
    return {
        "schema": "ace.video_kingdom.publish_recap.v1",
        "project_id": project_id,
        "status": "PENDING",
        "authority": "NEXT_ITERATION_INPUT_ONLY",
        "delivery_approval": "NOT_AUTHORIZED",
        "brief_snapshot": {
            "title": _text((brief or {}).get("title")),
            "platform": _text((brief or {}).get("platform")),
            "audience": _text((brief or {}).get("audience")),
            "creative_mode": _text((brief or {}).get("creative_mode")) or "live_action",
        },
        "metrics": {
            "impressions": None,
            "views": None,
            "completion_rate": None,
            "average_watch_seconds": None,
            "first_drop_off_seconds": None,
        },
        "qualitative": {
            "hook_verified": None,
            "ending_hook_verified": None,
            "confusing_beats": [],
            "audience_comments": [],
        },
        "next_iteration": {
            "keep": [],
            "change": [],
            "test": [],
        },
    }


def load_creator_brief(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"creator brief is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("creator brief must be a JSON object")
    return value
