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


def _append_repeated_option(command: list[str], flag: str, values: object | None) -> None:
    """Forward plan-owned URL collections without accepting ambiguous strings.

    Flash references are deliberately URL-only: this keeps the episode plan
    auditable and prevents a local path from being silently uploaded by the
    wrong renderer contract.
    """
    if values is None:
        return
    if not isinstance(values, list) or not all(isinstance(value, str) and value for value in values):
        raise SystemExit(f"{flag} must be a non-empty-string list when supplied")
    for value in values:
        command.extend([flag, value])


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
        references = render.get("reference_image_urls")
        if image and references:
            raise SystemExit("a shot cannot mix local image and Flash reference_image_urls")
        if references is not None:
            if not isinstance(references, list) or len(references) != 1 or not isinstance(references[0], str) or not references[0]:
                raise SystemExit("each Flash reference shot must declare exactly one scene-anchor URL")
            image = references[0]
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


def _quota_exhausted(manifest: Path, shot_id: str) -> bool:
    try:
        records = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    rows = records if isinstance(records, list) else [records]
    record = next((row for row in rows if isinstance(row, dict) and row.get("shot_id") == shot_id), {})
    return (
        record.get("error_class") == "HTTP_CREATE_ERROR"
        and "insufficient_user_quota" in str(record.get("error_body_excerpt", ""))
    )


def _replace_model(command: list[str], model: str) -> list[str]:
    updated = list(command)
    try:
        index = updated.index("--model")
    except ValueError:
        updated.extend(["--model", model])
    else:
        updated[index + 1] = model
    return updated


def _v2_fallback_command(command: list[str], render: dict) -> list[str]:
    """Turn a failed Flash reference attempt into an explicit local v2.0 I2V retry.

    The fallback never receives Flash's URL-only fields as its conditioning
    input.  It must name the matching local anchor in ``fallback_image`` so
    the two providers preserve the same scene boundary.
    """
    image = render.get("fallback_image")
    if not isinstance(image, str) or not image:
        raise SystemExit("Flash -> v2.0 fallback requires render.fallback_image")
    filtered: list[str] = []
    skip_next = False
    flash_flags = {
        "--flash-mode", "--flash-first-frame-url", "--flash-last-frame-url",
        "--flash-reference-image-url", "--flash-reference-audio-url",
        "--reference-video-url", "--reference-video-require-audio",
        "--seconds", "--size", "--aspect-ratio",
    }
    for token in command:
        if skip_next:
            skip_next = False
            continue
        if token in flash_flags:
            skip_next = token != "--reference-video-require-audio"
            continue
        filtered.append(token)
    filtered = _replace_model(filtered, "agnes-video-v2.0")
    filtered.extend(["--image", image])
    return filtered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--media-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, help="optional local media-integrity review JSON")
    parser.add_argument("--preflight-output", type=Path,
                        help="where to persist the mandatory deterministic preflight receipt")
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
    preflight_output = args.preflight_output or args.manifest.with_name(args.manifest.stem + ".preflight.json")
    preflight = subprocess.run([
        sys.executable, str(Path(__file__).with_name("preflight_episode.py")), "--episode", str(args.episode),
        "--output", str(preflight_output), "--require-formal",
    ], cwd=Path(__file__).resolve().parents[1])
    if preflight.returncode:
        raise SystemExit(
            "episode preflight is BLOCKED/REWORK; no provider request submitted. "
            f"See {preflight_output}"
        )
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
        _append_option(command, "--model", render.get("model"))
        image = render.get("image")
        if image:
            image_path = (args.episode.parent / image).resolve() if not str(image).startswith(("http://", "https://", "data:")) else image
            _append_option(command, "--image", image_path)
        for field, flag in (
            ("width", "--width"), ("height", "--height"), ("num_frames", "--num-frames"),
            ("frame_rate", "--frame-rate"), ("seed", "--seed"),
            ("negative_prompt", "--negative-prompt"), ("seconds", "--seconds"),
            ("size", "--size"), ("aspect_ratio", "--aspect-ratio"),
            ("flash_mode", "--flash-mode"),
        ):
            _append_option(command, flag, render.get(field))
        _append_option(command, "--flash-first-frame-url", render.get("flash_first_frame_url"))
        _append_option(command, "--flash-last-frame-url", render.get("flash_last_frame_url"))
        _append_repeated_option(command, "--flash-reference-image-url", render.get("reference_image_urls"))
        _append_repeated_option(command, "--flash-reference-audio-url", render.get("reference_audio_urls"))
        result = subprocess.run(command)
        fallback_model = render.get("fallback_model")
        fallback_reason = _quota_exhausted(args.manifest, shot_id)
        fallback_on_failure = bool(render.get("fallback_on_failure"))
        if result.returncode and fallback_model and (fallback_reason or fallback_on_failure):
            print(json.dumps({
                "status": "FALLBACK_AFTER_PRIMARY_FAILURE",
                "shot_id": shot_id,
                "from_model": render.get("model", "agnes-video-v2.0"),
                "to_model": fallback_model,
            }, ensure_ascii=False), flush=True)
            if render.get("model") == "agnes-video-2.5-flash" and fallback_model == "agnes-video-v2.0":
                command = _v2_fallback_command(command, render)
            else:
                command = _replace_model(command, str(fallback_model))
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
