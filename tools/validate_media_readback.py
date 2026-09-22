"""Compare delivered media readback with its planned contract."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Callable


def compare_readback(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    mismatches: list[str] = []
    for key in ("width", "height", "frame_count", "audio_tracks", "subtitle_tracks"):
        if key in expected and actual.get(key) != expected[key]:
            mismatches.append(f"{key}: expected {expected[key]!r}, got {actual.get(key)!r}")
    if "duration_seconds" in expected:
        tolerance = float(expected.get("duration_tolerance_seconds", 0.15))
        if actual.get("duration_seconds") is None or abs(float(actual["duration_seconds"]) - float(expected["duration_seconds"])) > tolerance:
            mismatches.append(f"duration_seconds outside tolerance: expected {expected['duration_seconds']!r}, got {actual.get('duration_seconds')!r}")
    human = str(expected.get("human_listening") or "UNVERIFIED").upper()
    if expected.get("audio_required", False) and human != "VERIFIED":
        mismatches.append("human_listening is not VERIFIED")
    return {"status": "PASS" if not mismatches else "READBACK_MISMATCH", "mismatches": mismatches, "actual": actual, "expected": expected}


def ffprobe_readback(path: Path, runner: Callable[..., Any] = subprocess.run) -> dict[str, Any]:
    result = runner(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_tracks = sum(s.get("codec_type") == "audio" for s in streams)
    subtitle_tracks = sum(s.get("codec_type") == "subtitle" for s in streams)
    frame_count = video.get("nb_frames")
    return {"width": video.get("width"), "height": video.get("height"), "frame_count": int(frame_count) if str(frame_count or "").isdigit() else None, "audio_tracks": audio_tracks, "subtitle_tracks": subtitle_tracks, "duration_seconds": float(payload.get("format", {}).get("duration")) if payload.get("format", {}).get("duration") else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    args = parser.parse_args()
    result = compare_readback(ffprobe_readback(args.media), json.loads(args.expected.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
