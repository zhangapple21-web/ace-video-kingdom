"""Build the one-shot E/S05 Shot Core fixture after the asset gate is READY."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets" / "library" / "task_assets" / "E_S05_HARDENING_20260906"
OUT_DIR = ROOT / "episodes" / "generated" / "E_S05_HARDENING_20260906"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    asset_dir = root / "assets" / "library" / "task_assets" / "E_S05_HARDENING_20260906"
    out_dir = root / "episodes" / "generated" / "E_S05_HARDENING_20260906"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "research" / "E_S05_shotcore_manifest.v1.json"
    fixture_path = root / "research" / "E_S05_shotcore_fixture.v1.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")).get("takes"):
        raise SystemExit("refusing to reuse a non-empty E/S05 manifest")

    refs = [
        ("identity_lufan_v1", "character", "1", "CHAR_LUFAN_THREE_VIEW_V2.png"),
        ("CHAR_LUFAN_FACE_EXPRESSION_V1", "character", "1", "CHAR_LUFAN_FACE_EXPRESSION_V1.png"),
        ("SCN_MOUNTAIN_GRAVE", "scene", "2", "SCN_MOUNTAIN_GRAVE_MULTI_VIEW_V2.png"),
        ("PROP_WINE_SINGLE_BOTTLE", "prop", "2", "PROP_WINE_SINGLE_BOTTLE_V2.png"),
    ]
    asset_refs = []
    for asset_id, asset_type, version, filename in refs:
        path = asset_dir / filename
        if not path.exists():
            raise SystemExit(f"missing locked asset: {path}")
        asset_refs.append({
            "asset_id": asset_id,
            "asset_type": asset_type,
            "version": int(version),
            "sha256": digest(path),
            "scope": "E_S05_HARDENING",
            "provider_ref": {
                "path": str(path.resolve()),
                "sha256": digest(path),
                "size_bytes": path.stat().st_size,
            },
        })

    shot = {
        "episode_id": "E_S05_HARDENING",
        "scene_id": "SCN_MOUNTAIN_GRAVE",
        "aspect_ratio": "9:16",
        "shot_id": "S05A",
        "shot_type": "ACTION",
        "provider_mode": "reference",
        "provider_asset_ids": [ref["asset_id"] for ref in asset_refs],
        "visible_character_ids": ["identity_lufan_v1"],
        "visible_prop_ids": ["PROP_WINE_SINGLE_BOTTLE"],
        "prompt": (
            "Realistic restrained memorial scene in an open barren mountain graveyard. "
            "Use the attached identity, scene, face and prop boards as hidden production references; "
            "do not render their labels, diagrams, borders, or text. One adult Chinese man, Lu Fan, "
            "wearing the same dark green digital camouflage uniform, seen from a fixed side-back "
            "medium-long view. He stands left of the fixed tombstone on the right. He begins with his "
            "back to camera and one bottle in his right hand at waist-to-lower-chest height. Slowly "
            "raise that single bottle 10–15 cm toward the tombstone, then keep the bottle neck slightly "
            "up in a restrained toast for at least two seconds. Natural breathing, faint cloth rustle, "
            "dry wind. Muted earth and slate palette, soft overcast daylight, realistic texture."
        ),
        "negative_prompt": (
            "drinking, pouring, spilling, waving the bottle, turning around, looking at camera, "
            "extra people, second bottle, glass, flowers, rain, changed tombstone, changed camera angle, "
            "zoom, pan, tilt, orbit, internal cut, shot-size change, text, subtitles, logo, watermark, "
            "fake characters, halo, bloom, promotional light, cartoon, anime, beauty filter, face swap, "
            "deformed hands, fused fingers, flicker, jump cuts"
        ),
        "intent": {
            "dramatic_function": "restrained memorial beat",
            "primary_visual_event": "slowly raise one bottle toward the tombstone",
            "story_delta": "Lu Fan completes a quiet toast without verbal declaration",
            "emotion_delta": "contained grief remains controlled and private",
            "knowledge_delta": "the audience sees the ritual action, not a new plot fact",
            "relationship_delta": "Lu Fan remains alone with the grave; no new character enters",
        },
        "state": {
            "start_state": {"character": "Lu Fan back to camera", "location": "left of fixed tombstone", "wardrobe": "locked digital camouflage uniform", "prop": "one bottle at waist-chest band", "camera": "fixed side-back"},
            "action_state": {"character": "only right arm and bottle rise slowly 10-15 cm", "location": "unchanged", "wardrobe": "unchanged", "prop": "single bottle axis stable", "camera": "fixed side-back"},
            "end_state": {"character": "back to camera, still", "location": "unchanged", "wardrobe": "unchanged", "prop": "neck slightly raised, toast held", "camera": "fixed side-back"},
        },
        "contract": {
            "first_frame_ref": None,
            "last_frame_ref": None,
            "allowed_behaviors": ["natural breathing", "slow bottle raise", "two-second restrained hold"],
            "forbidden_behaviors": ["drink", "pour", "spill", "wave", "turn", "look at camera", "new character", "move tombstone", "pan", "tilt", "zoom", "orbit", "internal cut", "text", "logo", "watermark", "halo"],
            "camera": {"scale": "medium_long", "position": "side_back", "movement": "NONE", "axis": "Lu Fan left / tombstone right; locked", "internal_cuts": 0},
            "render_seconds": 9,
        },
        "audio": {
            "dialogue": [], "narration": [], "sfx": [], "ambience": ["dry mountain wind", "cloth rustle", "quiet breathing"], "music": [],
            "dialogue_duration": 0, "action_duration": 4.0, "hold_duration": 3.0, "render_seconds": 9,
        },
        "asset_refs": asset_refs,
        "require_negative_prompt": True,
        "media_profile": {"expected_seconds": 9, "expected_aspect_ratio": "9:16", "expected_internal_cuts": 0, "requires_audio": True},
    }
    fixture = {
        "schema": "video_kingdom.e_s05_shotcore_fixture.v1",
        "production_boundary": "E_S05_HARDENING_ONE_SHOT_ONLY",
        "provider": "agnes-video-2.5-flash",
        "asset_gate_receipt": "assets/index/E_S05_asset_gate_receipt.v1.json",
        "shots": [shot],
    }
    fixture_path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {"schema": "video_kingdom.e_s05_shotcore_manifest.v1", "shots": {}, "takes": [], "events": [], "manifest_revision": 0}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "research" / "E_S05_shotcore_admission_plan.v1.md").write_text(
        "# E/S05 Shot Core 一次性提交计划\n\n"
        "- 资产门：READY（任务范围）\n"
        "- 模式：`NEW_ONE_TIME_SUBMISSION`；不恢复旧 S05 video_id\n"
        "- Shot Core：只提交 S05A，9 秒，9:16，reference mode，固定侧后方机位\n"
        "- 资产：identity_lufan_v1 / SCN_MOUNTAIN_GRAVE / PROP_WINE_SINGLE_BOTTLE\n"
        "- 生成后：必须通过画面、动作、摄影、连续性、导演五层门禁；失败停在候选态\n",
        encoding="utf-8",
    )
    print(json.dumps({"fixture": fixture_path.as_posix(), "manifest": manifest_path.as_posix(), "output_dir": out_dir.as_posix(), "shot_id": "S05A"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
