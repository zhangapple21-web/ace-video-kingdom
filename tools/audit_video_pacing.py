"""Audit actual short-drama pacing and internal cuts without calling a provider."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def probe(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,width,height", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not video:
        raise SystemExit(f"no video stream: {path}")
    return {
        "duration_seconds": float(data.get("format", {}).get("duration", 0) or 0),
        "width": video.get("width"), "height": video.get("height"),
        "has_audio": audio is not None,
    }


def scene_cuts(path: Path, threshold: float) -> list[float]:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-filter:v",
         f"select='gt(scene,{threshold})',showinfo", "-f", "null", "NUL"],
        check=False, capture_output=True, text=True,
    )
    times: list[float] = []
    for line in result.stderr.splitlines():
        match = re.search(r"pts_time:([0-9.]+)", line)
        if match:
            times.append(float(match.group(1)))
    return times


def subtitle_coverage(path: Path | None) -> float | None:
    if not path:
        return None
    text = path.read_text(encoding="utf-8")
    total = 0.0
    for values in re.findall(r"(\d\d):(\d\d):(\d\d),(\d\d\d) --> (\d\d):(\d\d):(\d\d),(\d\d\d)", text):
        h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, values)
        total += (h2 * 3600 + m2 * 60 + s2 + ms2 / 1000) - (h1 * 3600 + m1 * 60 + s1 + ms1 / 1000)
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--srt", type=Path)
    parser.add_argument("--dialogue", action="store_true", help="apply zero-internal-cut dialogue gate")
    parser.add_argument("--scene-threshold", type=float, default=0.25)
    parser.add_argument("--max-internal-cuts", type=int, default=0)
    parser.add_argument("--tts-duration", type=float,
                        help="measured dialogue duration; video must cover it")
    parser.add_argument("--expected-duration", type=float,
                        help="TTS-derived planned duration before render padding")
    parser.add_argument("--duration-tolerance", type=float, default=2.0,
                        help="allowed deviation from expected duration; longer clips are retained for reaction hold")
    parser.add_argument("--require-audio", action="store_true",
                        help="fail when the clip has no audio stream")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    media = probe(args.video)
    cuts = scene_cuts(args.video, args.scene_threshold)
    subtitle_seconds = subtitle_coverage(args.srt)
    coverage = (subtitle_seconds / media["duration_seconds"]) if subtitle_seconds is not None and media["duration_seconds"] else None
    allowed = args.max_internal_cuts if not args.dialogue else 0
    failures: list[str] = []
    if media["duration_seconds"] <= 0:
        failures.append("video duration must be positive")
    if len(cuts) > allowed:
        failures.append(f"internal scene cuts {len(cuts)} exceed allowed {allowed}")
    if args.require_audio and not media["has_audio"]:
        failures.append("dialogue shot has no audio stream")
    if args.tts_duration is not None:
        if args.tts_duration <= 0:
            failures.append("tts duration must be positive")
        elif media["duration_seconds"] + 1e-6 < args.tts_duration:
            failures.append("video duration is shorter than measured TTS")
    duration_deviation = None
    if args.expected_duration is not None:
        if args.expected_duration <= 0:
            failures.append("expected duration must be positive")
        else:
            duration_deviation = media["duration_seconds"] - args.expected_duration
            # A provider may add a few frames of recovery/hold.  Never reject
            # that extra performance; only reject a clip that is materially
            # shorter than the TTS-derived contract or wildly overlong.
            if duration_deviation < -max(0.0, args.duration_tolerance) or duration_deviation > max(0.0, args.duration_tolerance):
                failures.append(
                    f"video duration deviates from expected by {duration_deviation:.3f}s "
                    f"(tolerance {args.duration_tolerance:.3f}s)"
                )
    status = "PASS" if not failures else "FAIL"
    report = {
        "contract_version": "ace.video_kingdom.video_pacing_audit.v1",
        "video": str(args.video), "status": status, "media": media,
        "internal_scene_cut_count": len(cuts), "internal_scene_cut_times_seconds": cuts,
        "dialogue_gate": args.dialogue, "max_internal_cuts": allowed,
        "subtitle_seconds": subtitle_seconds, "subtitle_coverage_ratio": coverage,
        "tts_duration_seconds": args.tts_duration,
        "expected_duration_seconds": args.expected_duration,
        "duration_tolerance_seconds": args.duration_tolerance,
        "duration_deviation_seconds": duration_deviation,
        "failures": failures,
        "note": "Scene detection is a conservative QC signal; it does not prove acting or lip-sync.",
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
