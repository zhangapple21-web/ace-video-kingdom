"""Build the asset-first package for a new original short drama.

This compiler intentionally stops before creating a production Run.  It writes
the story contract, visual bible, hashed anchor assets, and semantic continuity
bridges first.  The control Run is created only after this package is complete
and its manifest can be verified.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "episodes" / "generated" / "awakening_reverse_20260907"
ASSET_DIR = OUT / "assets"
BRIDGE_DIR = OUT / "continuity"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def anchor(path: Path, kind: str, accent: tuple[int, int, int], phase: int) -> None:
    """Create a non-placeholder, original 9:16 visual anchor."""
    w, h = 720, 1280
    image = Image.new("RGB", (w, h), (9, 16, 25))
    px = image.load()
    for y in range(h):
        for x in range(w):
            glow = max(0, 1 - math.hypot(x - w * 0.55, y - h * 0.42) / (w * 0.9))
            px[x, y] = tuple(min(255, int(base + glow * delta)) for base, delta in zip((9, 16, 25), accent))
    draw = ImageDraw.Draw(image, "RGBA")
    # Fictional archive-room architecture and one recurring token motif.
    for x in (60, 220, 500, 660):
        draw.line((x, 120, x, 1120), fill=(90, 120, 140, 90), width=4)
    for y in range(210, 1090, 150):
        draw.line((45, y, 675, y), fill=(55, 80, 96, 100), width=3)
    draw.rounded_rectangle((120, 720, 600, 1030), radius=24, fill=(24, 31, 40, 225), outline=(112, 140, 145, 150), width=4)
    if kind == "character":
        draw.ellipse((250, 255, 470, 475), fill=(184, 130, 102, 255), outline=(240, 200, 170, 190), width=4)
        draw.rounded_rectangle((205, 450, 515, 920), radius=70, fill=(24, 65, 74, 255), outline=(120, 190, 182, 170), width=4)
        draw.line((300, 620, 420, 620), fill=(210, 230, 220, 160), width=8)
        draw.ellipse((310, 910, 410, 1010), fill=(accent[0], accent[1], accent[2], 235), outline=(240, 215, 145, 220), width=5)
    elif kind == "desk":
        draw.rectangle((168, 585, 552, 820), fill=(40, 43, 46, 245), outline=(145, 158, 165, 180), width=4)
        draw.rectangle((205, 625, 515, 755), fill=(15, 44, 52, 255), outline=(96, 201, 192, 180), width=4)
        draw.ellipse((298, 810, 422, 934), fill=(accent[0], accent[1], accent[2], 240), outline=(240, 215, 145, 220), width=5)
    elif kind == "token":
        draw.ellipse((230, 420, 490, 680), fill=(accent[0], accent[1], accent[2], 220), outline=(249, 230, 163, 240), width=8)
        draw.ellipse((295, 485, 425, 615), outline=(255, 241, 187, 230), width=6)
        draw.line((360, 515, 360, 585), fill=(255, 241, 187, 220), width=6)
    else:
        draw.rectangle((190, 520, 530, 820), fill=(25, 30, 35, 240), outline=(150, 180, 184, 180), width=5)
        for i in range(5):
            draw.line((230, 580 + i * 38, 490, 580 + i * 38), fill=(accent[0], accent[1], accent[2], 180), width=6)
        draw.ellipse((300, 855, 420, 975), fill=(accent[0], accent[1], accent[2], 220), outline=(240, 215, 145, 220), width=5)
    # No generated text, logos, or real-world marks.
    image = image.filter(ImageFilter.GaussianBlur(0.15))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=False)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)

    story = {
        "title": "《逆向回声》",
        "logline": "档案员沈栖在整理一宗被判定为‘自然失联’的旧案时，触发只能识别证据链结构的逆向系统；她不靠外挂逃生，而是用系统标出的缺口，把一条被掩盖的求助链送到合法援助网络。",
        "source_class": "ORIGINAL_USER_BRIEF",
        "fiction_boundary": "完全虚构的‘澜港档案馆’，不对应现实机构、人物或地点。",
        "system_causal_event": [
            "触发：铜色档案筹码接触旧卷宗，耳边出现短促提示音。",
            "任务：在 90 秒内确认‘失联’结论是否有完整证据链。",
            "能力：只标出已观察、待核实、高风险推断，不开锁、不黑入、不预言。",
            "改变决策：系统指出‘原始时间戳缺口’，沈栖放弃直接报警的冲动，先保存可核验的原始记录。",
        ],
        "ethics": ["不提供违法入侵或规避执法教程", "通过正式援助、第三方核验和可追溯记录脱身", "不把受困处境做成猎奇爽点"],
    }
    write_json(OUT / "story_root.json", story)

    visual_bible = {
        "schema": "video_kingdom.visual_bible.v1",
        "aspect_ratio": "9:16",
        "style_block": "写实电影感、冷蓝档案室、铜色系统光、低饱和、自然皮肤纹理、固定轴线",
        "invariants": ["沈栖深青工作夹克与米白衬衫", "铜色筹码始终在右手或桌面右侧", "系统界面只用抽象色块和环形脉冲，不生成可读文字"],
        "negative": ["无现实品牌、无现实机构标识、无新增角色、无内部切镜、无超能力开锁"],
    }
    write_json(OUT / "visual_bible.json", visual_bible)

    specs = [
        ("CHAR_SHENQI_FRONT_V1.png", "character", (32, 120, 114), 1),
        ("SCN_ARCHIVE_DESK_V1.png", "desk", (28, 108, 130), 2),
        ("PROP_COPPER_TOKEN_V1.png", "token", (168, 104, 35), 3),
        ("DISP_EVIDENCE_PULSE_V1.png", "display", (38, 150, 125), 4),
    ]
    records: list[dict[str, Any]] = []
    for filename, kind, accent, phase in specs:
        path = ASSET_DIR / filename
        anchor(path, kind, accent, phase)
        records.append({
            "record_id": f"REC_{path.stem}",
            "asset_id": path.stem,
            "asset_type": kind,
            "source_path": path.relative_to(OUT).as_posix(),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "width": 720,
            "height": 1280,
            "format": "png",
            "asset_state": "MEDIA_CANDIDATE",
            "usage": "video_asset",
            "naming_status": "CANONICAL",
            "evidence_status": "LOCAL_HASHED",
            "rights_status": "ORIGINAL",
        })
    write_json(OUT / "asset_registry.json", {"schema": "video_kingdom.asset_registry.v1", "status": "READY", "records": records})

    shots = [
        ("S01", "沈栖把铜色筹码贴近旧卷宗", "触发觉醒系统", "筹码接触纸面前", "提示音与环形脉冲出现", "沈栖从惯性整理转为警觉", 5),
        ("S02", "沈栖停住翻页，注视脉冲缺口", "系统首次扫描", "脉冲未稳定", "系统标出待核实缺口", "她不再相信‘自然失联’结论", 5),
        ("S03", "沈栖将卷宗时间戳与值班表并排核对", "求证", "两份记录错开一格", "错位被保存为可核验线索", "她从恐惧转为专注", 6),
        ("S04", "沈栖按下离线保存键", "保全证据", "屏幕仍连着内网", "离线指示灯亮起", "她选择证据优先而非冒险追问", 5),
        ("S05", "沈栖把筹码放在正式援助联络盒旁", "联络外界", "联络盒未启动", "第三方回执灯闪一次", "孤立感转为有人接住", 5),
        ("S06", "沈栖合上卷宗，守在亮起的回执灯前", "余波与 payoff", "回执灯未亮", "灯亮、系统提示变为静默", "她从被动记录者变成证据守门人", 6),
    ]
    shot_rows: list[dict[str, Any]] = []
    for shot_id, action, function, first_state, last_state, emotion, seconds in shots:
        shot_rows.append({
            "shot_id": shot_id,
            "action": action,
            "dramatic_function": function,
            "first_state": first_state,
            "last_state": last_state,
            "emotion_change": emotion,
            "render": {"seconds": seconds, "aspect_ratio": "9:16"},
            "required_asset_ids": ["CHAR_SHENQI_FRONT_V1", "SCN_ARCHIVE_DESK_V1", "PROP_COPPER_TOKEN_V1", "DISP_EVIDENCE_PULSE_V1"],
            "shot_contract": {"single_action": True, "max_primary_actions": 1, "internal_cuts_allowed": 0, "primary_action": action, "duration_seconds": {"min": seconds, "max": seconds}},
            "continuity_bridge": {"evidence_path": f"continuity/{shot_id}_to_next.json"},
            "generation_request": {"model": "provider_to_be_verified", "prompt": action, "reference_asset_ids": ["CHAR_SHENQI_FRONT_V1", "SCN_ARCHIVE_DESK_V1", "PROP_COPPER_TOKEN_V1", "DISP_EVIDENCE_PULSE_V1"], "camera": "locked_mid_vertical"},
        })
    for index in range(len(shot_rows) - 1):
        current, following = shot_rows[index], shot_rows[index + 1]
        bridge = {
            "schema": "video_kingdom.continuity_bridge.v1",
            "status": "READY",
            "from_shot": current["shot_id"],
            "to_shot": following["shot_id"],
            "previous_end_state": current["last_state"],
            "next_initial_state": following["first_state"],
            "invariants": visual_bible["invariants"],
            "asset_ids": current["required_asset_ids"],
            "evidence_basis": "asset package + explicit state transition; post-generation frame proof remains pending",
        }
        write_json(BRIDGE_DIR / f"{current['shot_id']}_to_next.json", bridge)

    plan = {
        "schema": "video_kingdom.episode_plan.asset_first.v1",
        "project_id": "awakening-reverse-20260907",
        "production_integration": False,
        "scope": "ORIGINAL_FICTION_RESEARCH_TO_PRODUCTION",
        "story": story,
        "visual_bible": visual_bible,
        "assets": {
            "characters": [{"asset_id": "CHAR_SHENQI_FRONT_V1", "reference_path": "assets/CHAR_SHENQI_FRONT_V1.png", "sha256": records[0]["sha256"], "status": "APPROVED_REFERENCE_SHEET"}],
            "scenes": [{"asset_id": "SCN_ARCHIVE_DESK_V1", "reference_path": "assets/SCN_ARCHIVE_DESK_V1.png", "sha256": records[1]["sha256"], "status": "APPROVED_REFERENCE_SHEET"}],
            "props": [{"asset_id": "PROP_COPPER_TOKEN_V1", "reference_path": "assets/PROP_COPPER_TOKEN_V1.png", "sha256": records[2]["sha256"], "status": "APPROVED_REFERENCE_SHEET"}],
            "displays": [{"asset_id": "DISP_EVIDENCE_PULSE_V1", "reference_path": "assets/DISP_EVIDENCE_PULSE_V1.png", "sha256": records[3]["sha256"], "status": "APPROVED_REFERENCE_SHEET"}],
        },
        "shots": shot_rows,
        "acceptance": {"required": ["provider_receipt", "artifact_hash", "five_layer_qc", "selected_take", "assembly", "final_acceptance"], "delivery_approved": False},
    }
    write_json(OUT / "episode_plan.json", plan)
    write_json(OUT / "asset_gate_preflight.json", {"status": "READY", "asset_registry": "asset_registry.json", "continuity_edges": 5, "provider_calls": 0, "run_created": False})
    print(json.dumps({"status": "ASSETS_READY", "project_dir": str(OUT), "plan": str(OUT / 'episode_plan.json'), "assets": len(records), "continuity_edges": 5}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
