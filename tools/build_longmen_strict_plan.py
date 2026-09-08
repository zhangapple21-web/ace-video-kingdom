"""Compile a source-bound, five-section plan for the Longmen tomb excerpt.

This is a planner/asset stage only.  It does not submit video jobs; the
existing ``run_comedy_episode.py`` remains the single renderer and audit path.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

from PIL import Image

try:
    from .run_idea_pipeline import _build_generation_contract, _write_json, _sha256
except ImportError:
    from run_idea_pipeline import _build_generation_contract, _write_json, _sha256
from runtime.provider_admission import admit_provider_request, assert_admission, build_canonical_generation_request

ROOT = Path(__file__).resolve().parents[1]
IMAGE_MAX_BYTES = 500 * 1024
SOURCE = Path(r"C:\tmp\小说题材\龙门战神.txt")
SOURCE_SHA256 = "cc0eef87635f1fa5d93203d80ec4a7a4f52249eaea7dca9f1b8248677a7d132d"

def _compress_webp(path: Path) -> Path:
    target = path.with_suffix(".webp")
    with Image.open(path) as source:
        image = source.convert("RGB")
        for scale in (1.0, 0.85, 0.7, 0.55, 0.4):
            candidate = image.copy()
            if scale != 1.0:
                candidate.thumbnail((max(1, int(image.width * scale)), max(1, int(image.height * scale))))
            for quality in (82, 70, 58, 46, 34):
                buffer = io.BytesIO()
                candidate.save(buffer, format="WEBP", quality=quality, method=6)
                if buffer.tell() < IMAGE_MAX_BYTES:
                    fd, temporary_name = tempfile.mkstemp(
                        prefix=f".{target.name}.",
                        suffix=".tmp",
                        dir=str(target.parent),
                    )
                    try:
                        with os.fdopen(fd, "wb") as handle:
                            handle.write(buffer.getvalue())
                            handle.flush()
                            os.fsync(handle.fileno())
                        os.replace(temporary_name, target)
                    finally:
                        Path(temporary_name).unlink(missing_ok=True)
                    return target
    raise RuntimeError(f"image could not be compressed below 500KB: {path.name}")


def _valid_webp(path: Path) -> bool:
    if path.suffix.lower() != ".webp" or not path.is_file() or path.stat().st_size >= IMAGE_MAX_BYTES:
        return False
    try:
        with Image.open(path) as image:
            return image.format == "WEBP"
    except (OSError, ValueError):
        return False


def _image_reference(path: Path) -> dict[str, object]:
    if not _valid_webp(path):
        path = _compress_webp(path)
    size = path.stat().st_size
    if size >= IMAGE_MAX_BYTES:
        raise RuntimeError(f"image exceeds 500KB: {path.name}")
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": size,
    }


SHOT_SPECS = [
    ("S01A", "SC01", "久跪凝视", "陆凡穿迷彩服在乱石孤坟前久跪，泛红双眼直盯墓头", "", "陆凡", "荒山孤坟前，乱石坟头与长满青苔的木板墓牌；空旷冷清，不添加天气季节"),
    ("S02A", "SC02", "三磕立誓", "陆凡连磕三个响头并身体微颤", "爸，儿子不孝，此仇不报，誓不为人！", "陆凡", "同一荒山孤坟前，陆凡仍跪在墓前；保持迷彩服、红眼和墓牌位置"),
    ("S03A", "SC03", "迟到祭酒", "陆凡打开两瓶五十年陈酿，一瓶倒在坟前，另一瓶紧握在手", "", "陆凡", "同一墓前；两瓶酒的数量、坟前与手中位置按原文锁定"),
    ("S04A", "SC04", "父子陪酒", "陆凡举起酒杯，面对父亲墓碑说出迟到的父子对白", "爸，你以前一直想让我陪你喝酒，今天，我陪你喝个够！只是没想到，我们父子俩第一次喝酒，是这种方式！", "陆凡", "同一墓前；酒杯在手，视线朝墓碑；不把对白变成字幕或旁白"),
    ("S05A", "SC05", "猛灌咳嗽", "陆凡举杯猛灌一口后连续咳嗽，暴露伤还没好", "咳咳咳……", "陆凡", "同一墓前；动作只表现猛灌后咳嗽，不添加伤口特写或医疗背景"),
    ("S06A", "SC06", "黑雨搀扶", "身后的黑雨满脸担忧地搀扶陆凡", "龙魂，您别太伤心了，您伤还没好。", "黑雨", "同一墓前；黑雨从陆凡身后进入搀扶关系，不添加军衔、车辆或新人物"),
]


def _asset_prompt(kind: str, spec: tuple[str, ...] | None = None) -> str:
    identity = "陆凡：30岁左右中国男性，东亚自然脸型，短黑发，迷彩服，神情压抑；黑雨：成年中国男性，短黑发，深色无品牌便装，克制担忧"
    base = "中国审美写实短剧电影摄影，真实东亚面部比例，低饱和自然肤色，竖屏9:16，光线克制，无广告感"
    forbidden = "禁止欧美脸、动漫、赛博霓虹、品牌logo、原文之外可读文字、字幕、额外人物、自动推拉摇移、内部切镜、宣传MV构图"
    if kind == "character_main":
        return f"{base}。角色身份参考图：{identity.split('；')[0]}。正面半身中性表情，固定脸型、发型、迷彩服。{forbidden}。"
    if kind == "character_counter":
        return f"{base}。角色身份参考图：{identity.split('；')[1]}。正面半身中性表情，固定脸型、发型、深色无品牌便装。{forbidden}。"
    if kind == "prop_wine":
        return f"{base}。孤坟前两瓶五十年陈酿酒瓶与一只酒杯，作为道具锚图，真实中国祭奠场景，{forbidden}。"
    if kind == "prop_tomb":
        return f"{base}。乱石砌成的简陋坟头与长满青苔的木板墓牌，道具/环境锚图，{forbidden}。"
    shot_id, _, title, action, _, speaker, setting = spec or ("", "", "", "", "", "", "")
    # Do not put the full cast list into every anchor prompt.  The previous
    # version did that and the image model repeatedly materialised Hei Yu in
    # Lu Fan-only shots.  The allowed-cast set is now explicit per shot.
    cast = "仅陆凡" if speaker != "黑雨" else "陆凡与黑雨两人"
    cast_rule = (
        "画面人物数量严格为1，只能出现陆凡，黑雨不得出镜"
        if speaker != "黑雨"
        else "画面人物数量严格为2，只能出现陆凡与黑雨，不得出现第三人"
    )
    shot_identity = "陆凡：30岁左右中国男性，东亚自然脸型，短黑发，迷彩服，神情压抑"
    if speaker == "黑雨":
        shot_identity += "；黑雨：成年中国男性，短黑发，深色无品牌便装，克制担忧"
    return f"{base}。场景锚图 {shot_id}《{title}》：{setting}。允许出镜：{cast}。{cast_rule}。人物身份锁：{shot_identity}。只呈现一个主要视觉事件：{action}。首态稳定、动作完成后保留反应停留；固定机位。{forbidden}。"


def _generate_assets(project: Path) -> None:
    key = os.getenv("SHENWEN_IMAGE_API_KEY") or os.getenv("SHENWEN_API_KEY")
    if not key:
        raise RuntimeError("SHENWEN_IMAGE_API_KEY/SHENWEN_API_KEY unavailable")
    base = os.getenv("SHENWEN_IMAGE_BASE_URL", "https://api.shenwenai.com/v1").rstrip("/")
    assets = project / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    jobs: list[tuple[Path, str, tuple[str, ...] | None]] = [
        (assets / "char_main_reference.webp", "character_main", None),
        (assets / "char_counter_reference.webp", "character_counter", None),
        (assets / "prop_wine_anchor.webp", "prop_wine", None),
        (assets / "prop_tomb_anchor.webp", "prop_tomb", None),
    ]
    jobs.extend((assets / f"{sid.lower()}_anchor.webp", "scene", spec) for spec in SHOT_SPECS for sid in [spec[0]])
    for path, kind, spec in jobs:
        if _valid_webp(path):
            continue
        payload = {"model": "gpt-image-2", "prompt": _asset_prompt(kind, spec), "size": "1024x1536", "quality": "medium", "n": 1}
        canonical_shot = {
            "episode_id": project.name,
            "shot_id": f"ASSET_{path.stem}",
            "prompt": payload["prompt"],
            "action": kind,
            "camera": {"framing": "asset_reference_sheet", "movement": "NONE"},
            "visible_entities": [path.stem],
            "audio_contract": {"status": "NOT_APPLICABLE"},
            "reference_assets": [],
        }
        canonical_request = build_canonical_generation_request(
            canonical_shot, payload, provider="shenwen-image", endpoint=f"{base}/images/generations",
            payload_schema="openai.images.generations.v1", model="gpt-image-2", scope="research", request_kind="asset",
        )
        admission_path = project / "admission_receipts" / f"{path.stem}.json"
        admission = admit_provider_request(canonical_request, contract_status="CONTRACT_VALID", receipt_path=admission_path)
        if admission["status"] != "ADMITTED":
            raise RuntimeError("provider admission blocked for asset: " + ";".join(admission["preflight"]["errors"]))
        req = urllib.request.Request(f"{base}/images/generations", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
        assert_admission(admission, admission["request_hash"], provider_payload=payload)
        with urllib.request.urlopen(req, timeout=180) as response:
            data = json.load(response)
        item = (data.get("data") or [{}])[0]
        raw = item.get("b64_json")
        if not raw:
            raise RuntimeError(f"image provider returned no b64_json for {path.name}")
        source_path = path.with_name(path.stem + ".source")
        try:
            source_path.write_bytes(base64.b64decode(raw, validate=True))
            _compress_webp(source_path)
        finally:
            source_path.unlink(missing_ok=True)


def _asset_reference(project: Path, relative_path: str) -> dict[str, object]:
    return _image_reference(project / relative_path)


def build(project: Path) -> dict:
    project.mkdir(parents=True, exist_ok=True)
    (project / "assets").mkdir(exist_ok=True)
    asset_refs = {
        "char_main": _asset_reference(project, "assets/char_main_reference.webp"),
        "char_counter": _asset_reference(project, "assets/char_counter_reference.webp"),
        "prop_wine": _asset_reference(project, "assets/prop_wine_anchor.webp"),
        "prop_tomb": _asset_reference(project, "assets/prop_tomb_anchor.webp"),
        **{
            spec[0].lower(): _asset_reference(project, f"assets/{spec[0].lower()}_anchor.webp")
            for spec in SHOT_SPECS
        },
    }
    source_bytes = SOURCE.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()
    if digest != SOURCE_SHA256:
        raise RuntimeError(f"source SHA-256 mismatch: {digest}")
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    excerpt = "\n".join(lines[10:35])
    generation_contract = _build_generation_contract(
        idea="《龙门战神》第一章“回来了”墓前连续段落：陆凡祭奠父亲陆山河，因伤咳嗽，由黑雨搀扶。",
        setting="荒山孤坟、乱石坟头、长满青苔的木板墓牌",
        characters=[
            {"asset_id": "CHAR_MAIN", "identity": "陆凡；中国男性，迷彩服，泛红双眼，伤未好；陆山河之子", "role": "祭奠父亲并立誓的儿子"},
            {"asset_id": "CHAR_COUNTER", "identity": "黑雨；成年中国男性，身后搀扶，满脸担忧；具体军衔未知", "role": "随行照护者，称陆凡为龙魂"},
        ],
        forbidden=[
            "不得新增或替换人物，不得改变父子/照护关系",
            "不得添加原文未写的天气、季节、车辆、军衔、伤口特写、死因或阴谋",
            "不得改变荒山孤坟、乱石坟头、青苔木板墓牌、迷彩服和两瓶酒的状态",
            "不得自动推拉摇移、内部切镜、转场或第二主要动作",
            "不得生成原文之外的字幕、logo、品牌、现实机构标识、宣传风或MV风；原文明确要求的墓牌字样只允许按原文出现",
            "不得把原文对白改写成旁白、口号或新增台词",
        ],
    )
    shots = []
    sidecars = []
    for idx, spec in enumerate(SHOT_SPECS):
        sid, scene_id, title, action, dialogue, speaker, setting = spec
        identity = "assets/char_counter_reference.webp" if speaker == "黑雨" else "assets/char_main_reference.webp"
        anchor = f"assets/{sid.lower()}_anchor.webp"
        shot_contract = {
            "version": "ace.video_kingdom.single_action_shot_contract.v1",
            "single_action": True, "action_unit": action, "primary_visual_event": title,
            "max_primary_actions": 1, "internal_cuts_allowed": 0,
            "camera_autonomy": "OFF", "scene_transition_autonomy": "OFF", "secondary_action_autonomy": "OFF",
            "first_state": f"{title}前：{setting}", "last_state": "动作完成后保留原文情绪与空间关系",
            "allowed_characters": ["陆凡", "黑雨"] if speaker == "黑雨" else ["陆凡"],
            "required_on_screen_text": "陆山河之墓" if sid == "S02A" else "",
            "cut_policy": "cut only after action completion and recovery hold",
        }
        request = {
            "main_generation_instruction": generation_contract["main_generation_instruction"],
            "character_identity_lock": generation_contract["character_identity_lock"],
            "shot_contract_constraints": generation_contract["shot_contract_constraints"],
            "shot_contract": shot_contract,
            "forbidden_behavior": generation_contract["forbidden_behavior"],
            "acceptance_standard": generation_contract["acceptance_standard"]["per_shot"],
            "allowed_characters": ["陆凡", "黑雨"] if speaker == "黑雨" else ["陆凡"],
            "required_on_screen_text": "陆山河之墓" if sid == "S02A" else "",
        }
        text_rule = "只允许原文墓牌文字‘陆山河之墓’，不得出现其它文字" if sid == "S02A" else "画面不得出现任何文字"
        prompt = f"主生成指令：{request['main_generation_instruction']}。角色身份锁：{identity}；关系不可改写。允许出镜人物仅：{'、'.join(request['allowed_characters'])}。当前镜头合同：首态={shot_contract['first_state']}；唯一主要视觉事件={action}；末态={shot_contract['last_state']}；固定机位、内部切镜=0。禁止行为：{'；'.join(generation_contract['forbidden_behavior'])}。场景事实：{setting}。屏显文字规则：{text_rule}。对白由外部 TTS 注入，不在画面生成字幕。"
        duration = 3.0 if not dialogue else 4.0
        shot = {
            "shot_id": sid, "scene_id": scene_id, "prompt": prompt,
            "action_beats": [f"首态：{shot_contract['first_state']}", f"动作：{action}", f"末态：{shot_contract['last_state']}"],
            "required_asset_ids": ["CHAR_MAIN", "CHAR_COUNTER", "PROP_WINE", "PROP_TOMB", scene_id],
            "first_state": shot_contract["first_state"], "action": action, "last_state": shot_contract["last_state"],
            "continuity_bridge": f"{scene_id} -> {SHOT_SPECS[idx+1][0]}" if idx + 1 < len(SHOT_SPECS) else "原文段落收束",
            "continuity_bridge_to_next": f"{scene_id} -> {SHOT_SPECS[idx+1][0]}" if idx + 1 < len(SHOT_SPECS) else "原文段落收束",
            "quality_gate": "audit_video_pacing PASS；内部切镜0；TTS覆盖；首态/动作/末态及人物关系可复核",
            "camera": {"shot_type": "dialogue" if dialogue else "action", "scale": "medium close-up", "movement": "FIXED_DIALOGUE", "axis": "screen-left facing screen-right", "movement_count": 0},
            "dramatic_function": title, "information_gain": dialogue or action, "emotion_change": "悔恨与克制痛感逐步外露", "anchor_reuse_allowed": False,
            "shot_contract": shot_contract, "generation_request": request,
            "render": {"model": "agnes-video-v2.0", "seconds": 6, "width": 704, "height": 1280, "num_frames": 49, "frame_rate": 8, "image": anchor, "fallback_image": anchor, "image_reference": asset_refs[sid.lower()], "negative_prompt": "; ".join(generation_contract["forbidden_behavior"])},
            "dialogue_text": dialogue, "speaker": speaker,
        }
        shots.append(shot)
        sidecars.append({
            "shot_id": sid, "source_scene": f"{title}：{action}", "anchor_reuse_allowed": False,
            "shot_contract": shot_contract,
            "generation_request": request,
            "script": {"scene_id": scene_id, "speaker": "CHAR_COUNTER" if speaker == "黑雨" else "CHAR_MAIN", "dialogue_text": dialogue, "emotion": "grief" if idx < 5 else "concern", "line_locked": True, "tts_duration_seconds": None, "audio_status": "AUDIO_PENDING" if dialogue else "NO_DIALOGUE"},
            "camera": shot["camera"] | {"first_frame_kind": "scene_action_anchor"},
            "edit": {"duration_seconds": duration, "render_seconds": 6, "duration_source": "PENDING_TTS" if dialogue else "silent_action_editorial_floor", "cut_after_performance": True, "transition_reason": "cut after performance and recovery hold"},
            "performance": {"emotion_goal": shot["emotion_change"], "action_beats": shot["action_beats"], "sound_cues": ["dialogue" if dialogue else "room tone", "single prop foley"]},
            "assets": {"identity_reference": identity, "identity_reference_metadata": asset_refs["char_counter" if speaker == "黑雨" else "char_main"], "scene_action_anchor": anchor, "scene_action_anchor_metadata": asset_refs[sid.lower()], "costume": "陆凡固定迷彩服；黑雨固定深色无品牌便装", "props": ["乱石坟头", "青苔木板墓牌", "两瓶五十年陈酿"], "lighting": "原文未说明；克制自然光适配", "space": "荒山孤坟"},
            "recovery": {"max_attempts": 2, "retry_delay_policy": "Retry-After first; otherwise >=60s provider cooldown", "degrade_order": ["retry with seed offset", "manual replacement marker retaining failure evidence"]},
        })
    contract = {
        "contract_version": "video_kingdom.six_module_shot_contract.idea_compiler.v3_strict_source",
        "production_boundary": "RESEARCH_ONLY", "project_id": project.name, "quality_mode": "FORMAL",
        "premise": "严格按《龙门战神》第一章物理行11–35还原墓前段落，不补写后文",
        "causal_chain": [x[2] for x in SHOT_SPECS], "plants": ["陆山河之墓木板", "两瓶五十年陈酿", "陆凡伤未好"], "payoffs": ["黑雨搀扶收束"],
        "viewer_knowledge_checkpoints": ["观众明确父子关系", "观众看见祭酒与悔恨", "观众理解咳嗽与搀扶因果"],
        "shots": sidecars, "timing_policy": "tts_first; measured dialogue plus 0.6s recovery hold; silent actions use explicit editorial floor", "generation_contract": generation_contract,
        "source_anchor": {"path": str(SOURCE), "sha256": digest, "line_range": [11, 35], "byte_range": [357, 1392], "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(), "excerpt": excerpt},
    }
    plan = {
        "schema": "video_kingdom.idea_pipeline_plan.v2_strict_source", "project_id": project.name, "status": "COMPILED", "title": "《龙门战神》墓前段落·原文严格还原测试片",
        "scope": "FREE_ZONE_RESEARCH_ONLY", "production_integration": False, "quality_mode": "FORMAL", "source_rights_note": "用户本地小说库；仅用于本地研究测试，严格绑定原文行/字节锚点",
        "source_anchor": contract["source_anchor"], "story": {"root_brief": {"theme": "父子悔恨与迟到的祭奠", "relationship_and_conflict": "陆凡与已故父亲陆山河的父子关系；黑雨为随行照护者", "mainline_events": [x[2] for x in SHOT_SPECS], "source_rights_note": "local_user_library_exact_excerpt", "semantic_anchor_type": "tomb_wine_cough_support"}, "scene_nodes": [{"scene_id": x[1], "title": x[2]} for x in SHOT_SPECS]},
        "assets": {"characters": [{"asset_id": "CHAR_MAIN", "name": "陆凡", "status": "APPROVED_REFERENCE_SHEET", "reference": asset_refs["char_main"], "dossier_path": "assets/char_main_dossier.json"}, {"asset_id": "CHAR_COUNTER", "name": "黑雨", "status": "APPROVED_REFERENCE_SHEET", "reference": asset_refs["char_counter"], "dossier_path": "assets/char_counter_dossier.json"}], "scenes": [{"asset_id": x[1], "name": x[2], "status": "APPROVED_REFERENCE_SHEET", "reference": asset_refs[x[0].lower()]} for x in SHOT_SPECS], "props": [{"asset_id": "PROP_WINE", "name": "两瓶五十年陈酿与酒杯", "status": "APPROVED_REFERENCE_SHEET", "reference": asset_refs["prop_wine"]}, {"asset_id": "PROP_TOMB", "name": "乱石坟头与青苔木板墓牌", "status": "APPROVED_REFERENCE_SHEET", "reference": asset_refs["prop_tomb"]}]},
        "six_module_contract": "six_module_contract.json", "generation_contract": generation_contract, "render_defaults": {"model": "agnes-video-v2.0", "seconds": 6, "width": 704, "height": 1280, "num_frames": 49, "frame_rate": 8, "duration_source": "per_shot_tts_measurement"}, "shots": shots, "acceptance": {"duration_window_seconds": [28, 32], "must_have_receipts": True, "must_pass_media_integrity": True, "must_pass_director_semantic_review": True}, "renderer_routing": {"mainline_identity_requires": "VERIFIED_REFERENCE_CONTROLLED_RENDERER", "agnes_video_v2_0": "LEAF_SHOTS_ONLY_UNTIL_REFERENCE_CONTROL_IS_EVIDENCED"},
    }
    for char, role in (("char_main", "陆凡；陆山河之子"), ("char_counter", "黑雨；随行照护者")):
        cid = "CHAR_MAIN" if char == "char_main" else "CHAR_COUNTER"
        _write_json(project / "assets" / f"{char}_dossier.json", {"schema": "video_kingdom.character_dossier.v1", "character_id": cid, "name": "陆凡" if char == "char_main" else "黑雨", "role": role, "fictional_character": True, "production_integration": False, "rights_and_provenance": {"source": "user_local_novel_research", "disallowed_sources": ["UNAUTHORIZED_REAL_PERSON_LIKENESS"]}, "identity_invariants": {"visual": generation_contract["character_identity_lock"], "negative_constraints": generation_contract["forbidden_behavior"], "behavioral": "只执行当前镜头合同动作，不自主导演", "relational": role}, "allowed_evolution": {"may_change": ["emotion", "pose", "prop_state"], "requires_new_dossier_version": True}, "visual_assets": [{"anchor_id": char, "reference": asset_refs[char]} ]})
    _write_json(project / "episode_plan.json", plan); _write_json(project / "six_module_contract.json", contract)
    return plan


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_longmen_strict_plan.py PROJECT_DIR")
    p = Path(sys.argv[1]).resolve()
    _generate_assets(p)
    plan = build(p)
    print(json.dumps({"status": "COMPILED", "project": str(p), "shots": len(plan["shots"]), "source_sha256": plan["source_anchor"]["sha256"]}, ensure_ascii=False))
