"""Execute the already-admitted human-dialogue episode and assemble a draft cut.

This runner only submits shots from the immutable episode plan.  It resumes a
completed provider record and refuses to overwrite an existing artifact.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "episodes" / "generated" / "reverse_system_human_20260907"
PLAN = PROJECT / "episode_plan.json"
EXEC = PROJECT / "provider_execution_human_v2"
MANIFEST = EXEC / "manifest.json"
MEDIA = EXEC


def main() -> int:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    MEDIA.mkdir(parents=True, exist_ok=True)
    for shot in plan["shots"]:
        shot_id = shot["shot_id"]
        output = MEDIA / f"{shot_id}.mp4"
        command = [sys.executable, str(ROOT / "tools" / "run_short_clip.py"), "--shot-id", shot_id, "--prompt", shot["prompt"], "--episode-contract", str(PLAN), "--manifest", str(MANIFEST), "--output", str(output), "--timeout", "600", "--model", shot["render"]["model"], "--seconds", str(shot["render"]["seconds"]), "--size", shot["render"]["size"], "--aspect-ratio", shot["render"]["aspect_ratio"], "--flash-mode", shot["render"]["flash_mode"], "--admission-scope", "production"]
        print(json.dumps({"status": "SHOT_START", "shot_id": shot_id}, ensure_ascii=False), flush=True)
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            print(json.dumps({"status": "STOPPED", "shot_id": shot_id, "returncode": result.returncode}, ensure_ascii=False), flush=True)
            return result.returncode
    concat = EXEC / "concat.txt"
    concat_lines = []
    for shot in plan["shots"]:
        media_path = (MEDIA / f"{shot['shot_id']}.mp4").as_posix()
        concat_lines.append(f"file '{media_path}'")
    concat.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    draft = PROJECT / "reverse_system_human_20260907_draft.mp4"
    result = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(draft)], cwd=ROOT)
    if result.returncode:
        return result.returncode
    print(json.dumps({"status": "DRAFT_ASSEMBLED", "path": str(draft), "shots": len(plan["shots"])}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
