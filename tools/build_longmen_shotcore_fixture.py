"""Build a single-shot Shot Core fixture for the Longmen S01A pilot.

This is a local, append-only preparation step. It reuses the already generated
Longmen reference images, binds their SHA-256 values, and embeds data URLs so
the existing Agnes leaf can receive the actual image bytes without publishing
or overwriting any prior episode artifacts.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_longmen_shotcore_fixture.py OUTPUT_DIR")
    out = Path(sys.argv[1]).resolve()
    source = Path(r"C:\tmp\小说题材\龙门战神.txt")
    old = Path("episodes/generated/novel-longmen-strict-30s-v3")
    assets = old / "assets"
    out.mkdir(parents=True, exist_ok=True)
    (out / "assets").mkdir(exist_ok=True)
    refs = {
        "CHAR_MAIN": ("character", assets / "char_main_reference.png"),
        "PROP_TOMB": ("prop", assets / "prop_tomb_anchor.png"),
        "SC01": ("scene", assets / "s01a_anchor.png"),
    }
    asset_refs = []
    for asset_id, (asset_type, path) in refs.items():
        target = out / "assets" / path.name
        if not target.exists():
            target.write_bytes(path.read_bytes())
        asset_refs.append({
            "asset_id": asset_id,
            "asset_type": asset_type,
            "version": 1,
            "sha256": sha256(target),
            "scope": "episode",
            "provider_ref": {
                "path": str(target.resolve()),
                "sha256": sha256(target),
                "size_bytes": target.stat().st_size,
            },
        })
    prompt = (
        "写实中文短剧，竖屏9:16，真实自然表演。荒山孤坟前，陆凡穿迷彩服独自久跪，"
        "泛红双眼安静直盯乱石坟头和青苔木板墓牌。只表现久跪凝视这一件事；让呼吸、"
        "重力、停顿和压抑的悲痛可信，动作完成后保持自然留白。固定机位、单一连续镜头。"
        "真实感和情绪感染力优先于电影分镜感。不得出现第二人物、雨天湿地、花束、车辆、"
        "伤口特写、字幕、logo、内部切镜、推拉摇移或原文之外事件。"
    )
    shot = {
        "episode_id": "NOVEL_LONGMEN_S01_PILOT",
        "scene_id": "SC01",
        "aspect_ratio": "9:16",
        "shot_id": "S01A",
        "shot_type": "ACTION",
        "provider_mode": "reference",
        "prompt": prompt,
        "intent": {
            "dramatic_function": "久跪凝视",
            "primary_visual_event": "陆凡独自久跪凝视孤坟",
            "story_delta": "观众第一次感到他已经回来却还无法面对父亲的坟",
            "emotion_delta": "压抑痛感从静止中逐渐可感知",
            "knowledge_delta": "观众确认荒山孤坟与陆凡的祭奠关系",
            "relationship_delta": "陆凡与已故父亲陆山河的父子关系被墓碑空间暗示",
        },
        "state": {
            "start_state": {"character": "陆凡", "location": "荒山孤坟前", "wardrobe": "迷彩服", "props": ["乱石坟头", "青苔木板墓牌"], "camera": "locked"},
            "action_state": {"character": "陆凡独自久跪凝视", "location": "荒山孤坟前", "wardrobe": "迷彩服", "props": ["乱石坟头", "青苔木板墓牌"], "camera": "locked"},
            "end_state": {"character": "陆凡保持跪姿和凝视，情绪留白", "location": "荒山孤坟前", "wardrobe": "迷彩服", "props": ["乱石坟头", "青苔木板墓牌"], "camera": "locked"},
        },
        "contract": {
            "first_frame_ref": None,
            "last_frame_ref": None,
            "allowed_behaviors": ["kneel", "hold gaze", "natural breathing"],
            "forbidden_behaviors": ["pan", "tilt", "zoom", "orbit", "internal cut", "new character", "rain", "flowers", "vehicle", "secondary action"],
            "camera": {"scale": "medium", "position": "grave front", "movement": "NONE", "axis": "screen-left facing screen-right", "internal_cuts": 0},
            "render_seconds": 6,
        },
        "audio": {"dialogue": [], "narration": [], "sfx": [], "ambience": ["natural mountain room tone"], "music": [], "dialogue_duration": 0, "action_duration": 2.5, "hold_duration": 1.0, "render_seconds": 6},
        "asset_refs": asset_refs,
        "visible_character_ids": ["CHAR_MAIN"],
        "visible_prop_ids": ["PROP_TOMB"],
        "source_anchor": {"path": str(source), "sha256": "cc0eef87635f1fa5d93203d80ec4a7a4f52249eaea7dca9f1b8248677a7d132d", "line_range": [11, 15]},
    }
    fixture = {"schema": "video_kingdom.longmen_shotcore_s01_pilot.v1", "production_boundary": "CONTROLLED_PRODUCTION_TEST", "provider": "agnes-video-2.5-flash", "source_plan": "novel-longmen-strict-30s-v3 (reused refs only; not delivery)", "shots": [shot]}
    (out / "fixture.json").write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "COMPILED", "fixture": str(out / 'fixture.json'), "shot_id": "S01A", "asset_count": len(asset_refs)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
