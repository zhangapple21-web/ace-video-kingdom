"""Rebuild the episode-001 shot contracts around identity/scene/shot state.

This is intentionally a migration tool: it backs up the old canonical shot
pack, rewrites only the main SHOT_*.json contracts, and marks them
REWORK_REQUIRED until fresh dual-review receipts and frame QC exist.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"D:\视频创作\projects\张铁铁的沙雕日常\张铁铁的沙雕日常\项目文件\EP01_EP01_20260918T171515Z_CONTRACTS")

PLANS = {
    "SHOT_035B_WENJI_IMAGINE": {"scene": "傍晚南宁街头与奔驰电动车内，暖色街灯掠过车窗", "action": "文姬握住车把向前看，笑着想象到南宁接人；镜头从侧前方轻跟随，车内光影连续变化", "emotion": "兴奋、期待", "camera": "侧前方中景轻跟随，随着车辆前进产生可见街灯流动"},
    "SHOT_035C_ZHANG": {"scene": "老张自己的夜间工作室，木桌与台灯，独立空间", "action": "老张放下手机，挑眉侧身靠回椅背，带笑反问后看向桌面，尾部保留短暂停顿", "emotion": "调侃、得意", "camera": "中景缓慢向近景收，落在挑眉和靠回椅背的反应"},
    "SHOT_07A_ZHANG": {"scene": "老张夜间工作室，电脑和桌面卡片清晰可见", "action": "老张把写有账号信息的卡片推到电脑旁，抬眼确认，手指点一下桌面后等待回应", "emotion": "务实、安排工作", "camera": "中景小幅横移跟随卡片落桌，再回到老张表情"},
    "SHOT_07B_WENJI": {"scene": "文姬自己的室内工作位，清晨偏亮自然光", "action": "文姬从困倦伏案抬头，听到有班后眼神变亮，坐直并卷起袖口，身体前倾说干", "emotion": "从困倦到兴奋", "camera": "中景固定起拍，随坐直动作轻推近"},
    "SHOT_07B_WENJI_RETOUCH": {"scene": "文姬明亮的工作位，电脑和鼠标在桌面，屏幕内容不可见", "action": "文姬把一张照片转向自己查看，眼睛发亮，手指快速滑动并抬头笑着展示成果", "emotion": "兴致勃勃、得意", "camera": "中景跟手部动作微移，最后落在她抬头的笑"},
    "SHOT_07B_ZHANG_RETOUCH": {"scene": "老张夜间工作室，听到文姬展示成果", "action": "老张端起茶杯看向镜头外，先无奈再宠溺地笑，轻轻摇头后抿一口茶", "emotion": "无奈、宠溺", "camera": "近景从茶杯抬到眼神，停在笑意上"},
}


def concrete_scene(old: dict) -> dict:
    scene = str(old.get("scene") or "").strip()
    return {"location": scene or "角色独立工作空间", "time": "本镜剧本规定时段", "lighting": "由场景动机决定的连续光线", "space": "角色所在独立空间，按本镜动作允许移动", "physical_layout": "地面、桌椅和前后景形成可进入的真实布局", "interaction_surface": "本镜人物实际接触的桌面、座椅或道具承托面", "scene_mode": "LIVE_DIEGETIC_SPACE"}


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = ROOT / f".pre_rework_{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    manifest = {"schema": "video_kingdom.episode_contract_rework.v1", "created_at": stamp, "status": "REWORK_REQUIRED", "shots": []}
    for path in sorted(ROOT.glob("SHOT_*.json")):
        if any(x in path.name for x in ("RECEIPT", "SCRIPT_PROMPT", "FIVE_GATE")):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        shutil.copy2(path, backup / path.name)
        shot_key = path.stem
        plan = PLANS.get(shot_key)
        data["status"] = "REWORK_REQUIRED"
        data["generation_allowed"] = False
        data["rebuild_required"] = True
        data["rework_reason"] = "旧合同把身份参考/贴耳模板当成构图，缺少真实场景与可见表演；须按 Identity + Scene State + Shot State 重新双审。"
        data["state_contract"]["scene_state"] = concrete_scene(data)
        shot = data["state_contract"]["shot_state"]
        shot["start_pose"] = shot.get("start_pose") or "从可见动作前的明确姿态开始"
        shot["primary_action"] = (plan or {}).get("action") or data.get("action") or "完成剧本规定的可见身体、手部和表情动作"
        shot["emotion_start_end"] = (plan or {}).get("emotion") or data.get("emotion") or "按剧本完成情绪变化并留下尾部反应"
        shot["camera"] = (plan or {}).get("camera") or "中景承载完整动作，按信息落点做有动机的近景变化"
        shot["end_state"] = "动作完成后的明确反应姿态，保留可剪辑尾帧"
        if plan:
            data["scene"] = plan["scene"]
            data["visual_action"] = plan["action"]
            data["emotion"] = plan["emotion"]
            data["action"] = plan["action"]
            data["shot_prompt"]["scene_lock"] = plan["scene"]
            data["shot_prompt"]["txt_prompt_elements"]["environment"] = plan["scene"]
            data["shot_prompt"]["txt_prompt_elements"]["action"] = plan["action"]
            data["shot_prompt"]["txt_prompt_elements"]["camera"] = plan["camera"]
            data["shot_prompt"]["compiled_prompt"] = f"主体身份锁定；场景：{plan['scene']}；可见动作：{plan['action']}；镜头：{plan['camera']}；禁止静态口播、重复帧、画中画和手机界面。"
            if shot_key == "SHOT_035B_WENJI_IMAGINE":
                data["composition_reference"] = "待 imagegen 审验通过的傍晚南宁街头/奔驰电动车构图静帧"
        data["render"]["provider_submission"] = "NOT_PERFORMED"
        data["rework_hash"] = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest["shots"].append({"shot_id": data.get("shot_id"), "file": path.name, "status": "REWORK_REQUIRED", "rework_hash": data["rework_hash"]})
    (ROOT / f"EP01_CONTRACT_REWORK_MANIFEST_{stamp}.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "REWORK_REQUIRED", "shots": len(manifest["shots"]), "backup": str(backup), "manifest": str(ROOT / f"EP01_CONTRACT_REWORK_MANIFEST_{stamp}.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
