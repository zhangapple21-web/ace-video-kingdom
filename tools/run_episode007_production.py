"""Durable sequential render for episode 007; resumes completed shot records.

No provider request may be made until the deterministic episode preflight is
READY or CONDITIONAL.  A technically complete MP4 is not a delivery if its
storyboard, identity anchors, or motion contract was blocked.
"""
from pathlib import Path
import json, subprocess, sys

root = Path(__file__).resolve().parents[1]
episode_path = root / "episodes/episode_007_virtual_data.v1.json"
preflight = root / "research/episode_007_preflight_runtime.json"
# Required pre-work memory step: inspect the prior cut before any provider
# request. This is read-only and never promotes a result automatically.
prior_audit = root / "research/episode_007_previous_cut_audit_latest.json"
audit = subprocess.run([
    sys.executable, str(root / "tools/audit_previous_cut.py"),
    "--root", str(root), "--output", str(prior_audit),
], cwd=root, check=False)
if audit.returncode:
    raise SystemExit(f"previous-cut audit failed; no provider request submitted. See {prior_audit}")
gate = subprocess.run([
    sys.executable, str(root / "tools/preflight_episode.py"),
    "--episode", str(episode_path),
    "--policy", str(root / "governance/short_drama_review_policy.v1.json"),
    "--output", str(preflight),
    "--require-formal",
], cwd=root, check=False)
if gate.returncode:
    raise SystemExit(
        "episode preflight is BLOCKED/REWORK; no provider request submitted. "
        f"See {preflight}"
    )
plan = json.loads(episode_path.read_text(encoding="utf-8"))
manifest = root / "experiments/episode_007_camera_grammar_tasks.v2.json"
outdir = root / "media_staging/episode_007_virtual_data/video_camera_grammar_v2"
outdir.mkdir(parents=True, exist_ok=True)
for shot in plan["shots"]:
    sid = shot["shot_id"]
    # Production camera grammar: dialogue stays locked; action gets one
    # deliberate move only after the performance is established.  Never use
    # a portrait as the motion first frame.
    base_prompt = shot["prompt"]
    is_dialogue = sid in {"S01C", "S02B", "S03A", "S04A", "S05A", "S06A"}
    if is_dialogue:
        camera_rule = "single continuous shot, locked-off tripod, same framing and focal length, no pan, no orbit, no tracking, no zoom; let the speaker finish the line and hold one beat before ending"
    else:
        camera_rule = "single continuous shot, one primary action only; establish preparation first, then force/impact, then natural inertia and recovery; one short motivated camera move at most, no compound moves, no early cut"
    prompt = f"{base_prompt}; {camera_rule}; scene-action first frame already contains the desk, props and body position; do not begin with an isolated portrait; cold oppressive realistic vertical 9:16"
    feige = {"S02A", "S02B", "S02C", "S03A", "S06A"}
    # Identity reference and action first frame are separate.  These four
    # scene-action anchors are the verified local fallback for v2.0.
    scene_anchor = {
        "S01A":"office_keyboard.png", "S01B":"office_keyboard.png",
        "S01C":"office_keyboard.png", "S01D":"office_phone_impact.png",
        "S02A":"manager_desk_impact.png", "S02B":"manager_desk_impact.png",
        "S02C":"manager_desk_impact.png", "S03A":"manager_desk_impact.png",
        "S03B":"manager_desk_impact.png", "S03C":"office_keyboard.png",
        "S04A":"office_keyboard.png", "S04B":"office_phone_impact.png",
        "S05A":"office_keyboard.png", "S05B":"office_phone_impact.png",
        "S05C":"office_phone_impact.png", "S06A":"manager_desk_impact.png",
        "S06B":"manager_desk_impact.png", "S07A":"night_copy_pullback.png"
    }[sid]
    anchor = root / "media_staging/episode_007_virtual_data/anchors/scene_action" / scene_anchor
    cmd=[sys.executable, str(root/"tools/run_short_clip.py"), "--shot-id", sid, "--prompt", prompt,
         "--episode-contract", str(episode_path), "--admission-scope", "production",
         "--manifest", str(manifest), "--output", str(outdir/f"{sid}.mp4"), "--model", "agnes-video-2.5-flash",
         "--image", str(anchor), "--width", "704", "--height", "1280", "--num-frames", "241", "--frame-rate", "24", "--timeout", "900"]
    result = subprocess.run(cmd, cwd=root, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)

