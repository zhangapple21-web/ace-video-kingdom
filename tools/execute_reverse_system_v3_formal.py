"""Generate the locked v3 shots in reference mode and bind receipts to the formal Run."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "episodes" / "generated" / "reverse_system_human_v3_20260907"
PLAN = PROJECT / "episode_plan.json"
EXEC = PROJECT / "formal_execution"
MANIFEST = EXEC / "manifest.json"
RUN_ID = "run_"  # filled from control receipt
OWNER = "codex:01a079c2-79f1-7111-b708-218461c6496d"
ACTION_ID = "reverse_system_v3_formal_generation_20260907"

def bind_manifest() -> None:
    if not MANIFEST.is_file():
        return
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if isinstance(rows, dict): rows = [rows]
    run = json.loads((PROJECT / ".control" / "formal_run.json").read_text(encoding="utf-8"))
    for row in rows:
        row["run_id"] = run["run_id"]
        row["action_id"] = ACTION_ID
        row["executor_owner"] = OWNER
    MANIFEST.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main() -> int:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    EXEC.mkdir(parents=True, exist_ok=True)
    ordered = list(plan["shots"][0]["render"]["reference_image_urls"])
    for shot in plan["shots"]:
        output = EXEC / f"{shot['shot_id']}.mp4"
        cmd = [sys.executable, str(ROOT / "tools" / "run_short_clip.py"), "--shot-id", shot["shot_id"], "--prompt", shot["prompt"], "--episode-contract", str(PLAN), "--manifest", str(MANIFEST), "--output", str(output), "--timeout", "900", "--model", "agnes-video-2.5-flash", "--seconds", str(shot["render"]["seconds"]), "--size", "720P", "--aspect-ratio", "9:16", "--flash-mode", "reference", "--admission-scope", "production"]
        for url in ordered: cmd += ["--flash-reference-image-url", url]
        print(json.dumps({"status": "SHOT_START", "shot_id": shot["shot_id"]}, ensure_ascii=False), flush=True)
        code = subprocess.run(cmd, cwd=ROOT).returncode
        bind_manifest()
        if code:
            print(json.dumps({"status": "STOPPED", "shot_id": shot["shot_id"], "returncode": code}, ensure_ascii=False), flush=True)
            return code
    bind_manifest()
    print(json.dumps({"status": "FORMAL_SHOTS_COMPLETED", "manifest": str(MANIFEST), "shots": len(plan["shots"])}, ensure_ascii=False), flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
