"""Run the OneAPI writing/directing/audit room without bypassing production gates.

Dry-run is the default. ``--execute`` calls the local OpenAI-compatible OneAPI
gateway and writes a role receipt; it never submits image or video jobs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "research" / "oneapi_role_room.v1.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _prompt(role_id: str, source: str, context: str) -> str:
    common = (
        "你是视频王国的候选角色，不是最终执行器。只能提出可审计的文字建议，"
        "不得调用图像/视频接口，不得切换模型，不得把接口完成当作创作验收。\n"
        "硬约束：真人电影感、多场景多镜头；全片禁止画中画、悬浮窗、通话界面、聊天UI、录屏感；"
        "对白和内心独白分离，独白必须给出完整原文。\n"
    )
    tasks = {
        "primary_writer": "写出故事主方案、角色目标、冲突和完整对白/独白草案。",
        "storyboarder": "把故事拆成可拍镜头，给出景别、机位、动作完成点、切镜理由和声音。",
        "contrarian_auditor": "从现实性、连续性、伦理、镜头可执行性和违规画面风险挑错。",
        "continuity_editor": "检查角色、道具、时间线、对白长度、字幕安全区和镜头前后衔接。",
        "director_convergence": "综合候选意见，收敛成一版可拍但仍需人工创作验收的镜头稿。",
    }
    return common + f"角色：{role_id}\n任务：{tasks.get(role_id, role_id)}\n素材：\n{source}\n已有意见：\n{context}"


def _call(base_url: str, api_key: str, model: str, prompt: str) -> str:
    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}, ensure_ascii=False).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as response:
        data = json.loads(response.read().decode("utf-8"))
    return str(data["choices"][0]["message"]["content"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--idea", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="调用本地 OneAPI；默认只做路由 dry-run")
    parser.add_argument("--base-url", default=os.environ.get("ONEAPI_BASE_URL", "http://127.0.0.1:3000/v1"))
    args = parser.parse_args(argv)
    matrix = _load_json(MATRIX)
    roles = {item["role_id"]: item for item in matrix["roles"]}
    source = args.idea.strip()
    receipt: dict[str, Any] = {"schema": matrix["schema"], "status": "DRY_RUN" if not args.execute else "RUNNING", "idea": source, "gateway": args.base_url, "roles": []}
    context = ""
    api_key = os.environ.get("ONEAPI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    for role_id in matrix["order"]:
        item = roles[role_id]
        record: dict[str, Any] = {"role_id": role_id, "model": item["model"], "status": "PLANNED"}
        if args.execute:
            if not api_key:
                record.update({"status": "FAILED", "error": "缺少 ONEAPI_API_KEY/OPENAI_API_KEY"})
            else:
                try:
                    output = _call(args.base_url, api_key, item["model"], _prompt(role_id, source, context))
                    record.update({"status": "COMPLETED", "output": output})
                    context += f"\n[{role_id}]\n{output}\n"
                except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
                    record.update({"status": "FAILED", "error": type(exc).__name__ + ": " + str(exc)})
        receipt["roles"].append(record)
    receipt["status"] = "COMPLETED" if args.execute and all(r["status"] == "COMPLETED" for r in receipt["roles"]) else receipt["status"]
    receipt["production_submission"] = "NOT_PERFORMED"
    receipt["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "roles": [r["role_id"] for r in receipt["roles"]], "out": str(args.out)}, ensure_ascii=False))
    return 0 if receipt["status"] in {"DRY_RUN", "COMPLETED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
