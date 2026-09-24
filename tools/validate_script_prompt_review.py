"""Validate this-round screenwriter + director dual review before generation.

Conversation order is enforced in AGENTS.md / video-kingdom skill. This module
is the machine gate: old COMPLETED receipts, other shots, other run_ids, or a
changed prompt hash cannot impersonate a current-round pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA = "video_kingdom.script_prompt_review.v1"
PASS_SCRIPT = "通过"
FAIL_SCRIPT = "不通过"
PASS_PROMPT = "合格，可以生成"
FAIL_PROMPT = "不合格需修改"
SCRIPT_FIELDS = (
    "dialogue_order",
    "phone_state",
    "monologue_handling",
    "unfilmable_risks",
)
PHONE_HIGH_RISK_PROMPT_TERMS = (
    "完整接听",
    "接听过程",
    "正在接听",
    "拨号",
    "震动",
    "亮屏",
)
ALWAYS_HIGH_RISK_PROMPT_TERMS = (
    "男声说",
    "女声说",
)
HIGH_RISK_PROMPT_TERMS = PHONE_HIGH_RISK_PROMPT_TERMS + ALWAYS_HIGH_RISK_PROMPT_TERMS
PHONE_SKIP_PREFIX = "本镜不涉及手机"


def prompt_hash(compiled_prompt: str) -> str:
    return hashlib.sha256(str(compiled_prompt).encode("utf-8")).hexdigest()


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _parse_time(value: Any, *, field: str, errors: list[str]) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        errors.append(f"{field} missing")
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} must be ISO-8601")
        return None


def validate_script_prompt_review(
    packet: Any,
    *,
    shot_id: str | None = None,
    run_id: str | None = None,
    expected_script_hash: str | None = None,
    compiled_prompt: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return {
            "status": "BLOCKED",
            "errors": ["script_prompt_review missing: 未完成本轮编剧审核与导演提示词审核，禁止生成"],
        }
    if packet.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")

    packet_shot = str(packet.get("shot_id") or "").strip()
    packet_run = str(packet.get("run_id") or "").strip()
    expected_shot = str(shot_id or "").strip()
    expected_run = str(run_id or "").strip()
    if not packet_shot:
        errors.append("shot_id missing")
    elif expected_shot and packet_shot != expected_shot:
        errors.append("shot_id mismatch: 旧镜收据不得冒充本镜已审")
    if not packet_run:
        errors.append("run_id missing: 旧状态不得冒充本轮已审")
    elif expected_run and packet_run != expected_run:
        errors.append("run_id mismatch: 旧轮次收据不得冒充本轮已审")

    script_hash = str(packet.get("script_hash") or "").strip().lower()
    stored_prompt_hash = str(packet.get("prompt_hash") or "").strip().lower()
    if len(script_hash) != 64 or any(ch not in "0123456789abcdef" for ch in script_hash):
        errors.append("script_hash must be sha256 hex of this-round script")
    expected_script_hash = str(expected_script_hash or "").strip().lower()
    if expected_script_hash and script_hash != expected_script_hash:
        errors.append("script_hash mismatch: review receipt does not bind the currently locked script")
    if compiled_prompt is None:
        if len(stored_prompt_hash) != 64 or any(ch not in "0123456789abcdef" for ch in stored_prompt_hash):
            errors.append("prompt_hash missing")
    else:
        expected_hash = prompt_hash(compiled_prompt)
        if stored_prompt_hash != expected_hash:
            errors.append("prompt_hash mismatch: 提示词已改，旧导演审核无效，必须重审")
        prompt_text = str(compiled_prompt)
        script_review_early = packet.get("script_review") if isinstance(packet.get("script_review"), dict) else {}
        phone_state = str(script_review_early.get("phone_state") or "").strip()
        terms = ALWAYS_HIGH_RISK_PROMPT_TERMS
        if not phone_state.startswith(PHONE_SKIP_PREFIX):
            terms = HIGH_RISK_PROMPT_TERMS
        for term in terms:
            if term in prompt_text:
                errors.append(f"high-risk prompt term: {term}；禁止写入提交提示词，必须先改再审")

    script_review = packet.get("script_review") if isinstance(packet.get("script_review"), dict) else {}
    if not script_review:
        errors.append("script_review missing: 必须先以编剧身份完成本轮剧本审核")
    if str(script_review.get("role") or "").strip() not in {"编剧", "screenwriter"}:
        errors.append("script_review.role must be 编剧")
    for key in SCRIPT_FIELDS:
        if _empty(script_review.get(key)):
            errors.append(f"script_review.{key} missing")
    script_verdict = str(script_review.get("verdict") or "").strip()
    if script_verdict not in {PASS_SCRIPT, FAIL_SCRIPT}:
        errors.append("script_review.verdict must be 通过 or 不通过")
    if script_verdict == FAIL_SCRIPT:
        if _empty(script_review.get("reason")):
            errors.append("script_review.reason required when 不通过")
        errors.append("剧本审核不通过，禁止写提示词，禁止生成")
    script_time = _parse_time(script_review.get("reviewed_at"), field="script_review.reviewed_at", errors=errors)

    prompt_review = packet.get("prompt_review") if isinstance(packet.get("prompt_review"), dict) else {}
    prompt_conclusion = str(prompt_review.get("conclusion") or "").strip() if prompt_review else ""
    if script_verdict != PASS_SCRIPT:
        if prompt_review:
            errors.append("剧本未通过时不得出具导演提示词审核")
    else:
        if not prompt_review:
            errors.append("prompt_review missing: 提示词写完后必须由导演审核，未审禁止生成")
        if str(prompt_review.get("role") or "").strip() not in {"导演", "director"}:
            errors.append("prompt_review.role must be 导演")
        if prompt_review.get("distorts_script") is not False:
            errors.append("prompt_review.distorts_script must be false")
        if prompt_review.get("hard_rules_complete") is not True:
            errors.append("prompt_review.hard_rules_complete must be true")
        if prompt_review.get("high_risk_extras") is not False:
            errors.append("prompt_review.high_risk_extras must be false")
        if prompt_conclusion == FAIL_PROMPT:
            if _empty(prompt_review.get("reason")):
                errors.append("prompt_review.reason required when 不合格需修改")
            errors.append("导演审核不合格，禁止生成，必须先改再审")
        elif prompt_conclusion != PASS_PROMPT:
            errors.append("导演未明确写出「合格，可以生成」，禁止生成")
        prompt_time = _parse_time(prompt_review.get("reviewed_at"), field="prompt_review.reviewed_at", errors=errors)
        if script_time and prompt_time and prompt_time < script_time:
            errors.append("提示词审核早于剧本审核：禁止跳步，必须重审")

    return {
        "status": "PASS" if not errors else "BLOCKED",
        "errors": errors,
        "shot_id": packet_shot,
        "run_id": packet_run,
        "script_verdict": script_verdict,
        "prompt_conclusion": prompt_conclusion,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--shot-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--prompt", default=None)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    packet = payload.get("script_prompt_review", payload)
    result = validate_script_prompt_review(
        packet,
        shot_id=args.shot_id or packet.get("shot_id"),
        run_id=args.run_id or packet.get("run_id"),
        compiled_prompt=args.prompt if args.prompt is not None else payload.get("compiled_prompt"),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
