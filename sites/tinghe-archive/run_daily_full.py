#!/usr/bin/env python3
"""Run opencode to write ep05 for all 5 works, then run full pipeline."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\视频创作\ace-video-kingdom\sites\tinghe-archive")
OPENCODE = Path(r"C:\Users\Administrator\.local\bin\opencode.exe")

def run(cmd: list[str], label: str) -> tuple[int, str]:
    print(f"=== {label} ===")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=600)
    out = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        print(f"[FAIL] {label} (exit {result.returncode})")
        print(out[-2000:])
    else:
        print(f"[OK] {label}")
        print(out[-500:])
    return result.returncode, out


def main() -> int:
    # 1. Generate context bundles
    for wid in ["fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin"]:
        code, _ = run([sys.executable, "build_context_bundle.py", wid], f"context:{wid}")
        if code != 0:
            return 1

    # 2. Run opencode to write ep05 for all 5 works
    prompt = (
        "为 5 部作品各写第 5 集 (ep05)，只在 work.json 的 episodes 里追加 blocks。"
        "每集：scene(含 place/time/light)、cast(在场/未出场)、若干 para/line、结尾唯一 hook。"
        "beat 必须是可视化的剧情推进。输出末行 JSON 摘要。"
    )
    opencode_cmd = [
        "py", "-3", "-c",
        "import subprocess, sys; "
        "subprocess.run([r'C:\\Users\\Administrator\\.local\\bin\\opencode.exe', 'run', '--auto', "
        "'--file', 'DAILY_DIRECTIVE.md', "
        "'--file', 'build_context_bundle.py', "
        "'--file', 'build_originals.py', "
        "'--file', 'run_audit.py', "
        "'--file', 'AUDIT_PROMPT.md', "
        "'--file', 'originals_source/fanguan/context_bundle.md', "
        "'--file', 'originals_source/liufang/context_bundle.md', "
        "'--file', 'originals_source/tingjijia/context_bundle.md', "
        "'--file', 'originals_source/tuiqun/context_bundle.md', "
        "'--file', 'originals_source/zhenqianjin/context_bundle.md', "
        "'为 5 部作品各写第 5 集 (ep05)，只在 work.json 的 episodes 里追加 blocks。"
        "每集：scene(含 place/time/light)、cast(在场/未出场)、若干 para/line、结尾唯一 hook。"
        "beat 必须是可视化的剧情推进。输出末行 JSON 摘要。'], cwd=r'D:\\\\视频创作\\\\ace-video-kingdom\\\\sites\\\\tinghe-archive', timeout=600)"
    ]
    code, out = run(opencode_cmd, "opencode_write_ep05")
    if code != 0:
        print("opencode 写入 ep05 失败，但继续尝试流水线")
    else:
        print("opencode 写入 ep05 完成")

    # 3. Run full pipeline (build/verify/audit/deploy)
    code, _ = run([sys.executable, "daily_originals.py"], "daily_originals.py")
    return code


if __name__ == "__main__":
    sys.exit(main())