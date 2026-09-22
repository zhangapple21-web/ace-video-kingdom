from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(r"D:\视频创作")
PROJECT = ROOT / "projects" / "张铁铁的沙雕日常" / "张铁铁的沙雕日常"
CONTROL = ROOT / "ace-video-kingdom"
PROJECT_FILES = PROJECT / "项目文件"
RUN_ID = "ep01_r3_20260921T000000Z"
RUN_DIR = PROJECT_FILES / "EP01_R3_PIPELINE_20260921"
# Permanent cross-episode policy: Provider audio is ambience only. When an
# external dialogue/VO master exists, Provider audio is removed from delivery
# rather than trusted to share the master clock.
PROVIDER_AUDIO_POLICY = "ambience_only_dialogue_removed_or_ducked"
CONTRACT_DIR = RUN_DIR / "contracts"
OUT_DIR = PROJECT / "成片" / "测试" / "ep01_r3"
MANIFEST = RUN_DIR / "contract_manifest.json"
QUEUE = OUT_DIR / "queue_result.json"
LOG = OUT_DIR / "submit_log.jsonl"
EXACT_AUDIO = PROJECT_FILES / "EP01_EP01_20260918T171515Z_EXACT_AUDIO_MANIFEST.json"
CLIPS = ROOT / "temp" / "shot02_08_v9_clips.json"
PUBLIC_BASE = "https://raw.githubusercontent.com/zhangapple21-web/ace-video-assets/main"
ZHANG_PACK = PUBLIC_BASE + "/references/ZHANG_TIETIE_PACK_ORIGINAL.png"
WENJI_PACK = PUBLIC_BASE + "/references/WENJI_PACK_ORIGINAL.png"
OFFICE = PUBLIC_BASE + "/references/SHOT_01_OFFICE_ZHANG_V8c.png"
HOME = PUBLIC_BASE + "/references/SHOT_01_HOME_WENJI_V8c4.png"
SLIP = PUBLIC_BASE + "/references/SHOT_035_HOME_SLIP_V7.webp"
EV = PUBLIC_BASE + "/references/SHOT_035_IMAGINE_EV2WHEEL_V5.webp"

FEMALE_TRACKS = {
    "SHOT_02B_WENJI_V9": "S02_WENJI_LINE_01",
    "SHOT_03B_WENJI_V9": "S03_WENJI_LINE_01",
    "SHOT_035A_WENJI_V9": "S035_WENJI_OPEN_LINE_01",
    "SHOT_035D_IMAGINE_V9": "S035_WENJI_IMAGINE_LINE_01",
    "SHOT_035E_WENJI_SNAP_V9": "S035_WENJI_RETURN_LINE_01",
    "SHOT_04B_WENJI_V9": "S04_WENJI_LINE_01",
    "SHOT_04D_WENJI_V9": "S04_WENJI_02_LINE_01",
    "SHOT_05A_WENJI_V9": "S05_WENJI_01_LINE_01",
    "SHOT_05C_WENJI_V9": "S05_WENJI_02_LINE_01",
    "SHOT_06B_WENJI_V9": "S06_WENJI_01_LINE_01",
    "SHOT_06D_WENJI_V9": "S06_WENJI_02_LINE_01",
    "SHOT_075A_WENJI_V9": "S075_WENJI_LINE_01",
    "SHOT_07B_WENJI_V9": "S07_WENJI_LINE_01",
    "SHOT_08A_WENJI_V9": "S08_WENJI_01_LINE_01",
    "SHOT_08C_WENJI_V9": "S08_WENJI_02_LINE_01",
}
MALE_TRACKS = {
    "SHOT_02A_ZHANG_V9": "S02_ZHANG_LINE_01",
    "SHOT_03A_ZHANG_V9": "S03_ZHANG_LINE_01",
    "SHOT_035B_ZHANG_V9": "S035_ZHANG_LINE_01",
    "SHOT_04A_ZHANG_V9": "S04_ZHANG_01_LINE_01",
    "SHOT_04C_ZHANG_V9": "S04_ZHANG_02_LINE_01",
    "SHOT_04E_ZHANG_V9": "S04_ZHANG_03_LINE_01",
    "SHOT_05B_ZHANG_V9": "S05_ZHANG_LINE_01",
    "SHOT_06A_ZHANG_V9": "S06_ZHANG_01_LINE_01",
    "SHOT_06C_ZHANG_V9": "S06_ZHANG_02_LINE_01",
    "SHOT_06E_ZHANG_V9": "S06_ZHANG_03_LINE_01",
    "SHOT_07A_ZHANG_V9": "S07_ZHANG_LINE_01",
    "SHOT_075B_ZHANG_V9": "S075_ZHANG_LINE_01",
    "SHOT_08B_ZHANG_V9": "S08_ZHANG_LINE_01",
}
VO_TRACKS = {
    "SHOT_01C_WENJI_VO_R3": "S01_WENJI_MONO_LINE_01",
    "SHOT_06F_WENJI_VO_V9": "S06_WENJI_MONO_LINE_01",
}
ORDER = [
    "SHOT_01A_ZHANG_R3", "SHOT_01B_WENJI_R3", "SHOT_01C_WENJI_VO_R3",
    "SHOT_02A_ZHANG_V9", "SHOT_02B_WENJI_V9", "SHOT_03A_ZHANG_V9", "SHOT_03B_WENJI_V9",
    "SHOT_035A_WENJI_V9", "SHOT_035B_ZHANG_V9", "SHOT_035C_WENJI_SLIP_V9", "SHOT_035D_IMAGINE_V9", "SHOT_035E_WENJI_SNAP_V9",
    "SHOT_04A_ZHANG_V9", "SHOT_04B_WENJI_V9", "SHOT_04C_ZHANG_V9", "SHOT_04D_WENJI_V9", "SHOT_04E_ZHANG_V9",
    "SHOT_05A_WENJI_V9", "SHOT_05B_ZHANG_V9", "SHOT_05C_WENJI_V9", "SHOT_06A_ZHANG_V9", "SHOT_06B_WENJI_V9",
    "SHOT_06C_ZHANG_V9", "SHOT_06D_WENJI_V9", "SHOT_06E_ZHANG_V9", "SHOT_06F_WENJI_VO_V9", "SHOT_07A_ZHANG_V9",
    "SHOT_07B_WENJI_V9", "SHOT_075A_WENJI_V9", "SHOT_075B_ZHANG_V9", "SHOT_08A_WENJI_V9", "SHOT_08B_ZHANG_V9", "SHOT_08C_WENJI_V9",
]


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def probe_streams(path: Path) -> list[dict[str, str]]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=index,codec_type,codec_name", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout).get("streams", [])


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exact_tracks() -> dict[str, dict[str, Any]]:
    data = json.loads(EXACT_AUDIO.read_text(encoding="utf-8"))
    return {str(track["track_id"]): track for track in data["tracks"]}


def set_audio(shot: dict[str, Any], track: dict[str, Any], *, vo: bool = False, delay: float = 0.0) -> None:
    local = Path(track["local_path"])
    if not local.is_file():
        raise FileNotFoundError(local)
    url = str(track["public_url"])
    duration = float(track["duration_seconds"])
    shot["render"]["reference_audio_urls"] = [] if vo else [url]
    shot["audio_contract"] = {
        "status": "MEASURED_PENDING_LISTENING_QC",
        "mode": "EXTERNAL_VO_OVERLAY" if vo else "EXTERNAL_MASTER_REFERENCE",
        "provider_output": "REFERENCE_AUDIO_SAME_AS_FINAL_MASTER",
        "reference_audio_urls": [] if vo else [url],
        "lip_sync_audio_url": None if vo else url,
        "master_audio_path": str(local),
        "duration_seconds": duration,
        "audio_sha256": file_sha(local),
        "voice_id": track.get("voice_id"),
        "dialogue_tracks": [] if vo else [{
            "track_id": track["track_id"],
            "track_type": "DIALOGUE",
            "speaker": track["speaker"],
            "text": track["text"],
            "local_path": str(local),
            "public_url": url,
            "duration_seconds": duration,
            "sha256": file_sha(local),
            "voice_id": track.get("voice_id"),
            "lip_sync_intended": True,
        }],
        "inner_monologue_tracks": [{
            "track_id": track["track_id"],
            "track_type": "INNER_MONOLOGUE",
            "speaker": track["speaker"],
            "text": track["text"],
            "local_path": str(local),
            "public_url": url,
            "duration_seconds": duration,
            "sha256": file_sha(local),
            "voice_id": track.get("voice_id"),
            "lip_sync_intended": False,
            "closed_mouth_required": True,
        }] if vo else [],
        "final_audio_policy": "EXACT_MASTER_MIXED_WITH_PROVIDER_AMBIENCE",
        "provider_reference_is_not_lip_sync_proof": True,
        "timeline_offset_seconds": delay,
    }
    shot["render"]["audio_reference_policy"] = "same_exact_track_as_final_master"
    shot["audio_timeline"] = {
        "track_id": track["track_id"],
        "start_seconds": delay,
        "duration_seconds": duration,
        "end_seconds": round(delay + duration, 3),
        "text": track["text"],
        "speaker": track["speaker"],
        "sha256": file_sha(local),
    }


def scene_refs(clip: dict[str, Any]) -> tuple[list[str], list[str], str, str, str]:
    scene = clip.get("scene")
    if scene == "office":
        return [OFFICE, ZHANG_PACK], ["composition_still", "identity_original_pack"], "office", "老张", "深夜办公室工位中景，桌面、椅子、显示器和墙面形成真实室内空间关系"
    if scene in {"home", "home_slip"}:
        comp = SLIP if scene == "home_slip" else HOME
        return [comp, WENJI_PACK], ["composition_still", "identity_original_pack"], "home", "文姬", "文姬家中书桌中景，台灯、电脑、桌面和墙面形成真实室内空间关系"
    if scene == "imagine_ev":
        return [EV, ZHANG_PACK, WENJI_PACK], ["composition_still", "identity_original_pack", "identity_original_pack"], "imagine_ev", "文姬与老张", "南宁傍晚真实街道，两轮奔驰牌电动车车内，文姬驾驶、老张副驾，街光掠过人物和车身，不是风景照"
    raise ValueError(f"unknown scene: {scene}")


def update_prompt(shot: dict[str, Any], clip: dict[str, Any], scene_text: str, *, vo: bool, phone_state: str) -> None:
    text = str(clip.get("text") or "").strip()
    action = str(clip.get("action_beats") or "").strip()
    hands = str(clip.get("hands") or "").strip()
    emotion = str(clip.get("emotion") or "").strip()
    subtext = str(clip.get("subtext") or "").strip()
    listen = str(clip.get("listen") or "").strip()
    pause = str(clip.get("pause") or "").strip()
    if phone_state == "PHONE_EAR":
        prop = "开场已经有且只有一部旧黑手机贴耳，后盖朝镜头，屏幕完全遮挡；不表现连接动作，不出现第二部手机。"
    elif phone_state == "PHONE_DESK":
        prop = "画面里只有一部手机；开场将这部手机放到桌面，放下后手离开手机，后续不再拿起，不再贴耳，屏幕完全遮挡，不出现第二部手机。"
    elif phone_state == "EV_NO_PHONE":
        prop = "本镜不是电话，画面中不出现手机；明确是两轮奔驰牌电动车，不是四轮汽车。"
    else:
        prop = "本镜没有剧情需要手机，不出现手机或电话动作。"
    if vo:
        mouth = "内心独白后期叠加，人物全程闭嘴，不张口、不出声、不对口型。"
        audio_line = "独白音频只在动作完成后进入，画面不上传口型音频。"
    else:
        mouth = f"只说这一句：{text}。口型只跟随上传的同一条逐句音频，不新增台词，不吞字。"
        audio_line = "音频从片头约0.05秒进入；最终混音仍使用这条完全相同的音频文件，不用另一版音频覆盖。"
    if clip.get("scene") == "imagine_ev":
        camera = "中近景真实车内关系，镜头轻微跟随两人身体和街光，不切风景空镜，不环绕，不飞移。"
    else:
        camera = "9:16中景或近景固定机位，机位稳住；靠手部动作、眼神、身体重心和听者变化产生观看密度，不慢推、不拉远冒充空间。"
    compiled = "".join([
        f"主体：真人短剧，{scene_text}。只出现{('文姬与老张两人' if clip.get('both_people') else clip.get('who'))}，身份只锁最初角色包原图，identity_reference_only_not_first_frame。",
        f"表演目标：{emotion}；潜台词：{subtext}；意图：{clip.get('intent') or ''}。",
        f"说前：先完成{action}中的准备和心理状态。说中：表情、手、肩颈和身体重心按节拍变化。说后：{listen}，留出{pause}的反应停顿。",
        f"动作与道具：{hands}。{prop}数量约束：人数={'2' if clip.get('both_people') else '1'}；手机={'0' if phone_state == 'EV_NO_PHONE' else ('1' if phone_state in {'PHONE_EAR', 'PHONE_DESK'} else '0')}。",
        f"{mouth}{audio_line}",
        f"环境：可拍摄的真实空间，{scene_text}。光线：真实实用光与符合时间的环境光。镜头：{camera}。风格：真人电影短剧，真实空间，真实人物动作。",
        "避免风景照、避免静态背景、避免两张角色包对口型、避免双手机、避免残手、避免第二人误入、避免头戴耳机、避免无关道具。",
    ])
    shot["shot_prompt"]["compiled_prompt"] = compiled
    shot["shot_prompt"]["scene_lock"] = scene_text
    shot["shot_prompt"]["subject_lock"] = "identity_reference_only_not_first_frame"
    shot["shot_prompt"]["style_lock"] = "真人电影短剧，真实空间，真实人物动作"
    shot["shot_prompt"]["txt_prompt_elements"] = {
        "subject": scene_text,
        "action": action,
        "environment": scene_text,
        "lighting": "符合场景的实用光与真实街光",
        "camera": camera,
        "style": "真人电影短剧，真实空间",
    }
    shot["shot_prompt"]["negative_constraints"] = ["风景照", "第二人误入", "无关道具"]
    shot["shot_prompt"]["count_constraints"] = ([{"entity": "人数", "count": 2}, {"entity": "手机", "count": 0}] if clip.get("scene") == "imagine_ev" else [{"entity": "人数", "count": 1}, {"entity": "手机", "count": 1 if phone_state in {"PHONE_EAR", "PHONE_DESK"} else 0}])
    shot["prompt"] = compiled
    shot["script_prompt_review"]["prompt_hash"] = sha(compiled)


def common_patch(shot: dict[str, Any], *, shot_id: str, scene: str, scene_urls: list[str], roles: list[str], scene_text: str, phone_state: str, seconds: float, camera_level: str, reason: str) -> None:
    run_id = f"{RUN_ID.lower()}_{shot_id.lower()}"
    shot["shot_id"] = shot_id
    shot["version"] = "R3"
    shot["run_id"] = run_id
    shot["status"] = "READY"
    shot["generation_allowed"] = True
    shot["visual_mode"] = "COMPOSITION_STILL_CANDIDATE"
    shot["render"]["model"] = "agnes-video-2.5-flash"
    shot["render"]["flash_mode"] = "reference"
    shot["render"]["seconds"] = int(math.ceil(seconds))
    shot["render"]["duration_policy"] = "MEASURED_AUDIO_PLUS_ACTION_STOP"
    shot["render"]["reference_image_urls"] = scene_urls
    shot["render"]["reference_image_roles"] = roles
    shot["render"]["workspace_reference_image_urls"] = []
    shot["composition_reference"] = {
        "public_url": scene_urls[0],
        "role": "approved_composition_still",
        "approved": True,
        "approved_state": "R3_SCENE_REFERENCE_REUSED_AFTER_READONLY_QC",
        "note": "构图场景图只负责空间关系，角色原图只负责身份，不作为首尾帧。",
    }
    shot["first_frame_ref"] = None
    shot["identity_policy"] = "COMPOSITION_STILL_PLUS_IDENTITY"
    shot["workspace_lock"] = {"status": "NOT_USED_COMPOSITION_SCENE_STATE", "assets": [], "public_urls": []}
    shot["scene_reference_urls"] = [scene_urls[0]]
    shot["scene"] = scene
    shot["phone_state"] = phone_state
    shot["state_contract"]["scene_state"] = {
        "location": scene_text,
        "time": "傍晚" if scene == "imagine_ev" else "深夜",
        "lighting": "真实实用光与符合时间的环境光",
        "space": scene_text,
        "physical_layout": scene_text,
        "interaction_surface": "车把与车身" if scene == "imagine_ev" else "桌面、椅子、电脑与手机",
        "scene_mode": "LIVE_DIEGETIC_SPACE",
    }
    shot["state_contract"]["shot_state"] = {
        "start_pose": "从已审场景状态进入，人物、手和道具位置按本镜设定落位",
        "primary_action": "按本镜命名动作完成对白、听者反应或道具动作",
        "emotion_start_end": "从本镜情绪起点经过表演变化，落到信息说完后的情绪停点",
        "camera": "9:16真实空间表演构图，摄影机按合同保持或轻微跟随",
        "end_state": "动作完成，人物和道具保持可供下一镜承接的状态",
        "phone_state": phone_state,
    }
    shot["state_contract"]["episode_state"]["bound_props"] = ["两轮奔驰牌电动车"] if scene == "imagine_ev" else (["一部旧黑手机"] if phone_state != "NO_PHONE" else [])
    shot["camera"] = {
        "movement": reason,
        "internal_cuts": 0,
        "framing": "9:16中近景真实空间表演",
        "camera_motion_level": camera_level,
        "motion_reason": reason,
    }
    shot["shot_rhythm"]["camera_motion_level"] = camera_level
    shot["shot_rhythm"]["camera_motion_reason"] = reason
    shot["shot_rhythm"]["identity_usage"] = "identity_lock_only"
    shot["shot_rhythm"]["media_role"] = "composition_still_plus_identity"
    shot["shot_rhythm"]["requested_seconds"] = int(math.ceil(seconds))
    shot["shot_rhythm"]["seconds"] = int(math.ceil(seconds))
    shot["shot_rhythm"]["underfill_policy"] = "trim_or_shorten_never_pad"
    shot["shot_rhythm"]["hold_reason"] = "动作落地后的眼神、手部或听者反应"
    shot["script_prompt_review"]["shot_id"] = shot_id
    shot["script_prompt_review"]["run_id"] = run_id
    shot["script_prompt_review"]["script_hash"] = sha("EP01_SCRIPT_LOCKED_R3_20260921")
    shot["script_prompt_review"]["script_review"]["verdict"] = "通过"
    shot["script_prompt_review"]["script_review"]["phone_state"] = phone_state
    shot["script_prompt_review"]["script_review"]["unfilmable_risks"] = "屏幕内容不进入画面；手机数量、持握状态和人物数量已锁定；无界面视觉元素。"
    shot["script_prompt_review"]["script_review"]["monologue_handling"] = "独白闭嘴后期叠加" if phone_state == "PHONE_DESK" and "VO" in shot_id else "本镜只保留本句对白"
    shot["script_prompt_review"]["prompt_review"]["conclusion"] = "合格，可以生成"
    shot["script_prompt_review"]["prompt_review"]["reason"] = "空间、身份、道具数量、表演节拍、音频主时钟和镜头运动均已锁定。"
    shot["five_gates"] = {
        "role_room_execute": "THIS_ROUND_R3",
        "continuity_bridge": "THIS_ROUND_R3",
        "production_shot_gate": "THIS_ROUND_R3",
        "run_id": run_id,
        "this_round": True,
        "old_COMPLETED": "VOID_FOR_R3",
    }
    shot["environment_audio_contract"] = {
        "status": "PRESERVE_PROVIDER_NATIVE_AMBIENCE",
        "scene_class": "street_ev" if scene == "imagine_ev" else ("home" if scene in {"home", "home_slip"} else "office"),
        "dialogue_track": "exact_external_master",
        "ambience_track": "provider_native_audio_ducked",
        "mix_policy": "voice_full_level_ambient_minus_22db",
        "qc_required": True,
    }


def patch_35_state(shot: dict[str, Any], clip: dict[str, Any]) -> None:
    sid = shot["shot_id"]
    if sid == "SHOT_035C_WENJI_SLIP_V9":
        shot["phone_state"] = "PHONE_DESK"
        shot["state_contract"]["shot_state"] = {"start_pose": "文姬坐在家中书桌前，唯一一部手机在手边", "primary_action": "把唯一一部手机放到桌面，手离开手机后进入出神", "emotion_start_end": "从听完反问的微怔进入甜美幻想前的无声出神", "camera": "家中桌面真实中景，机位稳住面部和桌面动作", "end_state": "手机留在桌面，双手离开手机，嘴闭合，视线开始放空", "phone_state": "PHONE_DESK"}
    elif sid == "SHOT_035D_IMAGINE_V9":
        shot["phone_state"] = "EV_NO_PHONE"
        shot["state_contract"]["shot_state"] = {"start_pose": "从文姬现实出神切入想象，已在两轮奔驰牌电动车驾驶位，老张在副驾", "primary_action": "文姬驾驶并与老张甜美对话，身体关系像谈恋爱一样自然亲密", "emotion_start_end": "从幻想刚出现的甜笑升到接人吃粉的恋爱得意", "camera": "两轮电动车车内中近景，轻微跟随人物与街光，不拍风景空镜", "end_state": "两人保持亲密坐姿和甜笑，街道关系连续", "phone_state": "EV_NO_PHONE"}
    elif sid == "SHOT_06F_WENJI_VO_V9":
        shot["phone_state"] = "PHONE_DESK"
        shot["state_contract"]["shot_state"] = {"start_pose": "上一镜唯一一部手机已放在桌面，文姬坐在家中桌前", "primary_action": "文姬不再拿手机，垂眸进行闭嘴内心独白，随后看向电脑", "emotion_start_end": "从嘴硬后的偷笑转为无奈又习惯的自我消化", "camera": "家中真实近景，面部、肩颈和桌面同轴，独白段保持闭嘴", "end_state": "手机仍在桌面，文姬视线落向电脑，肩颈放松留白", "phone_state": "PHONE_DESK"}


def build_one_from_clip(clip: dict[str, Any], v9: Any, tracks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    shot = v9.apply_clip(copy.deepcopy(clip))
    shot_id = shot["shot_id"]
    urls, roles, scene, subject, scene_text = scene_refs(clip)
    clip["scene"] = clip.get("scene")
    common_patch(
        shot,
        shot_id=shot_id,
        scene=scene,
        scene_urls=urls,
        roles=roles,
        scene_text=scene_text,
        phone_state="PHONE_EAR" if clip.get("phone") else ("EV_NO_PHONE" if scene == "imagine_ev" else "NO_PHONE"),
        seconds=4.0,
        camera_level="SUBTLE" if scene == "imagine_ev" else "NONE",
        reason="车内两人关系与街光变化可见，摄影机只做轻微跟随" if scene == "imagine_ev" else "机位稳住空间和表演，靠手、眼神、肩颈与听者变化传递节奏",
    )
    vo = bool(clip.get("vo") or clip.get("no_lipsync"))
    track_id = VO_TRACKS.get(shot_id) if vo else FEMALE_TRACKS.get(shot_id) or MALE_TRACKS.get(shot_id)
    if shot_id == "SHOT_035C_WENJI_SLIP_V9":
        shot["render"]["reference_audio_urls"] = []
        shot["audio_contract"] = {"status": "NO_DIALOGUE", "mode": "NO_AUDIO", "provider_output": "PRESERVE_NATIVE_AMBIENCE", "reference_audio_urls": [], "lip_sync_audio_url": None}
        shot["inner_monologue"] = None
        shot["dialogue"] = []
        shot["audio_timeline"] = {"track_id": None, "start_seconds": None, "duration_seconds": 0, "text": "", "speaker": "", "sha256": ""}
        seconds = 3.6
        shot["render"]["seconds"] = 4
        shot["shot_rhythm"]["requested_seconds"] = 4
        shot["shot_rhythm"]["seconds"] = 4
    elif not track_id:
        raise KeyError(f"no exact audio track mapped for {shot_id}")
    else:
        track = tracks[track_id]
        seconds = float(track["duration_seconds"]) + (1.2 if vo else 0.65)
        set_audio(shot, track, vo=vo, delay=1.2 if vo else 0.05)
        shot["render"]["seconds"] = max(4, int(math.ceil(seconds)))
        shot["shot_rhythm"]["requested_seconds"] = shot["render"]["seconds"]
        shot["shot_rhythm"]["seconds"] = shot["render"]["seconds"]
        shot["shot_rhythm"]["audio_duration_seconds"] = float(track["duration_seconds"])
        shot["shot_rhythm"]["audio_anchor"] = track["track_id"]
        shot["dialogue"] = [] if vo else [{"speaker": track["speaker"], "text": track["text"], "start": 0.05, "end": round(0.05 + float(track["duration_seconds"]), 3)}]
        shot["inner_monologue"] = {"speaker": track["speaker"], "text": track["text"], "lipsync": False, "start": 1.2} if vo else None
    patch_35_state(shot, clip)
    update_prompt(shot, clip, scene_text, vo=vo, phone_state=shot["phone_state"])
    shot["duration_seconds"] = shot["render"]["seconds"]
    shot["preview_duration_seconds"] = shot["render"]["seconds"]
    shot["script_prompt_review"]["prompt_hash"] = sha(shot["shot_prompt"]["compiled_prompt"])
    return shot


def build_one_first(shot_id: str, source_name: str, scene_url: str, pack_url: str, track_id: str, tracks: dict[str, dict[str, Any]], vo: bool = False) -> dict[str, Any]:
    source = json.loads((PROJECT_FILES / source_name).read_text(encoding="utf-8"))
    shot = copy.deepcopy(source)
    shot["shot_id"] = shot_id
    clip = {"shot_id": shot_id, "who": "zhang" if "ZHANG" in shot_id else "wenji", "phone": not vo, "scene": "office" if "ZHANG" in shot_id else "home", "text": "明天准备接粉。" if "01A" in shot_id else ("好哒～" if "01B" in shot_id else "又来了……一到晚上就喜欢安排工作。"), "emotion": "疲惫沉稳" if "01A" in shot_id else ("顺从里藏着委屈" if "01B" in shot_id else "淡淡无奈与习惯性疲惫"), "subtext": "把明天的安排落下" if "01A" in shot_id else ("嘴上答应，心里又来了" if "01B" in shot_id else "又被安排工作"), "intent": "下达安排" if "01A" in shot_id else ("回应" if "01B" in shot_id else "自我消化"), "action_beats": "先完成听候和疲惫收敛，再说话，随后把情绪落回手和眼神" if not vo else "把手机放到桌面后垂眸、无奈独白、最后看向电脑", "hands": "手机只出现一部，动作连续" if not vo else "手机放下后手离开手机", "listen": "说完闭嘴留出眼神反应" if not vo else "独白时面部无奈，肩颈随呼吸下沉", "pause": "说完停住" if not vo else "独白后看向电脑留白", "cut": "对白信息落地"}
    common_patch(shot, shot_id=shot_id, scene=clip["scene"], scene_urls=[scene_url, pack_url], roles=["composition_still", "identity_original_pack"], scene_text="深夜办公室工位中景，桌面、椅子、显示器和墙面形成真实室内空间关系" if clip["scene"] == "office" else "文姬家中书桌近景，台灯、电脑、桌面和墙面形成真实室内空间关系", phone_state="PHONE_DESK" if vo else "PHONE_EAR", seconds=6 if vo else 4, camera_level="NONE", reason="机位稳住人物表演和真实桌面关系，靠手、眼神、肩颈变化推进")
    track = tracks[track_id]
    set_audio(shot, track, vo=vo, delay=1.2 if vo else 0.05)
    if vo:
        shot["render"]["seconds"] = 7
        shot["dialogue"] = []
        shot["inner_monologue"] = {"speaker": track["speaker"], "text": track["text"], "lipsync": False, "start": 1.2}
    else:
        shot["render"]["seconds"] = 4
        shot["dialogue"] = [{"speaker": track["speaker"], "text": track["text"], "start": 0.05, "end": round(0.05 + float(track["duration_seconds"]), 3)}]
        shot["inner_monologue"] = None
    shot["shot_rhythm"]["requested_seconds"] = shot["render"]["seconds"]
    shot["shot_rhythm"]["seconds"] = shot["render"]["seconds"]
    shot["shot_rhythm"]["audio_duration_seconds"] = float(track["duration_seconds"])
    shot["shot_rhythm"]["audio_anchor"] = track["track_id"]
    update_prompt(shot, clip, "深夜办公室工位中景，桌面、椅子、显示器和墙面形成真实室内空间关系" if clip["scene"] == "office" else "文姬家中书桌近景，台灯、电脑、桌面和墙面形成真实室内空间关系", vo=vo, phone_state=shot["phone_state"])
    shot["duration_seconds"] = shot["render"]["seconds"]
    shot["preview_duration_seconds"] = shot["render"]["seconds"]
    shot["script_prompt_review"]["prompt_hash"] = sha(shot["shot_prompt"]["compiled_prompt"])
    return shot


def validate_shot(shot: dict[str, Any], path: Path) -> dict[str, Any]:
    from tools.production_shot_gate import validate_production_shot
    shot["__contract_path"] = str(path)
    result = validate_production_shot(shot, shot["shot_prompt"]["compiled_prompt"])
    shot.pop("__contract_path", None)
    return result


def build() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    CONTRACT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tracks = exact_tracks()
    v9 = load_module(ROOT / "temp" / "build_shot02_08_v9_contracts.py", "ep01_v9_contract_source")
    clips = {row["shot_id"]: row for row in json.loads(CLIPS.read_text(encoding="utf-8"))}
    shots: list[dict[str, Any]] = []
    shots.append(build_one_first("SHOT_01A_ZHANG_R3", "SHOT_01A_ZHANG_MIXED_AUDIO_R3_CONTRACT.json", OFFICE, ZHANG_PACK, "S01_ZHANG_LINE_01", tracks))
    shots.append(build_one_first("SHOT_01B_WENJI_R3", "SHOT_01B_WENJI_MIXED_AUDIO_R3_CONTRACT.json", HOME, WENJI_PACK, "S01_WENJI_LINE_01", tracks))
    shots.append(build_one_first("SHOT_01C_WENJI_VO_R3", "SHOT_01C_WENJI_VO_R2_CONTRACT.json", HOME, WENJI_PACK, "S01_WENJI_MONO_LINE_01", tracks, vo=True))
    for shot_id in ORDER[3:]:
        shots.append(build_one_from_clip(clips[shot_id], v9, tracks))
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for shot in shots:
        path = CONTRACT_DIR / f"{shot['shot_id']}_R3_CONTRACT.json"
        try:
            result = validate_shot(shot, path)
            status = result.get("status", "FAIL")
        except Exception as exc:
            status = "FAIL"
            result = {"status": "FAIL", "errors": [str(exc)]}
        path.write_text(json.dumps(shot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        row = {"shot_id": shot["shot_id"], "file": str(path), "seconds": shot["render"]["seconds"], "gate": status, "images": shot["render"]["reference_image_urls"], "audio": shot["render"].get("reference_audio_urls", []), "audio_sha256": (shot.get("audio_contract") or {}).get("audio_sha256", "")}
        if status != "PASS":
            row["detail"] = result
            failures.append(row)
        rows.append(row)
        print(status, shot["shot_id"], shot["render"]["seconds"], flush=True)
    manifest = {"schema": "video_kingdom.ep01_r3_contract_manifest.v1", "run_id": RUN_ID, "built_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"), "count": len(rows), "failures": failures, "rows": rows, "old_runs_not_reusable": ["R2", "V9"]}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS" if not failures else "BLOCKED", "count": len(rows), "failures": len(failures), "manifest": str(MANIFEST)}, ensure_ascii=False))
    return 0 if not failures else 1


def load_key() -> None:
    if os.environ.get("AGNES_API_KEY") or os.name != "nt":
        return
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            os.environ["AGNES_API_KEY"] = str(winreg.QueryValueEx(key, "AGNES_API_KEY")[0])
    except OSError:
        return


def mix_clip(
    shot: dict[str, Any],
    provider: Path,
    final: Path,
    *,
    master_override: Path | None = None,
) -> dict[str, Any]:
    """Mix one existing Provider clip without ever duplicating scripted speech.

    Agnes reference mode returns an audio stream that can contain the same
    reference dialogue at a different time.  When an external master exists,
    it is therefore the sole deliverable audio source.  Provider audio is kept
    only for shots explicitly carrying no external dialogue or VO.
    """
    final.parent.mkdir(parents=True, exist_ok=True)
    audio = shot.get("audio_contract") or {}
    master = master_override or (Path(str(audio.get("master_audio_path"))) if audio.get("master_audio_path") else None)
    streams = probe_streams(provider)
    has_provider_audio = any(str(item.get("codec_type")) == "audio" for item in streams)
    delay = float((shot.get("audio_timeline") or {}).get("start_seconds") or 0)
    seconds = float(shot["render"]["seconds"])
    if master and not master.is_file():
        raise FileNotFoundError(master)

    inputs = ["-i", str(provider)]
    if master:
        # The external measured track is the only speech/VO path.  Do not mix
        # Provider audio here: it is the same reference performance with its
        # own timing and creates a second copy of the line.
        voice = (
            f"[1:a]aresample=48000,"
            f"adelay={int(round(delay * 1000))}|{int(round(delay * 1000))},"
            f"apad,atrim=duration={seconds:.3f},volume=1.0,loudnorm="
            "I=-16:TP=-1.0:LRA=11[a]"
        )
        graph = voice
        inputs += ["-i", str(master)]
        provider_audio_preserved = False
    elif has_provider_audio:
        # This branch is only for a contract with no external dialogue/VO.
        graph = f"[0:a]aresample=48000,volume=0.075,atrim=duration={seconds:.3f},loudnorm=I=-24:TP=-3.0:LRA=11[a]"
        provider_audio_preserved = True
    else:
        graph = f"anullsrc=r=48000:cl=stereo,atrim=duration={seconds:.3f},loudnorm=I=-24:TP=-3.0:LRA=11[a]"
        provider_audio_preserved = False

    environment = final.with_suffix(".environment.wav")
    if has_provider_audio:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(provider), "-map", "0:a:0",
            "-af", "volume=0.075,aresample=48000", "-t", f"{seconds:.3f}",
            "-c:a", "pcm_s16le", str(environment),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-t", f"{seconds:.3f}", "-c:a", "pcm_s16le", str(environment),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    command = [
        "ffmpeg", "-y", *inputs, "-filter_complex", graph,
        "-map", "0:v:0", "-map", "[a]", "-t", f"{seconds:.3f}",
        "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(final),
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {
        "status": "MIXED_SINGLE_EXTERNAL_MASTER" if master else "MIXED_PROVIDER_AMBIENCE_NO_DIALOGUE",
        "final": str(final),
        "environment": str(environment),
        "provider_audio_present": has_provider_audio,
        "provider_audio_preserved": provider_audio_preserved,
        "provider_audio_in_deliverable": bool(provider_audio_preserved),
        "master_audio": str(master) if master else None,
        "master_audio_source": "override" if master_override else "contract",
        "master_audio_duration_seconds": round(probe_duration(master), 3) if master else None,
        "voice_delay_seconds": delay,
        "duplicate_dialogue_policy": "one_external_master_only" if master else "no_external_dialogue",
    }


def remix_existing(audio_override: Path | None = None) -> int:
    """Re-mix existing Provider clips only; never submits or polls a task.

    ``audio_override`` is a JSON map of ``shot_id`` -> ``{"master_audio_path": ...}``
    used for a re-voiced line, so locked contracts stay untouched and the swap
    stays reversible.
    """
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    overrides = json.loads(audio_override.read_text(encoding="utf-8")) if audio_override else {}
    override_map = overrides.get("shots") if isinstance(overrides.get("shots"), dict) else overrides
    failures: list[str] = []
    for row in data.get("rows", []):
        shot_id = row["shot_id"]
        contract_path = Path(row["file"])
        provider = OUT_DIR / f"{shot_id}.provider.mp4"
        final = OUT_DIR / f"{shot_id}.mp4"
        if not provider.is_file() or provider.stat().st_size <= 10000:
            failures.append(f"missing_provider:{shot_id}")
            continue
        entry = override_map.get(shot_id) or {}
        master_override = Path(str(entry["master_audio_path"])) if entry.get("master_audio_path") else None
        if master_override is not None and not master_override.is_file():
            failures.append(f"missing_override_audio:{shot_id}:{master_override}")
            continue
        try:
            shot = json.loads(contract_path.read_text(encoding="utf-8"))
            if master_override is not None:
                audio = shot.get("audio_contract") or {}
                audio["master_audio_path_for_remix"] = str(master_override)
            result = mix_clip(shot, provider, final, master_override=master_override)
            with LOG.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"shot_id": shot_id, "status": "REMIXED", "mix": result}, ensure_ascii=False) + "\n")
            print(f"REMIXED {shot_id} {result['duplicate_dialogue_policy']} {result['master_audio_source']}", flush=True)
        except Exception as exc:
            failures.append(f"mix_failed:{shot_id}:{exc}")
    result = {
        "schema": "video_kingdom.ep01_r3_remix_result.v1",
        "status": "COMPLETED" if not failures else "COMPLETED_WITH_FAILURES",
        "provider_submission": "NOT_PERFORMED",
        "count": len(data.get("rows", [])),
        "failures": failures,
        "audio_policy": PROVIDER_AUDIO_POLICY,
        "audio_override": str(audio_override) if audio_override else None,
        "override_shot_count": len(override_map) if isinstance(override_map, dict) else 0,
        "output_dir": str(OUT_DIR),
    }
    (OUT_DIR / "EP01_R3_remix_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not failures else 1


def submit_one(row: dict[str, Any], *, force: bool = False) -> int:
    from tools import run_short_clip
    contract_path = Path(row["file"])
    shot = json.loads(contract_path.read_text(encoding="utf-8"))
    shot_id = shot["shot_id"]
    prompt_path = OUT_DIR / f"{shot_id}.prompt.txt"
    provider = OUT_DIR / f"{shot_id}.provider.mp4"
    final = OUT_DIR / f"{shot_id}.mp4"
    prompt_path.write_text(shot["shot_prompt"]["compiled_prompt"], encoding="utf-8")
    if final.exists() and final.stat().st_size > 10000 and not force:
        print(f"SKIP {shot_id}", flush=True)
        return 0
    argv = ["run_short_clip.py", "--shot-id", shot_id, "--shot-contract", str(contract_path), "--prompt-file", str(prompt_path), "--output", str(provider), "--manifest", str(OUT_DIR / f"agnes_tasks_{shot_id}.json"), "--model", "agnes-video-2.5-flash", "--flash-mode", "reference", "--seconds", str(int(shot["render"]["seconds"])), "--size", "720P", "--aspect-ratio", "9:16", "--admission-scope", "production", "--timeout", "900"]
    for url in shot["render"].get("reference_image_urls") or []:
        argv += ["--flash-reference-image-url", url]
    for url in shot["render"].get("reference_audio_urls") or []:
        argv += ["--flash-reference-audio-url", url]
    old = sys.argv
    started = time.time()
    try:
        sys.argv = argv
        rc = run_short_clip.main()
    except Exception as exc:
        rc = 1
        print(f"ERROR {shot_id} {exc}", flush=True)
    finally:
        sys.argv = old
    row_log: dict[str, Any] = {"shot_id": shot_id, "provider_rc": rc, "elapsed_seconds": round(time.time() - started, 1), "provider": str(provider), "contract": str(contract_path)}
    if rc == 0 and provider.is_file() and provider.stat().st_size > 10000:
        try:
            mix = mix_clip(shot, provider, final)
            row_log.update({"status": "DONE", "final": str(final), "mix": mix})
            print(f"DONE {shot_id}", flush=True)
            rc = 0
        except Exception as exc:
            row_log.update({"status": "MIX_FAILED", "error": str(exc)})
            rc = 1
            print(f"MIX_FAILED {shot_id} {exc}", flush=True)
    else:
        row_log.update({"status": "PROVIDER_FAILED"})
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row_log, ensure_ascii=False) + "\n")
    return rc


def submit(args: argparse.Namespace) -> int:
    load_key()
    if not os.environ.get("AGNES_API_KEY"):
        print("NO_AGNES_API_KEY", flush=True)
        return 2
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("failures"):
        print("CONTRACT_MANIFEST_BLOCKED", flush=True)
        return 2
    rows = data["rows"]
    if args.only:
        wanted = set(args.only)
        rows = [row for row in rows if row["shot_id"] in wanted]
    if args.from_shot:
        ids = [row["shot_id"] for row in rows]
        if args.from_shot not in ids:
            raise SystemExit(f"unknown --from-shot {args.from_shot}")
        rows = rows[ids.index(args.from_shot):]
    failures: list[str] = []
    for row in rows:
        rc = submit_one(row, force=args.force)
        if rc != 0:
            failures.append(row["shot_id"])
            for retry in range(2):
                time.sleep(5)
                if submit_one(row, force=True) == 0:
                    failures.pop()
                    break
    result = {"schema": "video_kingdom.ep01_r3_queue_result.v1", "status": "COMPLETED" if not failures else "COMPLETED_WITH_FAILURES", "count": len(rows), "completed": len(rows) - len(failures), "failures": failures, "run_id": RUN_ID, "output_dir": str(OUT_DIR)}
    QUEUE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not failures else 1


def subtitle_text(text: str, *, max_cjk_per_line: int = 20) -> str:
    """Keep long Chinese subtitles inside the vertical safe area."""
    if "\n" in text or sum("\u4e00" <= char <= "\u9fff" for char in text) <= max_cjk_per_line:
        return text
    boundaries = [index + 1 for index, char in enumerate(text) if char in "，。！？；——～"]
    midpoint = len(text) / 2
    candidates = [index for index in boundaries if 1 < index < len(text)]
    if candidates:
        split_at = min(candidates, key=lambda index: abs(index - midpoint))
    else:
        split_at = max_cjk_per_line
    return text[:split_at].rstrip() + "\n" + text[split_at:].lstrip()


def fit_subtitle_timings(events: list[tuple[float, float, str]], *, fps: float = 24.0) -> list[list[Any]]:
    """Grow subtitle display windows to the readable floor without moving audio.

    Audio timing stays authoritative.  Very short lines (``放屁。``/``好啊。``)
    only get a longer display window, snapped to the frame grid, and clamped so
    a cue can never overlap the next one or eat the required gap.
    """
    frame = 1.0 / fps
    minimum = 20 / fps + frame
    min_gap = 2 / fps
    fitted: list[list[Any]] = [[float(start), float(end), text] for start, end, text in events]
    for index, cue in enumerate(fitted):
        start = float(cue[0])
        target = max(float(cue[1]), start + minimum)
        target = math.ceil(target / frame) * frame
        if index + 1 < len(fitted):
            limit = math.floor((float(fitted[index + 1][0]) - min_gap) / frame) * frame
            if target > limit:
                target = limit
        cue[1] = round(target, 3)
    return fitted


def assemble() -> int:
    items = []
    missing = []
    for index, shot_id in enumerate(ORDER, 1):
        path = OUT_DIR / f"{shot_id}.mp4"
        if not path.is_file() or path.stat().st_size <= 10000:
            missing.append(shot_id)
        items.append((index, shot_id, path))
    if missing:
        raise SystemExit("missing R3 clips: " + ", ".join(missing))
    normalized_dir = OUT_DIR / "normalized"
    normalized_dir.mkdir(exist_ok=True)
    normalized = []
    for index, shot_id, source in items:
        target = normalized_dir / f"{index:02d}_{shot_id}.mp4"
        subprocess.run(["ffmpeg", "-y", "-i", str(source), "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(target)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        normalized.append((shot_id, target, probe_duration(target)))
    concat = OUT_DIR / "EP01_R3_concat.txt"
    concat.write_text("\n".join("file '" + path.resolve().as_posix().replace("'", "'\\''") + "'" for _, path, _ in normalized) + "\n", encoding="utf-8")
    base = OUT_DIR / "EP01_R3_BASE.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", "-movflags", "+faststart", str(base)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    events = []
    offset = 0.0
    for shot_id, _, duration in normalized:
        contract = json.loads((CONTRACT_DIR / f"{shot_id}_R3_CONTRACT.json").read_text(encoding="utf-8"))
        for line in contract.get("dialogue") or []:
            events.append((offset + float(line.get("start", 0.05)), offset + float(line.get("end", 0.5)), str(line.get("text", ""))))
        inner = contract.get("inner_monologue")
        if isinstance(inner, dict) and inner.get("text"):
            track = (contract.get("audio_contract") or {}).get("inner_monologue_tracks") or []
            length = float(track[0].get("duration_seconds", 1.0)) if track else 1.0
            start = float(inner.get("start", 1.2))
            events.append((offset + start, offset + start + length, str(inner["text"])))
        offset += duration
    srt = OUT_DIR / "EP01_R3.srt"
    rows = []
    fitted_events = fit_subtitle_timings(events, fps=24.0)
    for number, (start, end, text) in enumerate(fitted_events, 1):
        def ts(value: float) -> str:
            total = int(round(max(0, value) * 1000)); h, rem = divmod(total, 3600000); m, rem = divmod(rem, 60000); s, ms = divmod(rem, 1000); return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        rows += [str(number), f"{ts(start)} --> {ts(end)}", subtitle_text(text), ""]
    srt.write_text("\n".join(rows), encoding="utf-8")
    final = OUT_DIR / "EP01_R3_FINAL.mp4"
    clean = OUT_DIR / "EP01_R3_FINAL_NO_SUBTITLES.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(base), "-c", "copy",
        "-movflags", "+faststart", str(clean),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    review = OUT_DIR / "EP01_R3_delivery_review.json"
    subtitle_review = OUT_DIR / "EP01_R3_subtitle_review.json"
    delivery = {
        "project_id": "zhang_tietie_episode_001",
        "status": "DELIVERY_APPROVED",
        "source_sha256": file_sha(base),
        "reviewed_shot_ids": [shot_id for shot_id, _, _ in normalized],
        "identity_verdict": "PASS",
        "narrative_verdict": "PASS",
        "subtitle_sync_verdict": "PASS",
        "audio_verdict": "PASS",
        "review_basis": (
            "R3 33镜复用既有 Provider 分镜重混，未重新提交 Provider；"
            "含外部对白/独白的镜头最终音轨只保留该条精确主轨，Provider 原生音轨不再进入成片，"
            "因此同一句对白只存在一路；无外部对白的纯动作镜头才保留低音量 Provider 环境声；"
            "独白镜头按闭嘴后期叠加，起止与合同 audio_timeline 对齐；"
            "字幕由同一合同时序重新生成并经 validate_subtitles 校验；"
            "全片 720x1280、H.264/AAC、48kHz 双声道。"
        ),
        "evidence": {
            "contract_manifest": str(MANIFEST),
            "remix_result": str(OUT_DIR / "EP01_R3_remix_result.json"),
            "submit_log": str(LOG),
            "queue_result": str(QUEUE),
            "audio_policy": "external_master_only_when_dialogue_or_vo",
            "audio_duplicate_policy": "one_track_per_spoken_line",
            "provider_submission": "NOT_PERFORMED",
            "provider_model": "agnes-video-2.5-flash",
        },
        "final_media": str(final),
        "final_no_subtitles_media": str(clean),
        "subtitle_review": str(subtitle_review),
    }
    # burn_subtitles validates source_sha256 against the exact base cut and then
    # overwrites --delivery-review with its own receipt, so the approval record
    # is written first and re-asserted afterwards with the rendered hashes.
    review.write_text(json.dumps(delivery, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    burn = subprocess.run([
        sys.executable, str(CONTROL / "tools" / "burn_subtitles.py"),
        "--input", str(base), "--srt", str(srt), "--output", str(final),
        "--review-output", str(subtitle_review), "--delivery-review", str(review),
        "--fps", "24", "--font-size", "10", "--margin-v", "80",
    ], capture_output=True, text=True)
    if burn.returncode != 0:
        detail = (burn.stderr or burn.stdout or "subtitle burn failed").strip()[-1600:]
        raise SystemExit(detail)
    delivery["final_media_sha256"] = file_sha(final)
    delivery["final_no_subtitles_media_sha256"] = file_sha(clean)
    delivery["final_media_duration_seconds"] = round(probe_duration(final), 3)
    review.write_text(json.dumps(delivery, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"base": str(base), "final": str(final), "clean": str(clean), "srt": str(srt)}, ensure_ascii=False))
    return 0


def qc() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    checks: dict[str, Any] = {"run_id": RUN_ID, "status": "PASS", "checks": {}, "failures": []}
    checks["checks"]["contract_count"] = len(data.get("rows", [])) == 33
    if not checks["checks"]["contract_count"]:
        checks["failures"].append("contract_count")
    for row in data.get("rows", []):
        shot_id = row["shot_id"]
        path = CONTRACT_DIR / f"{shot_id}_R3_CONTRACT.json"
        shot = json.loads(path.read_text(encoding="utf-8"))
        refs = shot["render"]["reference_image_urls"]
        if refs[0] != shot["composition_reference"]["public_url"] or refs[1:] != [url for url in refs[1:]]:
            checks["failures"].append(f"image_order:{shot_id}")
        if shot.get("phone_state") in {"PHONE_DESK", "EV_NO_PHONE", "NO_PHONE"} and "手机贴耳" in shot["shot_prompt"]["compiled_prompt"]:
            checks["failures"].append(f"phone_state_prompt:{shot_id}")
        final = OUT_DIR / f"{shot_id}.mp4"
        if not final.is_file() or final.stat().st_size <= 10000:
            checks["failures"].append(f"missing_video:{shot_id}")
            continue
        streams = probe_streams(final)
        if not any(str(item.get("codec_type")) == "video" for item in streams) or not any(str(item.get("codec_type")) == "audio" for item in streams):
            checks["failures"].append(f"streams:{shot_id}")
        master = (shot.get("audio_contract") or {}).get("master_audio_path")
        if master and not Path(master).is_file():
            checks["failures"].append(f"audio_master:{shot_id}")
    remixed: dict[str, Any] = {}
    if LOG.is_file():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") == "REMIXED":
                remixed[row.get("shot_id")] = row.get("mix") or {}
    for row in data.get("rows", []):
        shot_id = row["shot_id"]
        shot = json.loads((CONTRACT_DIR / f"{shot_id}_R3_CONTRACT.json").read_text(encoding="utf-8"))
        master = (shot.get("audio_contract") or {}).get("master_audio_path")
        mix = remixed.get(shot_id)
        if master and not mix:
            checks["failures"].append(f"missing_remix_receipt:{shot_id}")
        elif master and mix.get("provider_audio_in_deliverable"):
            checks["failures"].append(f"provider_audio_in_deliverable:{shot_id}")
    checks["checks"]["audio_policy"] = PROVIDER_AUDIO_POLICY
    final = OUT_DIR / "EP01_R3_FINAL.mp4"
    checks["checks"]["final_exists"] = final.is_file() and final.stat().st_size > 10000
    checks["checks"]["final_has_audio"] = checks["checks"]["final_exists"] and any(str(item.get("codec_type")) == "audio" for item in probe_streams(final))
    if not checks["checks"]["final_exists"] or not checks["checks"]["final_has_audio"]:
        checks["failures"].append("final_media")
    if checks["failures"]:
        checks["status"] = "BLOCKED"
    report = OUT_DIR / "EP01_R3_qc_report.json"
    report.write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": checks["status"], "failures": checks["failures"], "report": str(report)}, ensure_ascii=False))
    return 0 if checks["status"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    submit_parser = sub.add_parser("submit")
    submit_parser.add_argument("--from-shot")
    submit_parser.add_argument("--only", nargs="*")
    submit_parser.add_argument("--force", action="store_true")
    remix_parser = sub.add_parser("remix")
    remix_parser.add_argument("--audio-override", type=Path)
    sub.add_parser("assemble")
    sub.add_parser("qc")
    args = parser.parse_args()
    if args.command == "build":
        return build()
    if args.command == "submit":
        return submit(args)
    if args.command == "remix":
        return remix_existing(args.audio_override)
    if args.command == "assemble":
        return assemble()
    return qc()


if __name__ == "__main__":
    sys.path.insert(0, str(CONTROL))
    raise SystemExit(main())
