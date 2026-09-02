"""Burn a validated subtitle track into a local research video.

This is the single subtitle-rendering entry point for the Video Kingdom.  It
does not call a provider or publish anything: the SRT is linted first, then
ffmpeg renders a predictable vertical safe-area style while preserving audio.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

try:
    from validate_subtitles import parse_srt, validate
except ImportError:  # support ``python -m tools.burn_subtitles`` as well
    from tools.validate_subtitles import parse_srt, validate


def _filter_path(path: Path) -> str:
    # Prefer a path relative to the current repository: the subtitles filter
    # treats a Windows drive colon as an option separator.  The fallback is
    # still escaped for callers running the tool from another directory.
    absolute = path.resolve()
    try:
        value = absolute.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        value = absolute.as_posix()
        if len(value) >= 2 and value[1] == ":":
            value = value[0] + r"\:" + value[2:]
    return value.replace("'", r"'\\''")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--srt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-output", type=Path)
    parser.add_argument("--fps", type=float, default=24)
    parser.add_argument("--font-size", type=int, default=10)
    parser.add_argument("--margin-v", type=int, default=80)
    args = parser.parse_args()
    for path in (args.input, args.srt):
        if not path.is_file():
            raise SystemExit(f"missing input: {path}")
    validation = validate(parse_srt(args.srt), fps=args.fps)
    if validation["status"] != "VALID":
        if args.review_output:
            args.review_output.parent.mkdir(parents=True, exist_ok=True)
            args.review_output.write_text(json.dumps({"subtitle_validation": validation}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise SystemExit("subtitle validation failed; refusing to burn an invalid track")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    style = (
        f"FontName=Microsoft YaHei,FontSize={args.font_size},"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BorderStyle=1,Outline=1,Shadow=0,Alignment=2,"
        f"MarginV={args.margin_v},WrapStyle=2"
    ).replace(",", r"\,")
    filter_expr = f"subtitles={_filter_path(args.srt)}:force_style='{style}'"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(args.input), "-vf", filter_expr,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000",
        "-movflags", "+faststart", str(args.output),
    ], check=True)
    if not args.output.is_file() or args.output.stat().st_size == 0:
        raise SystemExit("ffmpeg produced no output")
    review = {
        "status": "SUBTITLED_MEDIA_INTEGRITY_PASSED",
        "input": str(args.input),
        "subtitle": str(args.srt),
        "output": str(args.output),
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "subtitle_validation": validation,
        "render_style": {"font": "Microsoft YaHei", "font_size": args.font_size, "margin_v": args.margin_v, "alignment": 2},
    }
    if args.review_output:
        args.review_output.parent.mkdir(parents=True, exist_ok=True)
        args.review_output.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(review, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
