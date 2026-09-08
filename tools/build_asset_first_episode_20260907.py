"""Build one fresh asset-first micro drama package without creating a Run."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "episodes" / "generated" / "reverse_system_new_20260907"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_anchor(path: Path, kind: str, accent: tuple[int, int, int]) -> None:
    width, height = 720, 1280
    image = Image.new("RGB", (width, height), (8, 15, 24))
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            glow = max(0.0, 1.0 - math.hypot(x - 390, y - 470) / 850.0)
            pixels[x, y] = tuple(min(255, int(base + glow * delta)) for base, delta in zip((8, 15, 24), accent))
    draw = ImageDraw.Draw(image, "RGBA")
    for x in (70, 220, 500, 650):
        draw.line((x, 120, x, 1120), fill=(110, 140, 155, 90), width=4)
    for y in range(190, 1100, 145):
        draw.line((45, y, 675, y), fill=(55, 80, 96, 100), width=3)
    if kind == "character":
        draw.ellipse((250, 260, 470, 480), fill=(183, 129, 101, 255), outline=(240, 203, 175, 190), width=4)
        draw.rounded_rectangle((205, 450, 515, 925), radius=70, fill=(24, 67, 76, 255), outline=(120, 190, 182, 170), width=4)
        draw.line((300, 620, 420, 620), fill=(210, 230, 220, 150), width=8)
    elif kind == "desk":
        draw.rectangle((150, 560, 570, 825), fill=(38, 43, 47, 245), outline=(145, 158, 165, 180), width=4)
        draw.rectangle((195, 610, 525, 760), fill=(15, 44, 52, 255), outline=(96, 201, 192, 180), width=4)
    else:
        draw.ellipse((225, 390, 495, 660), fill=(*accent, 220), outline=(249, 230, 163, 240), width=8)
        draw.ellipse((295, 460, 425, 590), outline=(255, 241, 187, 230), width=6)
        draw.line((360, 485, 360, 565), fill=(255, 241, 187, 220), width=6)
    draw.ellipse((302, 875, 418, 991), fill=(*accent, 230), outline=(240, 215, 145, 220), width=5)
    image.filter(ImageFilter.GaussianBlur(0.15)).save(path, format="PNG", optimize=False)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    assets_dir = OUT / "assets"
    continuity_dir = OUT / "continuity"
    assets_dir.mkdir(exist_ok=True)
    continuity_dir.mkdir(exist_ok=True)
    story = {
        "title": "《逆时针证词》",
        "logline": "修复师林照在旧车站的失物柜里触发逆向系统，系统不替她预言未来，只把被倒写的证词还原成可核验的三步证据。",
        "source_class": "ORIGINAL_FICTION_FROM_USER_BRIEF",
        "fiction_boundary": "完全虚构的临潮车站与人物，不对应现实机构、案件或个人。",
        "system_causal_event": [
            "铜色筹码贴上倒置车票时触发短促脉冲。",
            "系统只能把已观察、待核验、矛盾三类证据反向排列。",
            "系统标出的矛盾改变林照的决定：她停止追逐传闻，先保全原始票根并走正式报失流程。",
        ],
        "ethics": ["不展示入侵、跟踪或规避执法技巧", "证据通过正式报失与第三方见证进入援助链", "受困处境不被猎奇化"],
    }
    write_json(OUT / "story_root.json", story)
    visual_bible = {
        "schema": "video_kingdom.visual_bible.v1",
        "aspect_ratio": "9:16",
        "style_block": "写实电影感、冷蓝旧车站维修间、铜色系统脉冲、低饱和、自然皮肤纹理、固定轴线",
        "invariants": ["林照深青工装外套与米白衬衫", "铜色筹码始终在右手或桌面右侧", "系统只显示抽象环形光，不出现可读文字"],
        "negative": ["无现实品牌、无现实机构标识、无新增角色、无内部切镜、无超能力开锁"],
    }
    write_json(OUT / "visual_bible.json", visual_bible)
    specs = [
        ("CHAR_LINZHAO_V1.png", "character", (34, 122, 116)),
        ("SCN_TIDE_STATION_DESK_V1.png", "desk", (28, 108, 130)),
        ("PROP_REVERSED_TICKET_TOKEN_V1.png", "token", (168, 104, 35)),
    ]
    records: list[dict[str, Any]] = []
    for filename, kind, accent in specs:
        path = assets_dir / filename
        make_anchor(path, kind, accent)
        records.append({
            "record_id": f"REC_{path.stem}", "asset_id": path.stem, "asset_type": kind,
            "source_path": path.relative_to(OUT).as_posix(), "sha256": sha256(path),
            "bytes": path.stat().st_size, "width": 720, "height": 1280, "format": "png",
            "asset_state": "MEDIA_CANDIDATE", "usage": "video_asset", "naming_status": "CANONICAL",
            "evidence_status": "LOCAL_HASHED", "rights_status": "ORIGINAL",
        })
    write_json(OUT / "asset_registry.json", {"schema": "video_kingdom.asset_registry.v1", "status": "READY", "records": records})
    asset_ids = [row["asset_id"] for row in records]
    shots = [
        ("S01", "林照把铜色筹码贴上倒置车票，停住手", "触发逆向系统", "筹码尚未接触票根", "铜色脉冲亮起", 5),
        ("S02", "林照将倒置车票翻回正面，发现日期与失物柜记录矛盾", "系统给出可核验矛盾", "票根仍倒置", "两条记录被并排保全", 5),
        ("S03", "林照把票根放进正式报失信封并按下封口", "证据优先的决定", "信封未封口", "封口完成，脉冲归于静默", 5),
    ]
    shot_rows = []
    for shot_id, action, function, first_state, last_state, seconds in shots:
        prompt = ("写实电影感竖屏短镜头，临潮车站维修间，年轻修复师林照穿深青工装外套和米白衬衫，"
                  f"{action}。冷蓝环境、铜色抽象系统脉冲，固定中近景，单一动作，动作完成后保留反应，"
                  "不切镜、不新增人物、不出现可读文字、logo或现实机构标识。")
        shot_rows.append({
            "shot_id": shot_id, "episode_id": "reverse-system-new-20260907", "action": action,
            "dramatic_function": function, "first_state": first_state, "last_state": last_state,
            "render": {"model": "agnes-video-2.5-flash", "flash_mode": "text", "seconds": seconds, "aspect_ratio": "9:16", "size": "720P"},
            "shot_contract": {"single_action": True, "max_primary_actions": 1, "internal_cuts_allowed": 0, "primary_action": action, "duration_seconds": {"min": seconds, "max": seconds}},
            "reference_assets": [{"asset_id": aid, "sha256": rec["sha256"], "provider_ref": f"assets/{rec['asset_id']}.png"} for aid, rec in zip(asset_ids, records)],
            "visible_entities": asset_ids, "camera": {"framing": "medium_close_vertical", "movement": "NONE", "axis": "locked_station_desk_axis"},
            "audio_contract": {"status": "NOT_APPLICABLE", "dialogue": []},
            "generation_request": {"model": "agnes-video-2.5-flash", "prompt": prompt, "camera": "locked_mid_vertical", "reference_asset_ids": asset_ids},
            "prompt": prompt,
        })
    for current, following in zip(shot_rows, shot_rows[1:]):
        bridge = {"schema": "video_kingdom.continuity_bridge.v1", "status": "READY", "from_shot": current["shot_id"], "to_shot": following["shot_id"], "previous_end_state": current["last_state"], "next_initial_state": following["first_state"], "invariants": visual_bible["invariants"], "asset_ids": asset_ids, "evidence_basis": "asset package + explicit state transition; post-generation frame proof pending"}
        write_json(continuity_dir / f"{current['shot_id']}_to_{following['shot_id']}.json", bridge)
        current["continuity_bridge"] = {"evidence_path": f"continuity/{current['shot_id']}_to_{following['shot_id']}.json"}
    plan = {"schema": "video_kingdom.episode_plan.asset_first.v1", "project_id": "reverse-system-new-20260907", "production_integration": False, "scope": "ORIGINAL_FICTION_RESEARCH_TO_PRODUCTION", "story": story, "visual_bible": visual_bible, "assets": {"characters": [{"asset_id": asset_ids[0], "reference_path": f"assets/{asset_ids[0]}.png", "sha256": records[0]["sha256"], "status": "APPROVED_REFERENCE_SHEET"}], "scenes": [{"asset_id": asset_ids[1], "reference_path": f"assets/{asset_ids[1]}.png", "sha256": records[1]["sha256"], "status": "APPROVED_REFERENCE_SHEET"}], "props": [{"asset_id": asset_ids[2], "reference_path": f"assets/{asset_ids[2]}.png", "sha256": records[2]["sha256"], "status": "APPROVED_REFERENCE_SHEET"}]}, "shots": shot_rows, "acceptance": {"duration_window_seconds": [12, 20], "required": ["provider_receipt", "artifact_hash", "five_layer_qc", "selected_take", "assembly", "final_acceptance"], "delivery_approved": False}}
    write_json(OUT / "episode_plan.json", plan)
    write_json(OUT / "asset_gate_preflight.json", {"status": "READY", "asset_registry": "asset_registry.json", "continuity_edges": 2, "provider_calls": 0, "run_created": False})
    print(json.dumps({"status": "ASSETS_READY", "project_dir": str(OUT), "plan": str(OUT / "episode_plan.json"), "assets": len(records), "shots": len(shot_rows), "continuity_edges": 2}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
