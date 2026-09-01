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
import time
from pathlib import Path


def _append_option(command: list[str], flag: str, value: object | None) -> None:
    if value is not None and value != "":
        command.extend([flag, str(value)])


def _validate_asset_graph(shots: list[dict]) -> None:
    """Prevent accidental reuse of a scene's start image across a cut.

    Text-only episodes remain supported.  Once a plan chooses image-to-video,
    though, every shot must name a scene asset and two shots cannot silently
    share one unless the plan is explicitly a continuous action.
    """
    render_images: list[tuple[str, str, bool]] = []
    for shot in shots:
        render = shot.get("render", {}) if isinstance(shot.get("render"), dict) else {}
        image = render.get("image")
        if image:
            render_images.append((str(shot.get("shot_id", "unknown")), str(image), bool(shot.get("continuous_action"))))
    if not render_images:
        return
    if len(render_images) != len(shots):
        raise SystemExit("asset-first episode mixes image-backed and unanchored shots")
    seen: dict[str, tuple[str, bool]] = {}
    for shot_id, image, continuous_action in render_images:
        prior = seen.get(image)
        if prior and not (continuous_action and prior[1]):
            raise SystemExit(
                f"asset graph reuses start image for {prior[0]} and {shot_id}; "
                "set continuous_action=true on both only for one uninterrupted action"
            )
        seen[image] = (shot_id, continuous_action)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--media-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, help="optional local media-integrity review JSON")
    parser.add_argument("--timeout", type=int, default=480)
    parser.add_argument(
        "--shot-retry-rounds", type=int, default=2,
        help="additional durable resume rounds after a transient clip failure",
    )
    parser.add_argument(
        "--shot-retry-delay", type=int, default=60,
        help="seconds between durable resume rounds",
    )
    args = parser.parse_args()
    episode = json.loads(args.episode.read_text(encoding="utf-8"))
    shots = episode.get("shots", [])
    defaults = episode.get("render_defaults", {})
    if not isinstance(defaults, dict):
        raise SystemExit("render_defaults must be an object when supplied")
    if not shots:
        raise SystemExit("episode has no shots")
    if args.shot_retry_rounds < 0 or args.shot_retry_delay < 1:
        raise SystemExit("shot retry rounds must be >= 0 and retry delay must be >= 1")
    _validate_asset_graph(shots)
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
        for retry_round in range(1, args.shot_retry_rounds + 1):
            if not result.returncode:
                break
            print(json.dumps({
                "status": "RETRYING_DURABLE_SHOT",
                "shot_id": shot_id,
                "retry_round": retry_round,
                "retry_in_seconds": args.shot_retry_delay,
            }, ensure_ascii=False), flush=True)
            time.sleep(args.shot_retry_delay)
            # run_short_clip reads the persisted manifest first: a task that
            # received a video_id resumes polling instead of submitting a
            # duplicate provider request.
            result = subprocess.run(command)
        if result.returncode:
            print(json.dumps({"status": "STOPPED", "failed_shot": shot_id}, ensure_ascii=False))
            return result.returncode
    duration_window = episode.get("acceptance", {}).get("duration_window_seconds", [45, 60])
    assembly_command = [
        sys.executable, "tools/assemble_episode.py", "--manifest", str(args.manifest),
        "--shot-ids", *shot_ids, "--output", str(args.output), "--min-seconds",
        str(duration_window[0]), "--max-seconds", str(duration_window[1]),
    ]
    if args.review_output:
        assembly_command.extend(["--review-output", str(args.review_output)])
    result = subprocess.run(assembly_command)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
