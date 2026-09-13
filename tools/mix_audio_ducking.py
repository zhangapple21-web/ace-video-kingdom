"""Mix narration and BGM with fade-in/out and voice-driven ducking.

This is a local FFmpeg stage: no audio is uploaded and no provider key is
required.  The voice track determines the output duration; the BGM loops,
fades, and is compressed under the narration before the final loudness pass.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


def probe_duration(path: Path) -> float:
    ffprobe = _resolve_binary("FFPROBE_BIN", "ffprobe")
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    duration = float(result.stdout.strip())
    if duration <= 0:
        raise ValueError(f"voice track has invalid duration: {path}")
    return duration


def build_filter_complex(duration: float, bgm_volume: float, duck_ratio: float) -> str:
    fade = min(1.0, max(0.05, duration / 2.0))
    fade_out_start = max(0.0, duration - fade)
    return (
        f"[0:a]aresample=48000,volume=1.0[voice];"
        f"[1:a]aresample=48000,volume={bgm_volume:.4f},"
        f"atrim=duration={duration:.3f},asetpts=N/SR/TB,"
        f"afade=t=in:st=0:d={fade:.3f},"
        f"afade=t=out:st={fade_out_start:.3f}:d={fade:.3f}[bgm];"
        f"[bgm][voice]sidechaincompress=threshold=0.05:ratio={duck_ratio:.3f}:"
        f"attack=20:release=300:makeup=1[ducked];"
        f"[voice][ducked]amix=inputs=2:duration=first:dropout_transition=2,"
        f"loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
    )


def _codec_args(output: Path) -> list[str]:
    suffix = output.suffix.lower()
    if suffix == ".wav":
        return ["-c:a", "pcm_s16le"]
    if suffix == ".mp3":
        return ["-c:a", "libmp3lame", "-b:a", "192k"]
    return ["-c:a", "aac", "-b:a", "192k"]


def _resolve_binary(env_name: str, command: str) -> str:
    """Resolve FFmpeg tools from env/PATH, including the WinGet link path."""
    configured = os.environ.get(env_name)
    if configured:
        return configured
    found = shutil.which(command)
    if found:
        return found
    if os.name == "nt":
        winget_link = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / f"{command}.exe"
        if winget_link.is_file():
            return str(winget_link)
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice", type=Path, required=True, help="Narration/voice audio")
    parser.add_argument("--bgm", type=Path, required=True, help="Background music audio")
    parser.add_argument("--output", type=Path, required=True, help=".m4a, .mp3, or .wav output")
    parser.add_argument("--bgm-volume", type=float, default=0.22)
    parser.add_argument("--duck-ratio", type=float, default=8.0)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    for path in (args.voice, args.bgm):
        if not path.is_file():
            raise SystemExit(f"input audio not found: {path}")
    if not 0 < args.bgm_volume <= 1:
        raise SystemExit("--bgm-volume must be in (0, 1]")
    if args.duck_ratio < 1:
        raise SystemExit("--duck-ratio must be >= 1")

    duration = probe_duration(args.voice)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        _resolve_binary("FFMPEG_BIN", "ffmpeg"),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(args.voice),
        "-stream_loop",
        "-1",
        "-i",
        str(args.bgm),
        "-filter_complex",
        build_filter_complex(duration, args.bgm_volume, args.duck_ratio),
        "-map",
        "[aout]",
        "-t",
        f"{duration:.3f}",
        *_codec_args(args.output),
        str(args.output),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        detail = (result.stderr or "FFmpeg failed").strip()[-1200:]
        raise SystemExit(detail)

    receipt = {
        "status": "AUDIO_MIXED_DUCKING",
        "voice": str(args.voice),
        "bgm": str(args.bgm),
        "output": str(args.output),
        "voice_duration_seconds": round(duration, 3),
        "bgm_volume": args.bgm_volume,
        "duck_ratio": args.duck_ratio,
        "engine": "ffmpeg",
    }
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
