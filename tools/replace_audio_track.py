"""Replace a Provider clip's audio with the contract's external master track.

Permanent audio policy for every episode and shot:
Provider-native audio may only be treated as environmental noise. Before it
enters a deliverable it must have dialogue removed or be ducked over every
Provider dialogue interval. Because Provider reference-mode timing is not a
reliable dialogue clock, this utility uses the fail-closed path: when an
external master exists, Provider audio is excluded from the deliverable. The
Provider stream remains only in the source/download receipt. A no-dialogue
shot may use Provider audio as ambience in its own dedicated mix path.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


# Long-term audio policy for every future episode and every shot.
PROVIDER_AUDIO_POLICY = "ambience_only_dialogue_removed_or_ducked"
ONE_COPY_PER_SPOKEN_LINE = "one_external_master_only"


def _probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
         "-of", "json", str(path)], check=True, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout)
    duration = float(payload.get("format", {}).get("duration") or 0)
    if duration <= 0 or not any(item.get("codec_type") == "video" for item in payload.get("streams", [])):
        raise ValueError(f"video artifact has no valid video duration: {path}")
    return {"duration_seconds": round(duration, 3), "has_audio": any(item.get("codec_type") == "audio" for item in payload.get("streams", []))}


def replace_audio_track(video: Path, audio: Path, output: Path) -> dict[str, Any]:
    """Mux ``audio`` onto ``video`` and return a hash-bound receipt."""
    if not video.is_file():
        raise ValueError(f"video artifact missing: {video}")
    if not audio.is_file():
        raise ValueError(f"external master audio missing: {audio}")
    video_info = _probe(video)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=str(output.parent))
    os.close(fd)
    Path(temp_name).unlink(missing_ok=True)
    temp = Path(temp_name).with_suffix(".mp4")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(audio),
            "-filter_complex", f"[1:a]apad,atrim=duration={video_info['duration_seconds']},asetpts=PTS-STARTPTS[a]",
            "-map", "0:v:0", "-map", "[a]", "-t", str(video_info["duration_seconds"]),
            "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
            str(temp),
        ], check=True)
        os.replace(temp, output)
    finally:
        temp.unlink(missing_ok=True)
    result_info = _probe(output)
    return {
        "status": "EXTERNAL_AUDIO_MASTER_APPLIED",
        "video_source": str(video),
        "audio_source": str(audio),
        "video_source_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        "audio_source_sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
        "output": str(output),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "source_video_had_provider_audio": video_info["has_audio"],
        "output_media": result_info,
    }


def strip_audio_track(video: Path, output: Path) -> dict[str, Any]:
    """Create a silent production clip for an explicitly no-dialogue shot."""
    if not video.is_file():
        raise ValueError(f"video artifact missing: {video}")
    _probe(video)
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-map", "0:v:0", "-an", "-c:v", "copy", str(output)], check=True)
    return {
        "status": "PROVIDER_AUDIO_STRIPPED_NO_DIALOGUE",
        "video_source": str(video),
        "output": str(output),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }


__all__ = ["replace_audio_track", "strip_audio_track"]
