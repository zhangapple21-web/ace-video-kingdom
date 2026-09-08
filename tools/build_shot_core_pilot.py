"""Create the four-shot controlled Shot Core production pilot fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PUBLIC = "https://raw.githubusercontent.com/zhangapple21-web/-/main/ace-video-kingdom/wenji-episode-006/"


def asset(asset_id: str, path: Path, provider_ref: str, asset_type: str = "scene") -> dict:
    return {"asset_id": asset_id, "asset_type": asset_type, "version": 1, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "scope": "episode", "provider_ref": provider_ref}


def make_shots(root: Path) -> list[dict]:
    anchors = root / "media_staging/episode_006_wenji_110s/anchors"
    audio = root / "media_staging/episode_006_wenji_110s/audio"
    common = {"episode_id": "SHOT_CORE_PILOT", "scene_id": "PILOT", "aspect_ratio": "9:16"}
    return [
        {
            **common, "shot_id": "PILOT_DIALOGUE", "shot_type": "DIALOGUE", "provider_mode": "reference", "prompt": "Wenji quietly finishes one short line in a dim desk room; a single continuous locked-off shot, no extra movement, no cut.",
            "intent": {"dramatic_function": "reveal", "primary_visual_event": "Wenji finishes one line and holds", "story_delta": "the hidden note is acknowledged", "emotion_delta": "uncertain to focused", "knowledge_delta": "viewer learns the note matters", "relationship_delta": "none"},
            "state": {"start_state": {"character": "WENJI", "location": "desk", "wardrobe": "unchanged", "props": ["phone"], "lighting": "dim", "time": "night", "camera": "medium"}, "action_state": {"character": "WENJI speaks", "location": "desk", "wardrobe": "unchanged", "props": ["phone"], "lighting": "dim", "time": "night", "camera": "locked"}, "end_state": {"character": "WENJI holds gaze", "location": "desk", "wardrobe": "unchanged", "props": ["phone"], "lighting": "dim", "time": "night", "camera": "locked"}},
            "contract": {"first_frame_ref": None, "last_frame_ref": None, "allowed_behaviors": ["speak", "hold"], "forbidden_behaviors": ["pan", "tilt", "zoom", "orbit", "internal cut", "new character"], "camera": {"scale": "medium", "position": "desk", "movement": "NONE", "axis": "none", "internal_cuts": 0}, "render_seconds": 5},
            "audio": {"dialogue": [{"speaker": "WENJI", "content": "我先把这页记下来。", "start": 0, "end": 2.021, "audio_ref": str(audio / "wenji_01.wav")}], "narration": [], "sfx": [], "ambience": ["room_tone"], "music": [], "dialogue_duration": 2.021, "action_duration": 0, "hold_duration": 0.8, "render_seconds": 5},
            "asset_refs": [asset("SCENE_02", anchors / "SCENE_02_typing_log_anchor.png", PUBLIC + "SCENE_02_typing_log_anchor.png")], "visible_character_ids": ["WENJI"], "visible_prop_ids": ["PHONE"],
        },
        {
            **common, "shot_id": "PILOT_ACTION", "shot_type": "ACTION", "provider_mode": "keyframe", "prompt": "A hand closes the folder once, then rests; one single readable action with natural recovery, no additional actions, no cut.",
            "intent": {"dramatic_function": "commit", "primary_visual_event": "hand closes the folder", "story_delta": "the record is secured", "emotion_delta": "hesitation to resolve", "knowledge_delta": "viewer sees the record is preserved", "relationship_delta": "none"},
            "state": {"start_state": {"character": "WENJI", "location": "desk", "wardrobe": "unchanged", "props": ["folder open"], "lighting": "cool", "time": "night", "camera": "close"}, "action_state": {"character": "hand closes folder", "location": "desk", "wardrobe": "unchanged", "props": ["folder closing"], "lighting": "cool", "time": "night", "camera": "close"}, "end_state": {"character": "hand leaves folder", "location": "desk", "wardrobe": "unchanged", "props": ["folder closed"], "lighting": "cool", "time": "night", "camera": "close"}},
            "contract": {"first_frame_ref": PUBLIC + "SCENE_05_phone_close_anchor.png", "last_frame_ref": PUBLIC + "SCENE_06_consultation_lobby_anchor.png", "allowed_behaviors": ["close folder", "recover", "hold"], "forbidden_behaviors": ["open folder again", "walk", "camera cut", "new character"], "camera": {"scale": "close", "position": "desk", "movement": "CONTROLLED", "axis": "none", "internal_cuts": 0}, "render_seconds": 6},
            "audio": {"dialogue": [], "narration": [], "sfx": [{"id": "folder_close", "start": 1.5, "end": 2}], "ambience": ["room_tone"], "music": [], "dialogue_duration": 0, "action_duration": 2.5, "hold_duration": 0.8, "render_seconds": 6},
            "asset_refs": [asset("SCENE_05", anchors / "SCENE_05_phone_close_anchor.png", PUBLIC + "SCENE_05_phone_close_anchor.png"), asset("SCENE_06", anchors / "SCENE_06_consultation_lobby_anchor.png", PUBLIC + "SCENE_06_consultation_lobby_anchor.png")], "visible_character_ids": ["WENJI"], "visible_prop_ids": ["FOLDER"],
        },
        {
            **common, "shot_id": "PILOT_IDENTITY", "shot_type": "REACTION", "provider_mode": "reference", "prompt": "Wenji looks at the phone, remains the same person and wardrobe, then lowers her eyes; one restrained reaction, no new people, no cut.",
            "intent": {"dramatic_function": "reaction", "primary_visual_event": "Wenji lowers her eyes after reading", "story_delta": "the message lands", "emotion_delta": "hope to caution", "knowledge_delta": "viewer sees the warning affects her", "relationship_delta": "none"},
            "state": {"start_state": {"character": "WENJI", "location": "lobby", "wardrobe": "unchanged", "props": ["phone"], "lighting": "fluorescent", "time": "day", "camera": "medium"}, "action_state": {"character": "WENJI reads phone", "location": "lobby", "wardrobe": "unchanged", "props": ["phone"], "lighting": "fluorescent", "time": "day", "camera": "locked"}, "end_state": {"character": "WENJI lowers eyes", "location": "lobby", "wardrobe": "unchanged", "props": ["phone"], "lighting": "fluorescent", "time": "day", "camera": "locked"}},
            "contract": {"first_frame_ref": None, "last_frame_ref": None, "allowed_behaviors": ["read phone", "lower eyes", "hold"], "forbidden_behaviors": ["new person", "wardrobe change", "walk away", "camera movement", "internal cut"], "camera": {"scale": "medium", "position": "lobby", "movement": "NONE", "axis": "none", "internal_cuts": 0}, "render_seconds": 5},
            "audio": {"dialogue": [], "narration": [], "sfx": ["phone_vibration"], "ambience": ["lobby_tone"], "music": [], "dialogue_duration": 0, "action_duration": 2.5, "hold_duration": 1, "render_seconds": 5},
            "asset_refs": [asset("SCENE_06", anchors / "SCENE_06_consultation_lobby_anchor.png", PUBLIC + "SCENE_06_consultation_lobby_anchor.png")], "visible_character_ids": ["WENJI"], "visible_prop_ids": ["PHONE"],
        },
        {
            **common, "shot_id": "PILOT_REWORK", "shot_type": "ACTION", "provider_mode": "reference", "prompt": "A hand moves the phone from the left side of the desk to the right side in one continuous motion and stops; deliberately ignore any extra movement, no cut.",
            "intent": {"dramatic_function": "test_rework", "primary_visual_event": "hand moves phone once", "story_delta": "phone position changes", "emotion_delta": "neutral", "knowledge_delta": "none", "relationship_delta": "none"},
            "state": {"start_state": {"character": "WENJI", "location": "desk", "wardrobe": "unchanged", "props": ["phone left"], "lighting": "cool", "time": "night", "camera": "close"}, "action_state": {"character": "hand moves phone", "location": "desk", "wardrobe": "unchanged", "props": ["phone center"], "lighting": "cool", "time": "night", "camera": "close"}, "end_state": {"character": "hand leaves phone", "location": "desk", "wardrobe": "unchanged", "props": ["phone right"], "lighting": "cool", "time": "night", "camera": "close"}},
            "contract": {"first_frame_ref": None, "last_frame_ref": None, "allowed_behaviors": ["move phone once", "hold"], "forbidden_behaviors": ["pick up phone", "open screen", "new character", "internal cut"], "camera": {"scale": "close", "position": "desk", "movement": "NONE", "axis": "none", "internal_cuts": 0}, "render_seconds": 5},
            "audio": {"dialogue": [], "narration": [], "sfx": [], "ambience": ["room_tone"], "music": [], "dialogue_duration": 0, "action_duration": 2.5, "hold_duration": 1, "render_seconds": 5},
            "asset_refs": [asset("SCENE_02", anchors / "SCENE_02_typing_log_anchor.png", PUBLIC + "SCENE_02_typing_log_anchor.png")], "visible_character_ids": ["WENJI"], "visible_prop_ids": ["PHONE"],
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = {"schema": "video_kingdom.shot_core_pilot.v1", "production_boundary": "CONTROLLED_PRODUCTION_TEST", "provider": "agnes-video-2.5-flash", "shots": make_shots(args.root)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "shots": len(payload["shots"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
