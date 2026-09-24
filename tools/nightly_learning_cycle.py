"""视频王国夜间学习的唯一编排入口。

顺序固定为：公开资料采集 → ACE Evolution Kernel 桥接 → 任务墙收口。
它不创建媒体任务、不执行外部代码、不更改 Provider 或模型路由；真正的
研究与晋升仍由 ACE 既有 DailyLearningLoop/TaskPool/Guardian 负责。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.daily_external_learning import collect, persist
from tools.publish_ace_learning_packet import publish

def run(*, limit: int = 5) -> dict[str, object]:
    collected = collect()
    run_path = persist(collected)
    bridge = publish(run_path)
    drain = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "drain_task_wall.py"), "--execute", "--limit", str(int(limit))],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if drain.returncode != 0:
        raise RuntimeError(f"task_wall_drain_failed:{drain.returncode}:{drain.stderr[-500:]}")
    try:
        drain_summary = json.loads(drain.stdout.strip() or "{}")
    except json.JSONDecodeError:
        drain_summary = {"raw": drain.stdout[-1000:]}
    return {
        "schema": "video_kingdom.nightly_learning_cycle.v1",
        "run_id": collected.get("run_id"),
        "run_path": str(run_path),
        "bridge": bridge,
        "task_wall": drain_summary,
        "production_integration": False,
        "provider_calls": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)
    print(json.dumps(run(limit=args.limit), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
