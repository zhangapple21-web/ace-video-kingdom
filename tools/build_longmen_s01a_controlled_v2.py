"""Compile an append-only S01A controlled rework fixture.

This changes the control contract rather than replaying the prior keyframe
request: a single approved scene anchor in reference mode, an explicit negative
prompt, and a locked static hold. Prior fixtures and takes are never modified.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: build_longmen_s01a_controlled_v2.py SOURCE_FIXTURE OUTPUT_DIR")
    source = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    fixture = json.loads(source.read_text(encoding="utf-8"))
    shot = json.loads(json.dumps(fixture["shots"][0]))
    scene_ref = next(ref["provider_ref"] for ref in shot["asset_refs"] if ref["asset_id"] == "SC01")
    shot["provider_mode"] = "reference"
    shot["provider_asset_ids"] = ["SC01"]
    shot["require_negative_prompt"] = True
    shot["contract"]["first_frame_ref"] = None
    shot["contract"]["last_frame_ref"] = None
    shot["contract"]["render_seconds"] = 6
    shot["contract"]["camera"] = {
        "scale": "medium",
        "position": "grave front",
        "movement": "NONE",
        "axis": "screen-left facing screen-right",
        "internal_cuts": 0,
    }
    shot["audio"]["render_seconds"] = 6
    shot["audio"]["action_duration"] = 2.0
    shot["audio"]["hold_duration"] = 2.5
    shot["negative_prompt"] = (
        "禁止坟墓文字、英文、地图标记、花束、鲜花、车辆、第二人物、墓碑特写、镜头推拉摇移、"
        "突然变焦、内部切镜、跳切、改变人物脸型、改变服装、改变墓地布局、悬浮元素、字幕、logo、水印。"
    )
    shot["prompt"] = (
        "写实中文短剧，竖屏9:16，实体三脚架锁死的静态中景。"
        "荒山孤坟前，陆凡穿迷彩服独自久跪凝视，泛红双眼安静直盯乱石坟头和青苔木板墓牌。"
        "从第一帧到最后一帧保持完全相同的画面尺寸、透视、人物位置、墓牌位置和屏幕轴线；"
        "只允许自然呼吸、轻微眨眼和真实停留，不走动、不起身、不靠近镜头。"
        "固定机位、单一连续镜头、无内部切换。真实感和情绪感染力优先于电影分镜感。"
        "不得出现第二人物、雨天湿地、花束、车辆、伤口特写、字幕、logo、推拉摇移或原文之外事件。"
    )
    fixture["schema"] = "video_kingdom.longmen_shotcore_s01a_controlled_v2"
    fixture["source_plan"] = "S01A controlled rework v2; prior takes retained; changed control contract"
    fixture["shots"] = [shot]
    out.mkdir(parents=True, exist_ok=True)
    (out / "fixture.json").write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "COMPILED", "fixture": str(out / "fixture.json"), "render_seconds": 6, "mode": "reference", "provider_asset_ids": ["SC01"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
