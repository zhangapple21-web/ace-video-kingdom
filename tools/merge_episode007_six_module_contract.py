"""Build the formal research shot contract from the current episode and measurements.

The generated file is a sidecar for the existing episode contract.  It keeps
the episode in ``FREE_ZONE_RESEARCH_ONLY`` while making the six production
modules executable by the existing preflight boundary.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DIALOGUE_SHOTS = {"S01C", "S02B", "S03A", "S04A", "S05A", "S06A"}
ANCHORS = {
    "S01A": "../media_staging/episode_007_virtual_data/anchors/scene_action/office_keyboard.png",
    "S01B": "../media_staging/episode_007_virtual_data/anchors/scene_action/office_keyboard.png",
    "S01C": "../media_staging/episode_007_virtual_data/anchors/scene_action/office_keyboard.png",
    "S01D": "../media_staging/episode_007_virtual_data/anchors/scene_action/office_phone_impact.png",
    "S02A": "../media_staging/episode_007_virtual_data/anchors/scene_action/manager_desk_impact.png",
    "S02B": "../media_staging/episode_007_virtual_data/anchors/scene_action/manager_desk_impact.png",
    "S02C": "../media_staging/episode_007_virtual_data/anchors/scene_action/manager_desk_impact.png",
    "S03A": "../media_staging/episode_007_virtual_data/anchors/scene_action/manager_desk_impact.png",
    "S03B": "../media_staging/episode_007_virtual_data/anchors/scene_action/manager_desk_impact.png",
    "S03C": "../media_staging/episode_007_virtual_data/anchors/scene_action/office_keyboard.png",
    "S04A": "../media_staging/episode_007_virtual_data/anchors/scene_action/office_keyboard.png",
    "S04B": "../media_staging/episode_007_virtual_data/anchors/scene_action/office_phone_impact.png",
    "S05A": "../media_staging/episode_007_virtual_data/anchors/scene_action/office_keyboard.png",
    "S05B": "../media_staging/episode_007_virtual_data/anchors/scene_action/office_phone_impact.png",
    "S05C": "../media_staging/episode_007_virtual_data/anchors/scene_action/office_phone_impact.png",
    "S06A": "../media_staging/episode_007_virtual_data/anchors/scene_action/manager_desk_impact.png",
    "S06B": "../media_staging/episode_007_virtual_data/anchors/scene_action/office_keyboard.png",
    "S07A": "../media_staging/episode_007_virtual_data/anchors/scene_action/night_copy_pullback.png",
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _scene_id(shot_id: str) -> str:
    return shot_id[:3]


def _beats(scene: str, shot_type: str) -> list[str]:
    text = scene.strip()
    if shot_type == "dialogue":
        return [
            f"准备：人物稳定在场景中，呼吸/视线建立对白起点（{text}）",
            f"动作：完整说出台词并完成对应目光或手部动作（{text}）",
            "回收：说完后保留一拍，人物状态落定，再切镜",
        ]
    return [
        f"准备：道具与身体位置先建立（{text}）",
        f"动作：完成一个可辨认的主要动作或冲击（{text}）",
        "回收：保留惯性、反应或环境余波，动作完成后再切镜",
    ]


def build(episode_path: Path, measured_path: Path) -> dict[str, Any]:
    episode = _load(episode_path)
    measured = _load(measured_path)
    measured_by_id = {str(item.get("shot_id")): item for item in measured.get("shots", []) if isinstance(item, dict)}
    shots: list[dict[str, Any]] = []
    for source in episode.get("shots", []):
        shot_id = str(source.get("shot_id"))
        measurement = measured_by_id.get(shot_id, {})
        script = measurement.get("script", {}) if isinstance(measurement.get("script"), dict) else {}
        shot_type = "dialogue" if shot_id in DIALOGUE_SHOTS else "action"
        tts = script.get("tts_duration_seconds")
        duration = round(max(2.5, min(18.0, float(tts or 0) + 0.6)), 3)
        scene = str(source.get("scene", "")).strip()
        identity = str((source.get("render") or {}).get("fallback_image", ""))
        if not identity:
            identity = "../media_staging/episode_007_virtual_data/anchors/alang_character_anchor.png"
        movement = "FIXED_DIALOGUE" if shot_type == "dialogue" else ("ONE_PURPOSEFUL_MOVE" if source.get("continuous_action") else "FIXED_ACTION_FRAME")
        camera = {
            "shot_type": shot_type,
            "scale": "medium close-up" if shot_type == "dialogue" else "medium shot",
            "movement": movement,
            "axis": "screen-left facing screen-right",
            "first_frame_kind": "scene_action_anchor",
            "movement_count": 0 if shot_type == "dialogue" else (1 if source.get("continuous_action") else 0),
        }
        emotion = {"S01": "irritation", "S02": "pressure", "S03": "collapse", "S04": "hope", "S05": "hope", "S06": "collapse", "S07": "numbness"}.get(_scene_id(shot_id), "pressure")
        shots.append({
            "shot_id": shot_id,
            "source_scene": scene,
            "source_prompt": source.get("prompt", ""),
            "anchor_reuse_allowed": True,
            "script": {
                "scene_id": _scene_id(shot_id),
                "speaker": script.get("speaker", "UNKNOWN"),
                "dialogue_text": script.get("dialogue_text", "UNKNOWN"),
                "emotion": emotion,
                "line_locked": True,
                "tts_duration_seconds": tts,
                "audio_status": "MEASURED" if isinstance(tts, (int, float)) else "AUDIO_PENDING",
            },
            "camera": camera,
            "edit": {
                "duration_seconds": duration,
                "cut_after_performance": True,
                "transition_reason": "cut only after the line/action and recovery beat complete",
                "rhythm_phase": emotion,
            },
            "performance": {
                "emotion_goal": f"{emotion}: the character state must visibly change within the shot",
                "action_beats": _beats(scene, shot_type),
                "sound_cues": ["dialogue or room tone", "keyboard/phone/desk foley as applicable"],
            },
            "assets": {
                "identity_reference": identity,
                "scene_action_anchor": ANCHORS[shot_id],
                "costume": "episode identity invariant",
                "props": ["keyboard", "phone", "green chat windows", "desk or smoke haze"],
                "lighting": "dirty cool fluorescent plus green monitor spill",
            },
            "recovery": {
                "max_attempts": 2,
                "retry_delay_policy": "Retry-After first; otherwise >=60s provider cooldown",
                "degrade_order": ["retry with a small seed offset", "manual replacement marker retaining failure evidence"],
            },
        })
    return {
        "contract_version": "video_kingdom.six_module_shot_contract.research.v3",
        "production_boundary": "RESEARCH_ONLY",
        "source_episode": str(episode_path.name),
        "project_id": episode.get("project_id"),
        "quality_mode": "FORMAL",
        "premise": "在虚假数据驱动的封闭办公室里，阿浪逐步看见‘出单’和‘工资’都可能是同一套控制幻觉。",
        "causal_chain": ["假粉刷屏", "管理层加码", "同事困境", "到账幻觉", "冻结退回", "等待工资的真相", "机械化回归"],
        "plants": ["绿色聊天窗口", "护照/工资威胁", "男同事母亲住院", "假到账提示"],
        "payoffs": ["到账提示反转为冻结", "日报替代理由", "人被当作最廉价的数据单元"],
        "viewer_knowledge_checkpoints": ["观众先知道刷屏可能是机器人", "观众与阿浪同时看到到账反转", "结尾确认等待本身就是控制"],
        "anchor_reuse_policy": "允许同一场景动作锚在不同镜头复用，但每镜必须有不同的动作弧、台词/信息增量和切镜理由；肖像不得代替动作锚。",
        "shots": shots,
        "evidence": {
            "measured_contract": str(measured_path.name),
            "scene_action_anchor_root": "../media_staging/episode_007_virtual_data/anchors/scene_action",
            "audio_rule": "measured TTS duration is authoritative for research timing; provider audio remains separately verified",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--measured", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = build(args.episode.resolve(), args.measured.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "WRITTEN", "output": str(args.output), "shots": len(value["shots"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
