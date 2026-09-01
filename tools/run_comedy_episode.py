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


def _append_option(command: list[str], flag: str, value: object | None) -> None:
    if value is not None and value != "":
        command.extend([flag, str(value)])


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
    defaults = episode.get("render_defaults", {})
    if not isinstance(defaults, dict):
        raise SystemExit("render_defaults must be an object when supplied")
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
        render = {**defaults, **(shot.get("render", {}) if isinstance(shot.get("render"), dict) else {})}
        image = render.get("image")
        if image:
            image_path = (args.episode.parent / image).resolve() if not str(image).startswith(("http://", "https://", "data:")) else image
            _append_option(command, "--image", image_path)
        for field, flag in (
            ("width", "--width"), ("height", "--height"), ("num_frames", "--num-frames"),
            ("frame_rate", "--frame-rate"), ("seed", "--seed"),
            ("negative_prompt", "--negative-prompt"),
        ):
            _append_option(command, flag, render.get(field))
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
