"""Build an append-only wide-reference S01A fixture.

The previous controlled reference take used a tight scene anchor and produced
an overly close composition.  This fixture keeps the same novel-bound contract
but binds the provider to the approved wide S01A anchor.  It does not alter
prior fixtures or manifests.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def image_reference(path: Path) -> dict[str, object]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": str(path.resolve()),
        "sha256": digest,
        "size_bytes": path.stat().st_size,
    }


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: build_longmen_s01a_wide_reference.py SOURCE_FIXTURE WIDE_ANCHOR OUTPUT_DIR"
        )
    source = Path(sys.argv[1]).resolve()
    anchor = Path(sys.argv[2]).resolve()
    out = Path(sys.argv[3]).resolve()
    fixture = json.loads(source.read_text(encoding="utf-8"))
    shot = json.loads(json.dumps(fixture["shots"][0]))
    anchor_ref = image_reference(anchor)
    anchor_sha = str(anchor_ref["sha256"])
    for ref in shot.get("asset_refs", []):
        if ref.get("asset_id") == "SC01":
            ref["provider_ref"] = anchor_ref
            ref["sha256"] = anchor_sha
    shot["provider_mode"] = "reference"
    shot["provider_asset_ids"] = ["SC01"]
    shot["require_negative_prompt"] = True
    shot["contract"]["first_frame_ref"] = None
    shot["contract"]["last_frame_ref"] = None
    shot["contract"]["render_seconds"] = 8
    shot["contract"]["camera"] = {
        "scale": "wide_medium",
        "position": "three-quarter grave front",
        "movement": "NONE",
        "axis": "screen-left facing screen-right",
        "internal_cuts": 0,
    }
    shot["audio"]["render_seconds"] = 8
    shot["audio"]["action_duration"] = 3.0
    shot["audio"]["hold_duration"] = 4.0
    shot["media_profile"] = {"width": 720, "height": 1280, "fps": 24}
    shot["prompt"] = (
        "写实中文短剧，严格按《龙门战神》原文墓前段落。竖屏9:16，宽一点的静态中远景，"
        "人物和孤坟都完整可见，陆凡位于画面左侧三分之一，墓堆和青苔木板墓牌位于右侧，"
        "保留荒山空旷和人物与父亲坟墓之间的距离，不要把人物脸部或墓碑裁成近景。"
        "陆凡穿迷彩服独自久跪凝视，泛红双眼克制地看向乱石坟头；镜头固定在三脚架上。"
        "全程一条连续镜头，画面尺寸、透视、人物位置、墓堆位置和屏幕轴线保持不变；"
        "只允许自然呼吸、一次轻微低眼和手指轻微收紧，随后保持真实停留，不起身、不走动、不靠近镜头。"
        "真实感和情绪感染力优先于电影分镜感。"
        "不得出现英文、地图标记、墓碑大字、花束、鲜花、车辆、雨天湿地、第二人物、"
        "镜头推拉摇移、突然变焦、内部切镜、跳切、脸型变化、服装变化、字幕、logo、水印或原文之外事件。"
    )
    shot["negative_prompt"] = (
        "英文，地图，地图标记，墓碑大字，花束，鲜花，车辆，雨天，湿地，第二人物，"
        "墓碑特写，脸部近景，推拉摇移，自动变焦，内部切镜，跳切，改变脸型，改变服装，"
        "改变墓地布局，字幕，logo，水印，新增事件，MV风，宣传片风。"
    )
    fixture["schema"] = "video_kingdom.longmen_shotcore_s01a_wide_reference_r1"
    fixture["source_plan"] = "S01A wide reference rework r1; prior takes retained"
    fixture["shots"] = [shot]
    out.mkdir(parents=True, exist_ok=True)
    (out / "fixture.json").write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "COMPILED",
                "fixture": str(out / "fixture.json"),
                "render_seconds": 8,
                "mode": "reference",
                "provider_asset_ids": ["SC01"],
                "wide_anchor_sha256": anchor_sha,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
