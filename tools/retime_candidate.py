"""Create a slower research candidate from an existing cut and SRT.

The operation is deliberately local and reversible: it changes playback tempo
with pitch-preserving audio, scales subtitle timestamps by the same factor,
and never overwrites the input files or claims delivery approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

TIME_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2}),(\d{3})$")


def _seconds(groups: tuple[str, ...]) -> float:
    h, m, s, ms = (int(item) for item in groups)
    return h * 3600 + m * 60 + s + ms / 1000


def _stamp(value: float) -> str:
    total_ms = max(0, int(round(value * 1000)))
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def scale_srt(source: Path, target: Path, factor: float) -> int:
    raw = source.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\r?\n\s*\r?\n", raw.strip()) if raw.strip() else []
    output: list[str] = []
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 3:
            raise ValueError("invalid SRT block")
        match = TIME_RE.match(lines[1].strip())
        if not match:
            raise ValueError(f"invalid SRT timing: {lines[1]}")
        start = _seconds(match.groups()[:4]) * factor
        end = _seconds(match.groups()[4:]) * factor
        output.append("\n".join([lines[0], f"{_stamp(start)} --> {_stamp(end)}", *lines[2:]]))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n\n".join(output) + ("\n" if output else ""), encoding="utf-8")
    return len(output)


def probe(path: Path) -> dict:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height,sample_rate,channels",
        "-of", "json", str(path),
    ], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    return {
        "duration_seconds": float(payload.get("format", {}).get("duration", 0) or 0),
        "streams": payload.get("streams", []),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--srt", type=Path, required=True)
    parser.add_argument("--output-base", type=Path, required=True)
    parser.add_argument("--output-srt", type=Path, required=True)
    parser.add_argument("--factor", type=float, default=1.12)
    args = parser.parse_args()
    if not args.input.is_file() or not args.srt.is_file():
        raise SystemExit("input video and SRT must exist")
    if not 1.01 <= args.factor <= 1.30:
        raise SystemExit("factor must be between 1.01 and 1.30")
    args.output_base.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(args.input),
        "-vf", f"setpts={args.factor}*PTS",
        "-af", f"atempo={1.0 / args.factor:.9f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000",
        "-movflags", "+faststart", str(args.output_base),
    ], check=True)
    cue_count = scale_srt(args.srt, args.output_srt, args.factor)
    result = {
        "contract_version": "ace.video_kingdom.retime_candidate.v1",
        "status": "RESEARCH_CANDIDATE",
        "promotion": "NONE_AUTOMATIC",
        "input": str(args.input),
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "output_base": str(args.output_base),
        "output_srt": str(args.output_srt),
        "slowdown_factor": args.factor,
        "audio_tempo_factor": 1.0 / args.factor,
        "subtitle_cue_count": cue_count,
        "output_media": probe(args.output_base),
        "note": "Playback is slowed with pitch-preserving audio; source is not overwritten and this does not approve dialogue, identity, or acting quality.",
    }
    receipt = args.output_base.with_suffix(".retime_receipt.json")
    receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
