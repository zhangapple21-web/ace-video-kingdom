"""Compile the locked human-dialogue screenplay and reference-gated asset pack.

This compiler is intentionally asset-first: it writes the story, visual bible,
character dossier, shot contracts and continuity bridges, but it never creates
a production Run or submits a Provider request.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "episodes" / "generated" / "reverse_system_human_20260907"
OUT = ROOT / "episodes" / "generated" / "reverse_system_human_v3_20260907"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists():
        raise SystemExit(f"refusing to overwrite existing package: {OUT}")
    (OUT / "assets").mkdir(parents=True)
    (OUT / "continuity").mkdir()

    story = {
        "title": "《逆时针证词》第一集：这班是一天也上不下去了",
        "logline": "维修师林照在旧车票上触发逆向证据系统；它不替她下结论，只逼她先留住原件，再把矛盾交给正式核验。",
        "source_class": "ORIGINAL_USER_BRIEF",
        "fiction_boundary": "临潮车站、人物和事件均为原创虚构，不对应现实机构或案件。",
        "system_causal_event": [
            "铜色筹码接触旧票时触发系统，打断林照准备销毁票根的动作。",
            "系统给出九十秒任务：找出一条能被第三方核验的矛盾。",
            "系统明确区分已观察、待核验和高风险推断，改变林照先保全原件再报失的决定。",
        ],
        "ethics": ["不展示入侵、伪造或规避执法步骤", "证据走正式报失和第三方核验", "不把受困处境猎奇化"],
    }
    write_json(OUT / "story_root.json", story)

    visual_bible = {
        "schema": "video_kingdom.visual_bible.v1",
        "aspect_ratio": "9:16",
        "style_block": "写实电影感、冷蓝旧车站维修间、低饱和、自然皮肤纹理、固定轴线、铜色脉冲作为唯一超现实光源",
        "invariants": [
            "林照：24-26岁女性，黑色微卷长发低马尾/半扎，几缕碎发，偏瘦，眉眼锋利",
            "深青/墨绿色略宽工装外套，米白或浅灰松领衬衫，黑绳或细手链",
            "铜色筹码在右手或桌面右侧；旧车票始终为同一张；系统只显示抽象环形光，不出现可读文字",
        ],
        "negative": ["男性化脸孔", "短发", "浓妆", "现实品牌/机构标识", "新增可见人物", "超能力开锁", "可读系统文字"],
    }
    write_json(OUT / "visual_bible.json", visual_bible)

    source_assets = {
        "CHAR_LINZHAO_V3": (SOURCE / "assets" / "CHAR_LINZHAO_V2.png", "character"),
        "SCN_TIDE_STATION_DESK_V3": (SOURCE / "assets" / "SCN_TIDE_STATION_DESK_V2.png", "scene"),
        "PROP_REVERSED_TICKET_V3": (SOURCE / "assets" / "PROP_REVERSED_TICKET_V2.png", "prop"),
        "PROP_COPPER_TOKEN_V3": (SOURCE / "assets" / "PROP_COPPER_TOKEN_V2.png", "prop"),
    }
    records = []
    for asset_id, (src, asset_type) in source_assets.items():
        dst = OUT / "assets" / f"{asset_id}.png"
        shutil.copy2(src, dst)
        records.append({
            "asset_id": asset_id,
            "asset_type": asset_type,
            "source_path": f"assets/{dst.name}",
            "sha256": sha256(dst),
            "bytes": dst.stat().st_size,
            "usage": "video_asset",
            "rights_status": "ORIGINAL_SYNTHETIC_ANCHOR",
            "local_state": "HASH_VERIFIED",
            "provider_state": "PENDING_PUBLIC_URL_READ_PROBE",
        })
    write_json(OUT / "asset_registry.json", {"schema": "video_kingdom.asset_registry.v1", "status": "CONDITIONAL", "records": records})

    dossier = {
        "schema": "video_kingdom.character_dossier.v2",
        "character_id": "CHAR_LINZHAO_V3",
        "name": "林照",
        "age_range": "24-26",
        "occupation": "临潮车站维修间修复师（打杂+修东西的底层员工）",
        "identity_lock": {
            "face": "清冷里带锋利，眉眼偏利，冷淡或不耐烦；冷笑时好看但不柔媚",
            "hair": "黑色微卷长发，低马尾或半扎，脸颊有碎发",
            "body": "偏瘦，肩线干净，工装不显臃肿",
            "wardrobe": ["深青/墨绿色略宽工装外套", "米白或浅灰松领衬衫", "黑绳或细手链"],
            "performance": ["日常爱翻白眼、阴阳怪气、能摸鱼绝不多做", "真正遇到证据时突然安静，手很稳", "反转由吊儿郎当切到低声严肃"],
        },
        "visual_reference_requirements": ["front", "left_three_quarter", "right_profile", "working_waist_up", "same_identity_across_views"],
        "provider_reference_policy": "本地哈希不等于 Provider 已读；必须保存公开 URL、GET 200、image/*、字节哈希一致和 Provider admission receipt。",
    }
    write_json(OUT / "assets" / "CHAR_LINZHAO_V3.dossier.json", dossier)

    beats = [
        {
            "shot_id": "S01", "time": "0-12秒", "title": "打工人的日常崩溃",
            "action": "林照打着哈欠，把铜色筹码啪地扣在旧车票上；脉冲亮起，她的手停住。",
            "visual": "旧车票、筹码和林照不耐烦的半张脸同框，脉冲只闪一圈。",
            "dialogue": [("系统", "逆向证据系统，启动。"), ("林照", "又来？查个破车票，你至于亮成这样吗？")],
            "sound": "筹码落桌，短促脉冲，远处换班铃",
            "cut": "脉冲打断销毁动作，切入票面矛盾",
        },
        {
            "shot_id": "S02", "time": "12-25秒", "title": "人工智障发言",
            "action": "林照把票根翻过来，日期与登记记录错开；她用指腹压住缺口。",
            "visual": "两份记录不对齐，环形光停在断掉的时间戳位置。",
            "dialogue": [("系统", "已看到：日期冲突。还不能叫真相。"), ("林照", "差几分钟怎么了？我每天迟到半小时，宇宙也没塌。"), ("系统", "待核验：时间戳缺口。"), ("林照", "行，别吵。保存，下班。")],
            "sound": "纸张摩擦，内网电流声，保存键轻响",
            "cut": "缺口变成可查线索，切入流程压力",
        },
        {
            "shot_id": "S03", "time": "25-37秒", "title": "上有政策下有对策",
            "action": "值班喇叭催她销毁旧票；林照把票根塞进信封，封口时停一下。",
            "visual": "销毁盒半开，票根没有进去；林照边封信封边翻白眼。",
            "dialogue": [("值班声", "林照，按流程处理。旧票不能留。"), ("林照", "知道了。你们的流程，我先按字面来。"), ("系统", "高风险推断：规则可能被误用。证据不足。"), ("林照", "听见没？人工智障都让你别急。")],
            "sound": "喇叭失真，信封封口声，金属盒轻响",
            "cut": "她选择保全原件，切入正式报失",
        },
        {
            "shot_id": "S04", "time": "37-45秒", "title": "反转",
            "action": "林照把信封放进正式报失盒，回执灯亮；她背包转身，余光看见信封边缘渗出暗色，猛地停住。",
            "visual": "回执灯从暗到亮，暗色沿信封边缘慢慢出现；表情从嫌弃变僵住。",
            "dialogue": [("系统", "证据已进入正式渠道。等待第三方核验。"), ("林照", "行，这次走官方流程。烂摊子甩给上面，这叫合理摸鱼。"), ("林照", "……等等。")],
            "sound": "回执单声，背包拉链，环境声突然抽空",
            "cut": "定格她发现暗色的瞬间，片尾钩子",
        },
    ]
    shots = []
    asset_ids = [row["asset_id"] for row in records]
    for beat in beats:
        start, end = [int(x.replace("秒", "")) for x in beat["time"].split("-")]
        prompt = "写实电影感竖屏短镜头，原创虚构临潮车站维修间。林照是24-26岁女性，黑色微卷长发低马尾，深青工装外套、米白松领衬衫、黑绳手链；保持同一张脸、同一服装、同一固定轴线。" + beat["action"] + beat["visual"] + "单一主动作，动作完成后保留反应，不切镜，不新增可见人物，不出现可读文字、logo或现实机构标识。"
        shots.append({
            "shot_id": beat["shot_id"], "time_range": beat["time"], "title": beat["title"], "action": beat["action"],
            "first_state": "动作尚未完成", "last_state": "动作完成并留下表情反应", "dramatic_function": beat["visual"],
            "dialogue": [{"speaker": s, "text": t} for s, t in beat["dialogue"]], "sound": beat["sound"], "cut_reason": beat["cut"],
            "required_asset_ids": asset_ids, "provider_mode": "reference", "reference_assets": [],
            "shot_contract": {"single_action": True, "max_primary_actions": 1, "internal_cuts_allowed": 0, "duration_seconds": {"min": end-start, "max": end-start}},
            "camera": {"framing": "medium_close_vertical", "movement": "NONE", "axis": "locked_station_desk_axis"},
            "render": {"model": "agnes-video-2.5-flash", "flash_mode": "reference", "seconds": min(12, max(4, end-start)), "aspect_ratio": "9:16", "size": "720P"},
            "prompt": prompt,
        })
    for current, following in zip(shots, shots[1:]):
        bridge = {"schema": "video_kingdom.continuity_bridge.v1", "status": "READY", "from_shot": current["shot_id"], "to_shot": following["shot_id"], "previous_end_state": current["last_state"], "next_initial_state": following["first_state"], "invariants": visual_bible["invariants"], "asset_ids": asset_ids, "post_generation_frame_proof": "PENDING"}
        path = OUT / "continuity" / f"{current['shot_id']}_to_{following['shot_id']}.json"
        write_json(path, bridge)

    plan = {"schema": "video_kingdom.episode_plan.asset_first.v2", "project_id": "reverse-system-human-v3-20260907", "status": "ASSETS_CONDITIONAL", "production_integration": False, "story": story, "visual_bible": visual_bible, "character_dossier": "assets/CHAR_LINZHAO_V3.dossier.json", "assets": [{"asset_id": row["asset_id"], "path": row["source_path"], "sha256": row["sha256"], "provider_url": None} for row in records], "shots": shots, "gates": {"local_hash_gate": "PASS", "provider_reference_gate": "PENDING", "formal_run_allowed": False, "reason": "Provider must confirm it can GET each public reference URL and preserve the same asset hash before Run creation."}}
    write_json(OUT / "episode_plan.json", plan)

    screenplay = ["# 《逆时针证词》第一集：这班是一天也上不下去了", "", "45秒竖屏 AI 短剧｜原创虚构｜人话对白锁定版", "", "## 角色", "- **林照**：24–26岁，车站维修间修复师。清冷、锋利、嫌麻烦，但手很稳。", "- **逆向证据系统**：只把矛盾排成可核验顺序，不替人下结论。", "- **值班声**：只通过喇叭出现的流程压力。", ""]
    for beat in beats:
        screenplay += [f"## {beat['shot_id']}｜{beat['time']}｜{beat['title']}", f"画面：{beat['action']}", f"视觉单元：{beat['visual']}", f"声音：{beat['sound']}", ""]
        for speaker, text in beat["dialogue"]:
            screenplay.append(f"**{speaker}**：{text}")
        screenplay += [f"动作完成点：{beat['action']}", f"切镜理由：{beat['cut']}", ""]
    screenplay += ["## 台词验收", "林照不念系统说明书：她每句话都在嫌麻烦、顶流程或做决定。系统只说短句，并明确‘还不能叫真相’和‘证据不足’。系统真正改变剧情：林照放弃追传闻，先保全原件并报失。", ""]
    (OUT / "screenplay.md").write_text("\n".join(screenplay), encoding="utf-8")
    write_json(OUT / "asset_gate_preflight.json", {"status": "CONDITIONAL", "local_hashes": len(records), "provider_reference_reads": 0, "continuity_edges": len(shots)-1, "run_created": False})
    print(json.dumps({"status": "ASSETS_CONDITIONAL", "project_dir": str(OUT), "screenplay": str(OUT / "screenplay.md"), "plan": str(OUT / "episode_plan.json"), "assets": len(records), "shots": len(shots)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
