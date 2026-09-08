"""Rewrite a compiled six-shot plan into the originalized Chinese-aesthetic snow-breath pilot."""
from __future__ import annotations

import json
from pathlib import Path
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: build_longshe_snow_plan.py PROJECT_DIR")
        return 2
    root = Path(sys.argv[1]).resolve()
    plan_path = root / "episode_plan.json"
    contract_path = root / "six_module_contract.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    idea = "原创化《雪晨里的那一口白气》：普通高中生清晨在中国北方城市公园抄近路，看到中国成年女性在松林雪地练习慢进快收的身法；少年模仿吐气失败，女子吐出一口短暂笔直白气，只说先看脚下便离开，雪地留下第三串陌生脚印。"
    # Keep spoken lines out of movement clips.  This prevents the provider
    # from compressing dialogue and a second physical beat into one shot.
    dialogue = [
        "这人一大早，在练什么？",
        "脚下先稳，呼吸才不会散。",
        "",
        "",
        "",
        "那第三串脚印是谁的？",
    ]
    actions = [
        "少年踏雪进入松林并停步抬头",
        "女子站定保持伸掌姿势并自然呼吸一次",
        "少年从树后探头",
        "女子五指收拢后定势",
        "女子自然吐出一口白气",
        "少年低头看向已经存在的第三串陌生脚印",
    ]
    titles = ["雪晨入林", "慢掌收势", "少年偷学", "五指定势", "笔直白气", "第三串脚印"]
    information = [
        "少年第一次看见松林里的陌生练习者",
        "女子的呼吸与站姿显出克制和稳定",
        "少年确认自己正在被某种身法吸引",
        "女子的手势留下无法解释的异常",
        "白气在静止画面里形成短暂悬念",
        "第三串脚印把相遇变成追踪线索",
    ]
    prompts = [
        "中国北方城市公园冬晨，真实东亚高中男生穿深色校服背旧书包，踏雪进入深绿松林后停步抬头，结霜木栈道和远处居民楼虚化，冷青灰与土褐低饱和，东方留白，写实中文短剧摄影，竖屏9:16，单一动作，固定身份，不切镜，无欧美脸、无西部片、无动漫赛博光效。",
        "中国北方城市公园冬晨，真实东亚成年女性穿米白无品牌运动服、低马尾、白软底鞋，在积雪松林中站定保持伸掌姿势，只做一次自然呼吸，冷青灰、深绿、土褐，克制写实，竖屏9:16，静态一镜到底，禁止第二动作和转场。",
        "中国北方城市公园冬晨，深色校服高中男生藏在松树后，只从树干边探头一次，米白运动服女子保持远处静止姿势，真实东亚人物，竖屏9:16，固定中近景，禁止吐气、走动、改景或切镜。",
        "中国成年女性在中国松林雪地，米白无品牌运动服，双手保持原位，只做一次五指收拢并定势，近景看手与重心，冷青灰冬晨、深绿松针、雪地留白，竖屏9:16，固定机位，禁止连招和特效。",
        "中国成年女性在北方城市公园雪地保持半身静止，只完成一次自然呼气，嘴前出现普通寒冷天气的淡白雾气后散开，米白运动服、低马尾、东亚面部，竖屏9:16，静态一镜到底，禁止手势变化、光束、符文和转场。",
        "冬晨中国城市公园松林，画面中只有深色校服高中男生和雪地脚印，少年保持站立，只低头看向已经存在的第三串陌生脚印，远处松林与居民楼虚化，禁止任何第二人物、走入、离开、追逐、回头、改景和内部切镜，竖屏9:16，固定中远景。",
    ]
    for i, shot in enumerate(plan["shots"]):
        shot_id = f"S{i+1:02d}A"
        shot.update({
            "scene_id": f"SC{i+1:02d}",
            "prompt": prompts[i],
            "action": actions[i],
            "action_beats": [f"首态：{titles[i]}前的稳定构图", f"动作：{actions[i]}", "末态：动作完成后保留至少0.6秒反应留白"],
            "first_state": f"{titles[i]}前的稳定构图与角色身份",
            "last_state": "动作完成后保留至少0.6秒反应留白",
            "dramatic_function": titles[i],
            "information_gain": information[i],
            "emotion_change": "由好奇走向谨慎，再留下追踪悬念",
            "camera": {"shot_type": "dialogue" if i in (0, 1, 5) else "action", "scale": "medium close-up", "movement": "FIXED_DIALOGUE" if i in (0, 1, 5) else "ONE_PURPOSEFUL_MOVE", "axis": "screen-left facing screen-right", "movement_count": 0 if i in (0, 1, 5) else 1},
            "shot_contract": {"version": "ace.video_kingdom.single_action_shot_contract.v1", "single_action": True, "action_unit": actions[i], "max_primary_actions": 1, "internal_cuts_allowed": 0, "cut_policy": "cut only after action completion and recovery hold"},
        })
        side = contract["shots"][i]
        is_girl = i in (1, 3, 4)
        speaker = "CHAR_COUNTER" if is_girl else "CHAR_MAIN"
        identity = "assets/char_counter_reference.png" if is_girl else "assets/char_main_reference.png"
        audio_status = "AUDIO_PENDING" if dialogue[i] else "NO_DIALOGUE"
        sound_cues = ["dialogue", "snow footsteps", "cloth and breath"] if dialogue[i] else ["snow footsteps", "cloth and breath"]
        side.update({"shot_id": shot_id, "source_scene": f"{titles[i]}：{actions[i]}", "script": {"scene_id": f"SC{i+1:02d}", "speaker": speaker, "dialogue_text": dialogue[i], "emotion": "curious" if i < 3 else "restrained", "line_locked": True, "tts_duration_seconds": None, "audio_status": audio_status}, "camera": shot["camera"] | {"first_frame_kind": "scene_action_anchor"}, "edit": {"duration_seconds": None, "render_seconds": 6, "duration_source": "PENDING_TTS", "cut_after_performance": True, "transition_reason": "cut after single action and recovery hold"}, "performance": {"emotion_goal": shot.get("emotion_change", "克制悬念"), "action_beats": shot["action_beats"], "sound_cues": sound_cues}, "shot_contract": shot["shot_contract"], "assets": {"identity_reference": identity, "scene_action_anchor": f"assets/sc{i+1:02d}_anchor.png", "costume": "少年固定深色校服与旧书包；女子固定米白无品牌运动服、低马尾、白软底鞋", "props": ["snow-covered pine ground", "frosted path"], "lighting": "cold blue-grey winter dawn with natural skin tone", "space": "Chinese northern city park pine grove"}})
    plan.update({"title": "《雪晨里的那一口白气》", "source_rights_note": "仅吸收本地小说库《龙蛇演义》开篇的观察/模仿机制；不复用姓名、地名、原句或拳法专名，仅内部研究。", "story": {"root_brief": {"theme": "观察、模仿与未知线索", "relationship_and_conflict": "普通少年与隐藏能力者的短暂相遇", "mainline_events": titles, "source_rights_note": "originalized_mechanism_only", "semantic_anchor_type": "snow_breath_and_footprints"}, "scene_nodes": [{"scene_id": f"SC{i+1:02d}", "title": titles[i]} for i in range(6)]}})
    contract.update({"premise": idea, "causal_chain": titles, "plants": ["女子的身法", "第三串脚印"], "payoffs": ["笔直白气", "留下追踪钩子"], "viewer_knowledge_checkpoints": ["观众看到少年观察", "观众看到模仿失败与白气异常", "观众发现第三串脚印"], "timing_policy": "tts_first; measured dialogue plus 0.6s recovery hold; no character-count timing"})
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"project": str(root), "shots": 6, "title": plan["title"], "status": "CUSTOM_PLAN_WRITTEN"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
