"""Import a DramaAI or FastMovieAI export into the Video Kingdom control plane.

This is an intake adapter, not a second runtime.  It converts a local
workbench export into a hash-bound ``workbench_intake.v1.json`` plus an
episode plan and six-module sidecar that the existing preflight can inspect.
Missing contracts (TTS, approved anchors, locked dialogue) stay pending and
are never replaced with placeholders or synthetic provider receipts.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "video_kingdom.workbench_intake.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _slug(value: str) -> str:
    return (re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", value).strip("-").lower() or "imported-workbench")[:64]


def _first(value: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        candidate = value.get(key)
        if candidate not in (None, "", []):
            return candidate
    return default


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


def _seconds(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    # FastMovieAI stores storyboard duration in milliseconds.
    if number > 60:
        number /= 1000
    return round(number, 3)


def _materialize_asset(item: dict[str, Any], root: Path, assets_dir: Path, prefix: str) -> dict[str, Any]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    asset_id = str(_first(item, "id", "assetId", "asset_id", default=f"{prefix}_{len(list(assets_dir.iterdir()))+1}"))
    name = str(_first(item, "name", "filename", "fileName", default=asset_id))
    mime = str(_first(item, "mimeType", "mime_type", "type", default="application/octet-stream"))
    raw = item.get("blobBase64") or item.get("blob_base64") or item.get("base64")
    source = _first(item, "path", "filePath", "file_path", "url", "src", "headimg", "three_view_image", "icon", "image")
    suffix = mimetypes.guess_extension(mime) or Path(str(source or name)).suffix or ".bin"
    target = assets_dir / f"{_slug(asset_id)}{suffix}"
    materialized = False
    if isinstance(raw, str) and raw:
        try:
            target.write_bytes(base64.b64decode(raw, validate=True))
            materialized = True
        except (ValueError, base64.binascii.Error):
            pass
    elif isinstance(source, str) and source and not re.match(r"^https?://", source):
        candidate = (root / source).resolve() if not Path(source).is_absolute() else Path(source).resolve()
        if candidate.is_file():
            shutil.copyfile(candidate, target)
            materialized = True
    result: dict[str, Any] = {
        "source_id": asset_id,
        "name": name,
        "mime_type": mime,
        "source_ref": source,
        "materialized_path": str(target.relative_to(assets_dir.parent)).replace("\\", "/") if materialized else None,
        "materialized": materialized,
    }
    if materialized:
        result["sha256"] = _sha256(target)
    return result


def _dramai(payload: dict[str, Any], source: Path, out: Path) -> dict[str, Any]:
    projects = _as_list(payload.get("projects"))
    project = projects[0] if projects else {}
    project_id = str(_first(project, "id", default=_slug(source.stem)))
    title = str(_first(project, "title", "name", default=project_id))
    chars = _as_list(payload.get("characters"))
    storyboards = sorted(_as_list(payload.get("storyboards")), key=lambda x: int(x.get("sequence", 0) or 0) if isinstance(x, dict) else 0)
    assets = _as_list(payload.get("assets"))
    assets_dir = out / "assets"
    asset_rows = [_materialize_asset(row, source.parent, assets_dir, "dramai") for row in assets if isinstance(row, dict)]
    asset_by_id = {row["source_id"]: row for row in asset_rows}
    char_rows: list[dict[str, Any]] = []
    for index, char in enumerate(chars, 1):
        if not isinstance(char, dict):
            continue
        cid = str(_first(char, "id", default=f"CHAR_{index:02d}"))
        ref_id = _first(char, "referenceAssetId", "reference_asset_id")
        ref = asset_by_id.get(str(ref_id)) if ref_id else None
        char_rows.append({"asset_id": cid, "name": _first(char, "name", default=cid), "role": _first(char, "role", default="supporting"), "reference": ref, "locked": bool(char.get("locked"))})
    shots: list[dict[str, Any]] = []
    missing: list[str] = []
    for index, row in enumerate(storyboards, 1):
        if not isinstance(row, dict):
            continue
        source_sid = str(_first(row, "id", default=f"S{index:02d}A"))
        sid = f"S{index:02d}A"
        text = str(_first(row, "sceneText", "scene_text", "description", default=""))
        narration = str(_first(row, "narration", "dialogue", default=""))
        image_id = _first(row, "imageAssetId", "image_asset_id")
        image = asset_by_id.get(str(image_id)) if image_id else None
        if not text:
            missing.append(f"{sid}:scene_text")
        if not narration:
            missing.append(f"{sid}:locked_dialogue")
        if not image or not image.get("materialized"):
            missing.append(f"{sid}:scene_action_anchor")
        duration = _seconds(_first(row, "durationSec", "duration_sec"))
        shot = _shot(sid, f"SC{index:02d}", text, narration, _first(row, "imagePrompt", "image_prompt", default=text), duration, image, [str(x) for x in _as_list(row.get("characterIds"))])
        shot["source_shot_id"] = source_sid
        shots.append(shot)
    return _package("dramai", source, project_id, title, char_rows, shots, asset_rows, missing, out)


def _find_rows(root: dict[str, Any], names: tuple[str, ...]) -> list[dict[str, Any]]:
    for name in names:
        value = root.get(name)
        rows = [x for x in _as_list(value) if isinstance(x, dict)]
        if rows:
            return rows
    data = root.get("data")
    if isinstance(data, dict):
        return _find_rows(data, names)
    return []


def _fastmovie(payload: dict[str, Any], source: Path, out: Path) -> dict[str, Any]:
    project = _first(payload, "drama", "project", default={})
    if not isinstance(project, dict):
        project = {}
    project_id = str(_first(project, "id", "drama_id", "project_id", default=_slug(source.stem)))
    title = str(_first(project, "title", "name", "drama_name", default=project_id))
    actors = _find_rows(payload, ("actors", "characters", "actor"))
    storyboards = _find_rows(payload, ("storyboards", "storyboard", "shots", "shot"))
    scenes = _find_rows(payload, ("scenes", "scene"))
    props = _find_rows(payload, ("props", "properties", "props_list"))
    assets_dir = out / "assets"
    asset_rows: list[dict[str, Any]] = []
    for group, rows in (("actor", actors), ("scene", scenes), ("prop", props)):
        for row in rows:
            asset_rows.append(_materialize_asset(row, source.parent, assets_dir, group))
    shots: list[dict[str, Any]] = []
    missing: list[str] = []
    for index, row in enumerate(storyboards, 1):
        source_sid = str(_first(row, "shot_id", "id", "storyboard_id", default=f"S{index:02d}A"))
        sid = f"S{index:02d}A"
        scene_id = str(_first(row, "scene_id", "sceneId", default=f"SC{index:02d}"))
        text = str(_first(row, "description", "scene_description", "content", "画面描述", default=""))
        dialogues = _as_list(_first(row, "dialogues", "dialogue", "台词", default=[]))
        raw_dialogue = _first(row, "dialogues", "dialogue", "台词", default=None)
        if isinstance(raw_dialogue, str):
            dialogue = raw_dialogue.strip()
        elif dialogues:
            dialogue = " ".join(str(_first(d, "text", "content", "dialogue", default="")) for d in dialogues if isinstance(d, dict)).strip()
        else:
            dialogue = str(_first(row, "narration", "voice_text", "旁白", default=""))
        prompt = str(_first(row, "video_prompt", "prompt", "image_prompt", "首帧图提示词", default=text))
        duration = _seconds(_first(row, "duration", "duration_ms", "durationSec", default=None))
        ref = _first(row, "scene_action_anchor", "image", "image_url", "first_frame", default=None)
        ref_obj = {"source_id": f"{sid}_anchor", "source_ref": ref, "materialized": False}
        if isinstance(ref, str) and ref and not re.match(r"^https?://", ref):
            candidate = (source.parent / ref).resolve() if not Path(ref).is_absolute() else Path(ref).resolve()
            if candidate.is_file():
                target = assets_dir / f"{_slug(sid)}{candidate.suffix or '.png'}"
                shutil.copyfile(candidate, target)
                ref_obj.update(materialized=True, materialized_path=str(target.relative_to(out)).replace("\\", "/"), sha256=_sha256(target))
        if not text:
            missing.append(f"{sid}:scene_text")
        if not dialogue:
            missing.append(f"{sid}:locked_dialogue")
        if not ref:
            missing.append(f"{sid}:scene_action_anchor")
        shot = _shot(sid, scene_id, text, dialogue, prompt, duration, ref_obj, [str(x.get("actor_id")) for x in _as_list(row.get("actors")) if isinstance(x, dict) and x.get("actor_id")])
        shot["source_shot_id"] = source_sid
        shots.append(shot)
    return _package("fastmovieai", source, project_id, title, actors, shots, asset_rows, missing, out)


def _shot(sid: str, scene_id: str, scene_text: str, dialogue: str, prompt: str, duration: float | None, anchor: dict[str, Any] | None, character_ids: list[str]) -> dict[str, Any]:
    anchor_ref = anchor.get("materialized_path") if isinstance(anchor, dict) and anchor.get("materialized") else anchor.get("source_ref") if isinstance(anchor, dict) else None
    return {
        "shot_id": sid,
        "scene_id": scene_id,
        "prompt": prompt,
        "action_beats": [f"首态：{scene_text or '待补'}", f"动作：{scene_text or '待补'}", "末态：动作完成后保留反应与留白"],
        "required_asset_ids": character_ids,
        "first_state": scene_text or "待补",
        "action": scene_text or "待补",
        "last_state": "动作完成后保留反应与留白",
        "continuity_bridge_to_next": "待导演确认",
        "quality_gate": "抽帧无内部切镜、身份连续、动作完成、对白不截断",
        "camera": {"shot_type": "dialogue" if dialogue else "action", "scale": "medium shot", "movement": "FIXED_DIALOGUE" if dialogue else "ONE_PURPOSEFUL_MOVE", "axis": "screen-left facing screen-right", "movement_count": 0 if dialogue else 1},
        "dramatic_function": scene_text or "待补",
        "information_gain": dialogue or "待补",
        "emotion_change": "待导演确认",
        "anchor_reuse_allowed": False,
        "shot_contract": {"version": "ace.video_kingdom.single_action_shot_contract.v1", "single_action": True, "action_unit": scene_text or "待补", "max_primary_actions": 1, "internal_cuts_allowed": 0, "cut_policy": "cut only after action completion and recovery hold"},
        "render": {"model": "agnes-video-v2.0", "seconds": duration or 5, "width": 704, "height": 1280, "num_frames": int((duration or 5) * 8) + 1, "frame_rate": 8, "image": anchor_ref} if anchor_ref else {"model": "agnes-video-v2.0", "seconds": duration or 5, "width": 704, "height": 1280, "num_frames": int((duration or 5) * 8) + 1, "frame_rate": 8},
        "source_dialogue": dialogue,
    }


def _package(kind: str, source: Path, project_id: str, title: str, characters: list[dict[str, Any]], shots: list[dict[str, Any]], source_assets: list[dict[str, Any]], missing: list[str], out: Path) -> dict[str, Any]:
    char_assets = []
    for index, char in enumerate(characters, 1):
        cid = str(char.get("asset_id") or char.get("id") or f"CHAR_{index:02d}")
        ref = char.get("reference") if isinstance(char, dict) else None
        ref_path = ref.get("materialized_path") if isinstance(ref, dict) and ref.get("materialized") else None
        char_assets.append({"asset_id": cid, "name": char.get("name", cid), "status": "IMPORTED_REFERENCE_PENDING_REVIEW", "reference_path": ref_path, "source_ref": ref.get("source_ref") if isinstance(ref, dict) else None, "locked": bool(char.get("locked"))})
    scene_assets = []
    for shot in shots:
        image = shot.get("render", {}).get("image") if isinstance(shot.get("render"), dict) else None
        scene_assets.append({"asset_id": shot["scene_id"], "name": shot["scene_id"], "status": "IMPORTED_REFERENCE_PENDING_REVIEW", "reference_path": image, "sha256": None})
    contract_shots = []
    for shot in shots:
        dialogue = shot.get("source_dialogue", "")
        duration = shot.get("render", {}).get("seconds")
        contract_shots.append({"shot_id": shot["shot_id"], "source_scene": shot.get("action", ""), "script": {"scene_id": shot["scene_id"], "speaker": "UNKNOWN", "dialogue_text": dialogue, "emotion": "PENDING_DIRECTOR_REVIEW", "line_locked": bool(dialogue), "tts_duration_seconds": None, "audio_status": "AUDIO_PENDING"}, "camera": shot["camera"] | {"first_frame_kind": "scene_action_anchor"}, "edit": {"duration_seconds": duration, "duration_source": "IMPORTED_ESTIMATE" if duration else "PENDING_TTS", "cut_after_performance": True, "transition_reason": "cut after performance and recovery hold"}, "performance": {"emotion_goal": "PENDING_DIRECTOR_REVIEW", "action_beats": shot["action_beats"], "sound_cues": ["dialogue or room tone", "single prop foley"]}, "assets": {"identity_reference": None, "scene_action_anchor": shot.get("render", {}).get("image"), "costume": "PENDING_ASSET_REVIEW", "props": [], "lighting": "PENDING_DIRECTOR_REVIEW"}, "recovery": {"max_attempts": 2, "retry_delay_policy": "Retry-After first; otherwise >=60s provider cooldown", "degrade_order": ["retry with seed offset", "manual replacement marker retaining failure evidence"]}})
    contract = {"contract_version": "video_kingdom.six_module_shot_contract.workbench_import.v1", "production_boundary": "RESEARCH_ONLY", "project_id": project_id, "quality_mode": "INTAKE_PENDING", "premise": title, "causal_chain": [], "plants": [], "payoffs": [], "viewer_knowledge_checkpoints": [], "shots": contract_shots, "source_kind": kind}
    plan = {"schema": "video_kingdom.workbench_episode_plan.v1", "project_id": project_id, "status": "INTAKE_PENDING", "title": title, "scope": "FREE_ZONE_RESEARCH_ONLY", "production_integration": False, "source_rights_note": "Imported from a local workbench export; rights and reference approval must be reviewed before provider admission.", "story": {"root_brief": {"theme": "PENDING", "relationship_and_conflict": "PENDING", "mainline_events": [], "source_rights_note": "workbench_import", "semantic_anchor_type": "PENDING"}, "scene_nodes": [{"scene_id": s["scene_id"], "title": s["scene_id"]} for s in shots]}, "assets": {"characters": char_assets, "scenes": scene_assets, "props": []}, "six_module_contract": "six_module_contract.json", "render_defaults": {"model": "agnes-video-v2.0", "seconds": 5, "width": 704, "height": 1280, "num_frames": 41, "frame_rate": 8, "duration_source": "pending_tts"}, "shots": shots, "acceptance": {"duration_window_seconds": [15, 180], "must_have_receipts": True, "must_pass_media_integrity": True}, "renderer_routing": {"mainline_identity_requires": "VERIFIED_REFERENCE_CONTROLLED_RENDERER", "agnes_video_v2_0": "LEAF_SHOTS_ONLY_UNTIL_REFERENCE_CONTROL_IS_EVIDENCED"}}
    _write(out / "six_module_contract.json", contract)
    _write(out / "episode_plan.json", plan)
    intake = {"schema": SCHEMA, "source_kind": kind, "source_path": str(source), "source_sha256": _sha256(source), "created_at": datetime.now(timezone.utc).isoformat(), "project_id": project_id, "title": title, "production_integration": False, "status": "INTAKE_PENDING" if missing or not shots else "INTAKE_READY_FOR_REVIEW", "counts": {"characters": len(characters), "shots": len(shots), "source_assets": len(source_assets)}, "missing_requirements": sorted(set(missing)), "artifacts": {"episode_plan": "episode_plan.json", "six_module_contract": "six_module_contract.json"}}
    _write(out / "workbench_intake.v1.json", intake)
    return intake


def import_package(source: Path, out: Path, kind: str = "auto") -> dict[str, Any]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("source export must be a JSON object")
    resolved = "dramai" if kind == "auto" and payload.get("format") == "dramai-backup" else "fastmovieai" if kind == "auto" else kind
    if resolved == "dramai":
        if payload.get("format") != "dramai-backup":
            raise ValueError("DramaAI input must contain format=dramai-backup")
        return _dramai(payload, source.resolve(), out.resolve())
    if resolved == "fastmovieai":
        return _fastmovie(payload, source.resolve(), out.resolve())
    raise ValueError(f"unsupported kind: {resolved}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kind", choices=["auto", "dramai", "fastmovieai"], default="auto")
    args = parser.parse_args()
    if not args.source.is_file():
        print(json.dumps({"status": "BLOCKED", "reason": "source_missing"}, ensure_ascii=False))
        return 2
    try:
        result = import_package(args.source, args.output, args.kind)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
