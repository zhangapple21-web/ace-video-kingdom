"""Run the OneAPI writing/directing/audit room without bypassing production gates.

Dry-run is the default. ``--execute`` calls the local OpenAI-compatible OneAPI
gateway and writes a role receipt; it never submits image or video jobs.
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "research" / "oneapi_role_room.v1.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from production_control.model_transport import post_chat_completion

try:
    from tools.memory_context import build_memory_context, render_memory_context
    from tools.role_evaluator import evaluate_role_output
    from tools.role_feedback import build_feedback_proposals
except ImportError:  # pragma: no cover - script execution from tools/
    from memory_context import build_memory_context, render_memory_context  # type: ignore
    from role_evaluator import evaluate_role_output  # type: ignore
    from role_feedback import build_feedback_proposals  # type: ignore


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _prompt(role_id: str, source: str, context: str, memory_text: str = "") -> str:
    common = (
        "你是视频王国的候选角色，不是最终执行器。只能提出可审计的文字建议，"
        "不得调用图像/视频接口，不得切换模型，不得把接口完成当作创作验收。\n"
        "硬约束：真人电影感、多场景多镜头；全片禁止画中画、悬浮窗、通话界面、聊天UI、录屏感；"
        "对白和内心独白分离，独白必须给出完整原文。若输入剧本断层，必须先标出断点，"
        "区分原文事实/明确暗示/待补信息/不可擅自推断；不得把推断写成既定事实。\n"
    )
    tasks = {
        "outline_structurer": "把创意整理成结构化简报、角色表、场景表和硬约束清单。",
        "format_editor": "检查 JSON 字段完整性、对白/独白格式、字幕长度和交接可执行性。",
        "primary_writer": "写出故事主方案、角色目标、冲突和完整对白/独白草案。",
        "storyboarder": "把故事拆成可拍镜头，给出景别、机位、动作完成点、切镜理由和声音。",
        "contrarian_auditor": "从现实性、连续性、伦理、镜头可执行性和违规画面风险挑错。",
        "continuity_editor": "检查角色、道具、时间线、对白长度、字幕安全区和镜头前后衔接；发现断层时输出断点、风险等级、最小补桥候选和 NEEDS_CLARIFICATION 条件。",
        "director_convergence": "综合候选意见，收敛成一版可拍但仍需人工创作验收的镜头稿。",
        "ideation_branch": "提出多个开场钩子、结尾悬念或风格分支，标出各自的风险和适用场景。",
        "reality_reviewer": "从现实感、受众误读、文化语境和发布风险复核复杂项目。",
        "arbiter": "只针对已有分歧给出取舍依据、证据和保守方案，不重新创作整稿。",
    }
    return common + memory_text + f"角色：{role_id}\n任务：{tasks.get(role_id, role_id)}\n素材：\n{source}\n已有意见：\n{context}"


def _call(base_url: str, api_key: str, model: str, prompt: str, timeout: float) -> tuple[str, str]:
    # OneAPI/上游中文长输出可能持续很久；角色房间先产出可审计的短稿，
    # 详细扩写留给通过门禁后的专用步骤，避免串行角色把网关拖到超时。
    bounded_prompt = prompt + "\n输出上限：先给出可执行的短稿，最多 500 个汉字；不要重复题目，不要写过程说明。"
    data, _transport_meta = post_chat_completion(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=[{"role": "user", "content": bounded_prompt}],
        asset_store=ROOT / "assets" / "cache" / "transport",
        max_tokens=512,
        temperature=0.3,
        timeout=timeout,
    )
    return str(data["choices"][0]["message"]["content"]), str(data.get("model") or model)


def _normalize_base_url(value: str) -> str:
    """Accept either an OpenAI base URL or a full chat endpoint.

    The local launcher historically exported ``ONE_API_URL`` as
    ``.../v1/chat/completions`` while the role room expects a ``/v1`` base.
    Normalizing here prevents a silent ``.../chat/completions/chat/completions``
    request and makes new windows use the same gateway configuration.
    """
    normalized = value.strip().rstrip("/")
    suffix = "/chat/completions"
    if normalized.endswith(suffix):
        normalized = normalized[: -len(suffix)].rstrip("/")
    return normalized


def _invoke_call(base_url: str, api_key: str, model: str, prompt: str, timeout: float) -> tuple[str, str]:
    """Call the transport while keeping older local test shims compatible."""
    if len(inspect.signature(_call).parameters) >= 5:
        return _call(base_url, api_key, model, prompt, timeout)
    return _call(base_url, api_key, model, prompt)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--idea", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="调用本地 OneAPI；默认只做路由 dry-run")
    parser.add_argument("--profile", choices=("standard", "rapid", "full_audit"), default="standard", help="角色配置：日常、快速整理或全审计")
    parser.add_argument("--project-id", default=os.environ.get("VIDEO_KINGDOM_PROJECT_ID", ""), help="可选；匹配后才加载该项目的 L1/L2 记忆")
    parser.add_argument("--resume-from", type=Path, help="可选；从上一份角色收据续跑，只重试未完成角色")
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("ONEAPI_ROLE_TIMEOUT_SECONDS", "45")),
        help="单模型请求超时秒数（默认 45，可用 ONEAPI_ROLE_TIMEOUT_SECONDS 覆盖）",
    )
    parser.add_argument(
        "--base-url",
        default=(
            os.environ.get("ONEAPI_BASE_URL")
            or os.environ.get("ONE_API_URL")
            or "http://127.0.0.1:3000/v1"
        ),
    )
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout 必须大于 0")
    args.base_url = _normalize_base_url(args.base_url)
    matrix = _load_json(MATRIX)
    roles = {item["role_id"]: item for item in matrix["roles"]}
    source = args.idea.strip()
    role_order = matrix["profiles"][args.profile]
    trace_id = uuid.uuid4().hex
    memory = build_memory_context(args.project_id.strip() or None)
    memory_text = render_memory_context(memory)
    resume_receipt: dict[str, Any] = {}
    resume_compatible = False
    if args.resume_from:
        try:
            resume_receipt = _load_json(args.resume_from)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            parser.error(f"--resume-from 无法读取：{exc}")
        if resume_receipt.get("schema") != matrix["schema"]:
            parser.error("--resume-from 的收据 schema 与当前角色房间不兼容")
        if str(resume_receipt.get("idea") or "") != source:
            parser.error("--resume-from 的 idea 与本次输入不一致")
        old_memory = resume_receipt.get("memory_context") if isinstance(resume_receipt.get("memory_context"), dict) else {}
        resume_compatible = old_memory.get("sha256") == memory["sha256"]
        if not resume_compatible:
            print("[role-room] memory context changed; completed roles will be re-evaluated", file=sys.stderr, flush=True)
    receipt: dict[str, Any] = {
        "schema": matrix["schema"],
        "status": "DRY_RUN" if not args.execute else "RUNNING",
        "profile": args.profile,
        "idea": source,
        "gateway": args.base_url,
        "trace_id": trace_id,
        "memory_context": {
            "sha256": memory["sha256"],
            "sources": memory["sources"],
            "project_id": args.project_id.strip() or None,
            "l1_l2_loaded": bool(memory["payload"]["scope"]["l1_l2_loaded"]),
        },
        "resumed_from": str(args.resume_from) if args.resume_from else None,
        "resume_compatible": resume_compatible if args.resume_from else None,
        "roles": [],
    }
    context = ""
    previous_roles = {
        str(item.get("role_id")): item
        for item in (resume_receipt.get("roles") if isinstance(resume_receipt.get("roles"), list) else [])
        if isinstance(item, dict) and item.get("role_id")
    }
    # The local launcher historically exposed both ONEAPI_* and ONE_API_* names.
    # Accept the configured admin token as the local gateway credential so a new
    # window does not silently fall back to an empty/incorrect key.
    api_key = (
        os.environ.get("ONEAPI_LOCAL_MASTER_KEY")
        or os.environ.get("ONEAPI_KEY")
        or os.environ.get("ONEAPI_API_KEY")
        or os.environ.get("ONEAPI_ADMIN_TOKEN")
        or os.environ.get("ONE_API_KEY")
        or os.environ.get("OPENAI_API_KEY", "")
    )
    for role_id in role_order:
        item = roles[role_id]
        previous = previous_roles.get(role_id)
        if resume_compatible and previous and previous.get("status") == "COMPLETED":
            receipt["roles"].append(previous)
            if previous.get("output"):
                context += f"\n[{role_id}]\n{previous['output']}\n"
            continue
        primary_model = item["model"]
        fallback_models = list(item.get("fallback_models", []))
        record: dict[str, Any] = {"role_id": role_id, "span_id": uuid.uuid4().hex, "model": primary_model, "requested_model": primary_model, "declared_models": [primary_model, *fallback_models], "status": "PLANNED", "attempts": []}
        if args.execute:
            if not api_key:
                record.update({"status": "FAILED", "error": "缺少 ONEAPI_LOCAL_MASTER_KEY/ONEAPI_API_KEY/OPENAI_API_KEY"})
            else:
                output = None
                last_error = None
                for attempt_model in [primary_model, *fallback_models]:
                    print(f"[role-room] {role_id}: trying {attempt_model}", file=sys.stderr, flush=True)
                    try:
                        text, actual_model = _invoke_call(args.base_url, api_key, attempt_model, _prompt(role_id, source, context, memory_text), args.timeout)
                        evaluation = evaluate_role_output(role_id, text)
                        attempt = {"model": attempt_model, "actual_model": actual_model, "status": evaluation["status"], "evaluation": evaluation}
                        record["attempts"].append(attempt)
                        if evaluation["status"] != "PASS":
                            last_error = evaluation["failure_class"] or "QUALITY_FAIL"
                            record["quality_failures"] = int(record.get("quality_failures", 0)) + 1
                            print(f"[role-room] {role_id}: {attempt_model} returned an invalid candidate; trying fallback", file=sys.stderr, flush=True)
                            continue
                        output = text
                        route_rewritten = actual_model != attempt_model
                        used_fallback = attempt_model != primary_model or route_rewritten
                        record.update({"status": "COMPLETED", "model": actual_model, "requested_model": primary_model, "route_rewritten": route_rewritten, "fallback_used": used_fallback, "degraded": used_fallback, "output": text, "evaluation": evaluation})
                        context += f"\n[{role_id}]\n{text}\n"
                        break
                    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
                        last_error = type(exc).__name__ + ": " + str(exc)
                        record["attempts"].append({"model": attempt_model, "status": "FAILED", "error": last_error})
                        print(f"[role-room] {role_id}: {attempt_model} failed; trying fallback", file=sys.stderr, flush=True)
                if output is None:
                    record.update({"status": "BLOCKED" if item.get("authority") in {"blocking_candidate", "arbitration_only"} else "FAILED", "error": last_error or "no usable model"})
        receipt["roles"].append(record)
    if args.execute:
        if all(r["status"] == "COMPLETED" for r in receipt["roles"]):
            receipt["status"] = "COMPLETED"
        elif any(r["status"] == "BLOCKED" for r in receipt["roles"]):
            receipt["status"] = "BLOCKED"
        else:
            receipt["status"] = "FAILED"
    receipt["feedback_proposals"] = build_feedback_proposals(receipt)
    receipt["production_submission"] = "NOT_PERFORMED"
    receipt["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "roles": [r["role_id"] for r in receipt["roles"]], "out": str(args.out)}, ensure_ascii=False))
    return 0 if receipt["status"] in {"DRY_RUN", "COMPLETED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
