"""Run one explicit, finite short-drama plan through the durable clip utility.

This is a manual episode executor, not a scheduler: it has no clock, daemon,
or task-discovery authority. It stops on a failed shot and leaves the durable
manifest intact for an operator or later Free Zone turn to resume.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--media-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=480)
    args = parser.parse_args()
    episode = json.loads(args.episode.read_text(encoding="utf-8"))
    shots = episode.get("shots", [])
    if not shots:
        raise SystemExit("episode has no shots")
    args.media_dir.mkdir(parents=True, exist_ok=True)
    shot_ids: list[str] = []
    for shot in shots:
        shot_id, prompt = shot.get("shot_id"), shot.get("prompt")
        if not shot_id or not prompt:
            raise SystemExit("every episode shot requires shot_id and prompt")
        shot_ids.append(shot_id)
        command = [
            sys.executable, "tools/run_short_clip.py", "--shot-id", shot_id,
            "--prompt", prompt, "--manifest", str(args.manifest), "--output",
            str(args.media_dir / f"{shot_id}.mp4"), "--timeout", str(args.timeout),
        ]
        result = subprocess.run(command)
        if result.returncode:
            print(json.dumps({"status": "STOPPED", "failed_shot": shot_id}, ensure_ascii=False))
            return result.returncode
    duration_window = episode.get("acceptance", {}).get("duration_window_seconds", [45, 60])
    result = subprocess.run([
        sys.executable, "tools/assemble_episode.py", "--manifest", str(args.manifest),
        "--shot-ids", *shot_ids, "--output", str(args.output), "--min-seconds",
        str(duration_window[0]), "--max-seconds", str(duration_window[1]),
    ])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
