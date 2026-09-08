"""Bounded, research-only multi-model script-room round over the existing OneAPI gateway.

This is intentionally a one-shot sequential conversation (writer -> critic -> director),
not a scheduler or a second routing runtime. It prints a JSON receipt and never writes
production state.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.provider_admission import admit_provider_request, assert_admission, build_canonical_generation_request


BASE_URL = os.getenv("ONEAPI_BASE_URL", "http://127.0.0.1:3000/v1").rstrip("/")
API_KEY = os.getenv("ONEAPI_LOCAL_MASTER_KEY") or os.getenv("ONEAPI_KEY")


def call(model: str, prompt: str, max_tokens: int = 1100, timeout: int = 90) -> tuple[str, int]:
    if not API_KEY:
        raise RuntimeError("ONEAPI_LOCAL_MASTER_KEY or ONEAPI_KEY is missing")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是原创短剧编剧室成员。不要调用工具，不要写文件，输出简洁、可拍、中文。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.75,
        "max_tokens": max_tokens,
        "stream": False,
    }
    canonical = build_canonical_generation_request(
        {"episode_id": "research", "shot_id": f"SCRIPT_{model}", "prompt": prompt,
         "action": "script_room_round", "camera": {"framing": "text", "movement": "NONE"},
         "visible_entities": [], "audio_contract": {"status": "NOT_APPLICABLE"}, "reference_assets": []},
        body, provider="oneapi", endpoint=f"{BASE_URL}/chat/completions",
        payload_schema="openai.chat.completions.v1", model=model, scope="research", request_kind="research",
    )
    receipt_path = Path(__file__).resolve().parents[1] / "research" / "admission_receipts" / f"script_battle_{model}.json"
    admission = admit_provider_request(canonical, receipt_path=receipt_path)
    if admission["status"] != "ADMITTED":
        raise RuntimeError("provider admission blocked: " + ";".join(admission["preflight"]["errors"]))
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    assert_admission(admission, admission["request_hash"], provider_payload=body)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload: dict[str, Any] = json.load(response)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    content = payload["choices"][0]["message"]["content"]
    return content, elapsed_ms


def main() -> int:
    premise = (
        "为《我被卖去东南亚居然觉醒了系统》写第一版：60-90秒、9:16竖屏、完全虚构；"
        "地点只写‘东南亚某国边境园区’，不指向真实公司。被骗者不被猎奇化。系统只是把"
        "‘谁占席位、谁获利、谁承担代价、什么规则可验证’标注出来的观察装置，不是黑客外挂；"
        "结尾要走记录证据、联系外界、依法脱身，不提供违法入侵或伤害教程。请给一句梗概、3个角色、"
        "6个镜头beat（动作完成点+切镜理由）、12句以内短对白、伦理风险提醒。"
    )
    errors: list[dict[str, str]] = []
    try:
        writer, writer_ms = call("gpt-5.4-mini", premise, 1100, timeout=75)
    except Exception as exc:
        writer, writer_ms = "", 0
        errors.append({"stage": "writer", "error": type(exc).__name__ + ": " + str(exc)})
    critic_prompt = (
        "你是独立的伦理与连续性审稿人。下面是主笔草案：\n\n"
        f"{writer}\n\n"
        "请逐条指出：哪些对白像宣传口号、哪些动作缺乏完成点、哪些地方会把人口贩运拍成爽文、"
        "哪些信息可能被误读为现实指控；然后给出不超过6条可执行的修订指令。保持原创，不调用工具。"
    )
    try:
        critic, critic_ms = call("grok-4.6", critic_prompt, 900, timeout=75)
    except Exception as exc:
        critic, critic_ms = "", 0
        errors.append({"stage": "critic", "error": type(exc).__name__ + ": " + str(exc)})
    director_prompt = (
        "你是总编剧兼导演，负责把主笔和审稿人的冲突收敛成可拍样片。\n\n"
        f"【主笔】\n{writer}\n\n【审稿】\n{critic}\n\n"
        "请输出最终的60-90秒版本：一句梗概；角色表；6-8个镜头（每个含时长、画面、动作完成点、"
        "对白、字幕安全区、切镜理由）；结尾保留‘席位/规则边界’的结构性回响，但不要硬贴金句。"
        "所有地点与机构保持虚构；不写可执行的违法技术细节。最后列出仍需人工观看确认的3个点。"
    )
    try:
        # Keep the final pass on a compact model so a slow upstream does not
        # strand the whole research round; Terra remains the preferred final
        # judgment lane when its upstream is responsive.
        director, director_ms = call("gpt-5.4", director_prompt, 1200, timeout=75)
    except Exception as exc:
        director, director_ms = "", 0
        errors.append({"stage": "director", "error": type(exc).__name__ + ": " + str(exc)})
    receipt = {
        "schema": "episode008.multimodel_script_battle.v1",
        "production": False,
        "gateway": BASE_URL,
        "roles": ["draft_writer", "contrarian", "convergence_editor"],
        "models": ["gpt-5.4-mini", "grok-4.6", "gpt-5.4"],
        "activation_decision_ref": "research/episode_008_role_activation_decision.v1.json",
        "errors": errors,
        "latency_ms": {"writer": writer_ms, "critic": critic_ms, "director": director_ms},
        "writer": writer,
        "critic": critic,
        "director": director,
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
