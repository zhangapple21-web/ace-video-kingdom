"""Build a versioned S01A keyframe fixture without touching prior takes."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: build_longmen_s01a_keyframe_fixture.py SOURCE_FIXTURE OUTPUT_DIR")
    source = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    fixture = json.loads(source.read_text(encoding="utf-8"))
    shot = fixture["shots"][0]
    scene_ref = next(ref["provider_ref"] for ref in shot["asset_refs"] if ref["asset_id"] == "SC01")
    shot["provider_mode"] = "keyframe"
    shot["contract"]["first_frame_ref"] = scene_ref
    shot["contract"]["last_frame_ref"] = scene_ref
    shot["prompt"] = (
        shot["prompt"]
        + " 实体三脚架锁死的中景，整个镜头内画面尺寸、透视、人物与墓牌位置保持完全不变；"
        + "人物不向镜头靠近，镜头不自动追随，不推近、不拉远、不重新构图。"
    )
    shot["intent"]["primary_visual_event"] = "陆凡独自久跪凝视孤坟"
    fixture["schema"] = "video_kingdom.longmen_shotcore_s01a_keyframe.v1"
    fixture["source_plan"] = "S01A controlled rework; prior takes retained"
    out.mkdir(parents=True, exist_ok=True)
    (out / "fixture.json").write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "COMPILED", "fixture": str(out / "fixture.json"), "mode": "keyframe", "first_last_bound": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
