"""Compile a human-dialogue-first, asset-first AI short-drama package.

The compiler creates the screenplay, visual bible, hashed reference assets and
continuity bridges.  It deliberately does not create a production Run.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "episodes" / "generated" / "reverse_system_human_20260907"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def anchor(path: Path, kind: str, accent: tuple[int, int, int]) -> None:
    w, h = 720, 1280
    image = Image.new("RGB", (w, h), (8, 15, 24))
    px = image.load()
    for y in range(h):
        for x in range(w):
            glow = max(0.0, 1.0 - math.hypot(x - 390, y - 470) / 850.0)
            px[x, y] = tuple(min(255, int(base + glow * delta)) for base, delta in zip((8, 15, 24), accent))
    draw = ImageDraw.Draw(image, "RGBA")
    for x in (70, 220, 500, 650):
        draw.line((x, 120, x, 1120), fill=(110, 140, 155, 90), width=4)
    for y in range(190, 1100, 145):
        draw.line((45, y, 675, y), fill=(55, 80, 96, 100), width=3)
    if kind == "character":
        draw.ellipse((250, 260, 470, 480), fill=(183, 129, 101, 255), outline=(240, 203, 175, 190), width=4)
        draw.rounded_rectangle((205, 450, 515, 925), radius=70, fill=(24, 67, 76, 255), outline=(120, 190, 182, 170), width=4)
        draw.line((300, 620, 420, 620), fill=(210, 230, 220, 160), width=8)
    elif kind == "desk":
        draw.rectangle((150, 560, 570, 825), fill=(38, 43, 47, 245), outline=(145, 158, 165, 180), width=4)
        draw.rectangle((195, 610, 525, 760), fill=(15, 44, 52, 255), outline=(96, 201, 192, 180), width=4)
    elif kind == "ticket":
        draw.rounded_rectangle((180, 370, 540, 700), radius=18, fill=(219, 207, 165, 235), outline=(249, 230, 163, 240), width=6)
        draw.line((235, 470, 485, 470), fill=(100, 90, 70, 180), width=5)
        draw.line((235, 540, 430, 540), fill=(100, 90, 70, 180), width=5)
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

    project_id = "reverse-system-human-20260907"
    story = {
        "title": "《逆向回声》",
        "logline": "修复师林照在临潮车站整理一张被反复作废的旧票，触发只能整理证据关系的逆向系统；她不靠外挂逃走，而是把一条矛盾记录送进正式核验链。",
        "source_class": "ORIGINAL_USER_BRIEF",
        "fiction_boundary": "完全虚构的临潮车站与人物，不对应现实机构、案件或个人。",
        "root_brief": {
            "theme": "穿越式觉醒不是获得无敌外挂，而是学会把混乱倒过来核对。",
            "relationship_and_conflict": "林照想保护一张旧票的原始证据；内网值班声催她按流程销毁。",
            "mainline_events": ["触发系统", "发现矛盾", "保全原件", "正式报失", "等待第三方核验"],
            "source_rights_note": "原创虚构，不改编具体小说或现实案件。",
            "semantic_anchor_type": "逆向证据链",
        },
        "scene_nodes": [{"scene_id": "SCENE_TIDE_ARCHIVE", "place": "临潮车站维修档案间", "time": "夜班交接前", "fictional": True}],
        "system_causal_event": [
            "铜色筹码接触倒置票根，短促脉冲让林照停手。",
            "系统给出九十秒新手任务：找出一条能被第三方核验的矛盾。",
            "系统只区分已观察、待核实、高风险推断；它不能开锁、黑入或替人定案。",
            "它指出时间戳缺口，林照因此放弃追问内网，先离线保全原件。",
        ],
        "ethics": ["地点与组织完全虚构", "不提供入侵、伪造或规避执法步骤", "脱身依靠正式报失与第三方核验"],
    }
    write_json(OUT / "story_root.json", story)

    visual_bible = {
        "schema": "video_kingdom.visual_bible.v1",
        "aspect_ratio": "9:16",
        "style_block": "写实电影感、冷蓝旧车站维修间、铜色系统脉冲、低饱和、固定轴线、自然皮肤纹理",
        "invariants": ["林照深青工装外套与米白衬衫", "铜色筹码始终在右手或桌面右侧", "系统只显示抽象环形光，不出现可读文字"],
        "negative": ["无现实品牌、无现实机构标识、无新增可见人物、无内部切镜、无超能力开锁"],
    }
    write_json(OUT / "visual_bible.json", visual_bible)

    specs = [
        ("CHAR_LINZHAO_V2.png", "character", (34, 122, 116)),
        ("SCN_TIDE_STATION_DESK_V2.png", "desk", (28, 108, 130)),
        ("PROP_REVERSED_TICKET_V2.png", "ticket", (168, 104, 35)),
        ("PROP_COPPER_TOKEN_V2.png", "token", (178, 112, 38)),
    ]
    records: list[dict[str, Any]] = []
    for filename, kind, accent in specs:
        path = assets_dir / filename
        anchor(path, kind, accent)
        records.append({"record_id": f"REC_{path.stem}", "asset_id": path.stem, "asset_type": kind, "source_path": path.relative_to(OUT).as_posix(), "sha256": sha256(path), "bytes": path.stat().st_size, "width": 720, "height": 1280, "format": "png", "asset_state": "MEDIA_CANDIDATE", "usage": "video_asset", "naming_status": "CANONICAL", "evidence_status": "LOCAL_HASHED", "rights_status": "ORIGINAL"})
    write_json(OUT / "asset_registry.json", {"schema": "video_kingdom.asset_registry.v1", "status": "READY", "records": records})

    character_dossier = {
        "character_id": records[0]["asset_id"], "production_integration": False, "fictional_character": True,
        "identity_invariants": {"visual": ["深青工装外套", "米白衬衫"], "negative_constraints": ["不得变更为现实人物脸孔"], "behavioral": ["紧张时先抿嘴再做决定"], "relational": ["与内网值班声存在流程冲突"]},
        "allowed_evolution": {"may_change": ["从被动整理者变成证据守门人"], "requires_new_dossier_version": True},
        "rights_and_provenance": {"source": "ORIGINAL", "disallowed_sources": ["UNAUTHORIZED_REAL_PERSON_LIKENESS"]},
        "visual_assets": [{"anchor_id": records[0]["asset_id"], "sha256": records[0]["sha256"], "path": records[0]["source_path"]}],
    }
    write_json(OUT / "assets" / "CHAR_LINZHAO_V2.dossier.json", character_dossier)

    asset_ids = [row["asset_id"] for row in records]
    beats = [
        {"id": "S01", "time": "0-8秒", "action": "林照把铜色筹码贴近倒置票根，手停在半空", "visual": "票根上的旧印记与铜色脉冲同框", "dialogue": [("林照", "这张票怎么又回来了？昨晚明明已经作废了。"), ("系统", "逆向证据系统，启动。九十秒内，找出一条能核验的矛盾。"), ("林照", "你至少先告诉我，查什么？")], "sound": "纸张摩擦，短促脉冲，远处换班铃", "cut": "系统任务落下，切入扫描"},
        {"id": "S02", "time": "8-16秒", "action": "林照不翻票，先把票根和登记夹并排压平", "visual": "两份记录日期错开一格，环形光在缺口处停住", "dialogue": [("系统", "已看到：票面日期和登记日期不一致。还不能叫真相。"), ("林照", "行，那就给我一件能查的。"), ("系统", "待核实：原始时间戳缺口。")], "sound": "指腹压纸，内网电流声", "cut": "缺口成为可见线索，切入阻力"},
        {"id": "S03", "time": "16-24秒", "action": "内网喇叭响起，林照的手收回，盯住销毁盒", "visual": "销毁盒盖半开，票根没有被放进去", "dialogue": [("值班声", "林照，按流程处理。旧票不能留。"), ("林照", "流程写的是销毁复印件，没说销毁原件。"), ("系统", "高风险推断：规则可能被误用。证据不足。")], "sound": "喇叭失真，金属盒轻响", "cut": "外部压力出现，切到她的选择"},
        {"id": "S04", "time": "24-32秒", "action": "林照把票根放进透明证据袋，按下离线保存键", "visual": "离线指示灯亮起，铜色脉冲降为稳定一圈", "dialogue": [("林照", "好，我不跟它争。先把原件留下。"), ("系统", "已观察：原件已保全。不可替代的记录，优先于解释。")], "sound": "封袋咔哒声，保存提示音", "cut": "决定完成，切入正式联络"},
        {"id": "S05", "time": "32-40秒", "action": "林照把证据袋和铜色筹码放到正式报失联络盒旁，按下通话键", "visual": "回执灯从暗到亮一次，画面不出现可读文字", "dialogue": [("林照", "这里是临潮站正式报失。我报的不是猜测，是一条对不上的记录。"), ("系统", "第三方回执已发出。等待核验。"), ("林照", "听见了。")], "sound": "通话接通，单声回执灯", "cut": "有人接住证据，切入余波"},
        {"id": "S06", "time": "40-48秒", "action": "林照合上卷宗，守在回执灯前，没有追出去", "visual": "她的手离开筹码，肩膀慢慢放松，脉冲归于静默", "dialogue": [("林照", "这次，轮到他们回答了。"), ("系统", "任务阶段：等待第三方核验。"), ("林照", "那就等。")], "sound": "环境噪声退远，只留呼吸和灯的轻响", "cut": "余波金句，片尾停住"},
    ]

    shot_rows: list[dict[str, Any]] = []
    for beat in beats:
        seconds = int(beat["time"].split("-")[1].replace("秒", "")) - int(beat["time"].split("-")[0])
        script_lines = [{"speaker": speaker, "text": text} for speaker, text in beat["dialogue"]]
        prompt = ("写实电影感竖屏短镜头，临潮车站维修档案间，年轻修复师林照穿深青工装外套和米白衬衫。" + beat["action"] + "。" + beat["visual"] + "。" + beat["sound"] + "。镜头固定中近景，单一主动作，动作完成后保留人物反应，不切镜、不新增可见人物、不出现可读文字、logo或现实机构标识。")
        shot_rows.append({"shot_id": beat["id"], "episode_id": project_id, "scene_id": "SCENE_TIDE_ARCHIVE", "time_range": beat["time"], "action": beat["action"], "dramatic_function": beat["visual"], "first_state": "动作尚未完成", "last_state": "动作完成并留下反应", "required_asset_ids": asset_ids, "continuity_bridge_to_next": f"continuity/{beat['id']}_to_next.json", "continuity_bridge": {"evidence_path": f"continuity/{beat['id']}_to_next.json"}, "quality_gate": {"picture": "PENDING", "motion": "PENDING", "camera": "PENDING", "continuity": "PENDING", "director": "PENDING"}, "script": {"audio_status": "PLANNED", "dialogue": script_lines}, "shot_contract": {"single_action": True, "max_primary_actions": 1, "internal_cuts_allowed": 0, "primary_action": beat["action"], "duration_seconds": {"min": seconds, "max": seconds}}, "camera": {"framing": "medium_close_vertical", "movement": "NONE", "axis": "locked_station_desk_axis"}, "audio_contract": {"status": "PLANNED", "dialogue": script_lines}, "render": {"model": "agnes-video-2.5-flash", "flash_mode": "text", "seconds": seconds, "aspect_ratio": "9:16", "size": "720P"}, "prompt": prompt})

    for current, following in zip(shot_rows, shot_rows[1:]):
        bridge = {"schema": "video_kingdom.continuity_bridge.v1", "status": "READY", "from_shot": current["shot_id"], "to_shot": following["shot_id"], "previous_end_state": current["last_state"], "next_initial_state": following["first_state"], "invariants": visual_bible["invariants"], "asset_ids": asset_ids, "evidence_basis": "asset package + explicit state transition; post-generation frame proof pending"}
        write_json(continuity_dir / f"{current['shot_id']}_to_next.json", bridge)

    plan = {"schema": "video_kingdom.episode_plan.asset_first.v1", "project_id": project_id, "status": "READY", "production_integration": False, "scope": "ORIGINAL_FICTION_RESEARCH_TO_PRODUCTION", "story": story, "visual_bible": visual_bible, "assets": {"characters": [{"asset_id": asset_ids[0], "reference_path": f"assets/{asset_ids[0]}.png", "sha256": records[0]["sha256"], "status": "APPROVED_REFERENCE_SHEET", "dossier_path": "assets/CHAR_LINZHAO_V2.dossier.json"}], "scenes": [{"asset_id": asset_ids[1], "reference_path": f"assets/{asset_ids[1]}.png", "sha256": records[1]["sha256"], "status": "APPROVED_REFERENCE_SHEET"}], "props": [{"asset_id": asset_ids[2], "reference_path": f"assets/{asset_ids[2]}.png", "sha256": records[2]["sha256"], "status": "APPROVED_REFERENCE_SHEET"}, {"asset_id": asset_ids[3], "reference_path": f"assets/{asset_ids[3]}.png", "sha256": records[3]["sha256"], "status": "APPROVED_REFERENCE_SHEET"}]}, "renderer_routing": {"mainline_identity_requires": "VERIFIED_REFERENCE_CONTROLLED_RENDERER", "agnes_video_2_5_flash": "PRIMARY_FREE_REFERENCE_CONTROLLED_RENDERER"}, "shots": shot_rows, "acceptance": {"duration_window_seconds": [42, 60], "required": ["provider_receipt", "artifact_hash", "five_layer_qc", "selected_take", "assembly", "final_acceptance"], "delivery_approved": False}}
    write_json(OUT / "episode_plan.json", plan)

    screenplay = ["# 《逆向回声》", "", "45–50秒竖屏 AI 短剧｜原创虚构｜人话对白版", "", story["logline"], "", "## 角色", "- **林照**：临潮车站维修档案员，嘴硬但谨慎。", "- **逆向证据系统**：只整理证据关系，不替人下结论。", "- **值班声**：只通过喇叭出现的流程压力。", ""]
    for beat in beats:
        screenplay += [f"### {beat['id']}｜{beat['time']}｜{beat['action']}", f"画面：{beat['visual']}", f"声音：{beat['sound']}", ""]
        for speaker, text in beat["dialogue"]:
            screenplay.append(f"**{speaker}**：{text}")
        screenplay += [f"动作完成点：{beat['action']}（完成后保留反应）", f"切镜理由：{beat['cut']}", ""]
    screenplay += ["## 台词验收", "系统台词保持短、冷、带边界；林照每句都在做选择或追问，不念说明书。系统从触发、任务、限制到回执改变她一次关键决策：先保全原件，再走正式核验。"]
    (OUT / "screenplay.md").write_text("\n".join(screenplay) + "\n", encoding="utf-8")
    write_json(OUT / "asset_gate_preflight.json", {"status": "READY", "asset_registry": "asset_registry.json", "continuity_edges": len(shot_rows) - 1, "provider_calls": 0, "run_created": False})
    print(json.dumps({"status": "ASSETS_READY", "project_dir": str(OUT), "plan": str(OUT / "episode_plan.json"), "screenplay": str(OUT / "screenplay.md"), "assets": len(records), "shots": len(shot_rows), "continuity_edges": len(shot_rows) - 1}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
