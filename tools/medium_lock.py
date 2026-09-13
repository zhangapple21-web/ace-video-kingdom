"""Permanent fail-closed gate: story material is not the finished video medium.

Any AI short drama must sign medium_lock before an image or video provider
call. Chat logs, WeChat screenshots, and workbench aigc_prompt are intake,
not output style. Verbal reminders are not a control.
"""
from __future__ import annotations

from typing import Any


SCHEMA = "video_kingdom.medium_lock.v1"
RULE = (
    "故事素材不等于成片介质。聊天记录、微信截图、工作台 aigc_prompt 只是摄入，不是画面风格。"
    "允许成片介质：CHARACTER_PERFORMANCE 角色表演动画 / LIVE_ACTION_DRAMA 实拍感短剧 / "
    "UI_ANIMATION UI界面动画。未签名不得调用图像或视频模型。"
)
OUTPUT_MEDIA = ("CHARACTER_PERFORMANCE", "LIVE_ACTION_DRAMA", "UI_ANIMATION")
SOURCE_KINDS = (
    "ORIGINAL_STORY",
    "CHAT_LOG",
    "SCREENSHOT",
    "WORKBENCH_EXPORT",
    "SCRIPT",
    "OTHER",
)
UI_MEDIUM_TOKENS = (
    "聊天界面",
    "手机聊天",
    "聊天气泡",
    "微信界面",
    "微信对话框",
    "微信气泡",
    "消息气泡",
    "对话框界面",
    "气泡",
    "微信",
    "chat bubble",
    "chat interface",
    "chat ui",
    "wechat ui",
    "imessage",
)
INTAKE_PLACEHOLDER = "【待按 medium_lock 重编译：工作台提示词是故事素材，不是成片介质】"


def character_performance_lock(
    *,
    source_kind: str = "ORIGINAL_STORY",
    signed_by: str = "compiler",
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "signed": True,
        "source_kind": source_kind,
        "output_medium": "CHARACTER_PERFORMANCE",
        "signed_by": signed_by,
        "rule": RULE,
    }


def unsigned_medium_lock(*, source_kind: str = "WORKBENCH_EXPORT") -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "signed": False,
        "source_kind": source_kind,
        "output_medium": "UNSIGNED",
        "rule": RULE,
    }


def contains_ui_medium_language(text: Any) -> bool:
    blob = str(text or "").casefold()
    if not blob.strip():
        return False
    return any(token.casefold() in blob for token in UI_MEDIUM_TOKENS)


def wash_production_prompt(prompt: str) -> tuple[str, str, bool]:
    """Keep the source prompt as intake; strip UI-medium language from production."""
    original = str(prompt or "")
    if contains_ui_medium_language(original):
        return INTAKE_PLACEHOLDER, original, True
    return original, original, False


def _shot_production_blobs(shot: dict[str, Any]) -> list[str]:
    blobs = [str(shot.get("prompt") or "")]
    structured = shot.get("shot_prompt")
    if isinstance(structured, dict):
        for value in structured.values():
            if isinstance(value, str):
                blobs.append(value)
            elif isinstance(value, dict):
                blobs.extend(str(item) for item in value.values() if isinstance(item, str))
    return blobs


def validate_medium_lock(plan: dict[str, Any]) -> list[str]:
    """Return hard-failure messages. Empty means the lock may proceed to other gates."""
    lock = plan.get("medium_lock")
    if not isinstance(lock, dict):
        return ["medium_lock missing; story material is not the finished video medium"]
    errors: list[str] = []
    if lock.get("schema") != SCHEMA:
        errors.append("medium_lock.schema must be video_kingdom.medium_lock.v1")
    if lock.get("signed") is not True:
        errors.append("medium_lock unsigned; refuse image/video provider submission")
    source_kind = lock.get("source_kind")
    if source_kind not in SOURCE_KINDS:
        errors.append("medium_lock.source_kind invalid")
    output_medium = lock.get("output_medium")
    if output_medium not in OUTPUT_MEDIA:
        errors.append(
            "medium_lock.output_medium must be CHARACTER_PERFORMANCE, LIVE_ACTION_DRAMA, or UI_ANIMATION"
        )
    if output_medium != "UI_ANIMATION":
        shots = plan.get("shots") if isinstance(plan.get("shots"), list) else []
        for index, shot in enumerate(shots, start=1):
            if not isinstance(shot, dict):
                continue
            shot_id = str(shot.get("shot_id") or index)
            blob = "\n".join(_shot_production_blobs(shot))
            if contains_ui_medium_language(blob):
                errors.append(
                    f"{shot_id}: UI-medium language (微信/气泡/聊天界面) is forbidden unless "
                    "medium_lock.output_medium=UI_ANIMATION"
                )
    return errors
