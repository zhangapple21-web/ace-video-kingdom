"""Validate a short-drama SRT against the Video Kingdom subtitle contract."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

TIME_RE = re.compile(
    r"^(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2}),(?P<ms>\d{3})\s+-->\s+"
    r"(?P<h2>\d{2}):(?P<m2>\d{2}):(?P<s2>\d{2}),(?P<ms2>\d{3})$"
)
SCENE_MARKER_RE = re.compile(r"(?:^|\s)[【\[][^】\]]{1,40}[】\]](?:\s|$)|^(?:画面|镜头|场景|音效|背景音乐)[:：]")


@dataclass(frozen=True)
class Cue:
    index: int
    start: float
    end: float
    text: str


def _timestamp(match: re.Match[str], suffix: str = "") -> float:
    return (int(match.group("h" + suffix)) * 3600 + int(match.group("m" + suffix)) * 60
            + int(match.group("s" + suffix)) + int(match.group("ms" + suffix)) / 1000)


def parse_srt(path: Path) -> list[Cue]:
    raw = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\r?\n\s*\r?\n", raw.strip()) if raw.strip() else []
    cues: list[Cue] = []
    for block_no, block in enumerate(blocks, start=1):
        lines = block.splitlines()
        if len(lines) < 3:
            raise ValueError(f"block {block_no} must contain index, timing, and text")
        try:
            index = int(lines[0].strip())
        except ValueError as exc:
            raise ValueError(f"block {block_no} has a non-numeric cue index") from exc
        match = TIME_RE.match(lines[1].strip())
        if not match:
            raise ValueError(f"cue {lines[0].strip()} has invalid SRT timing")
        text = "\n".join(lines[2:]).strip()
        if not text:
            raise ValueError(f"cue {index} has empty text")
        cues.append(Cue(index, _timestamp(match), _timestamp(match, "2"), text))
    return cues


def validate(cues: list[Cue], *, fps: float = 24, min_duration: float = 20 / 24,
             max_lines: int = 3, max_cjk_per_line: int = 20) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    min_gap = 2 / fps
    previous: Cue | None = None
    for cue in cues:
        if cue.end <= cue.start:
            errors.append(f"cue {cue.index}: end must be after start")
        if cue.end - cue.start < min_duration:
            errors.append(f"cue {cue.index}: duration {cue.end - cue.start:.3f}s is below {min_duration:.3f}s")
        lines = cue.text.splitlines()
        if len(lines) > max_lines:
            errors.append(f"cue {cue.index}: {len(lines)} lines exceeds vertical limit {max_lines}")
        for line in lines:
            cjk_count = sum(1 for char in line if "\u4e00" <= char <= "\u9fff")
            if cjk_count > max_cjk_per_line:
                warnings.append(f"cue {cue.index}: line has {cjk_count} CJK characters; consider a natural break")
        if SCENE_MARKER_RE.search(cue.text):
            errors.append(f"cue {cue.index}: scene-direction text is not allowed in dialogue/inner-voice track")
        if previous is not None:
            gap = cue.start - previous.end
            if gap < 0:
                errors.append(f"cue {cue.index}: overlaps cue {previous.index} by {-gap:.3f}s")
            elif gap < min_gap:
                errors.append(f"cue {cue.index}: gap after cue {previous.index} is {gap:.3f}s; need at least {min_gap:.3f}s")
        previous = cue
    return {"status": "VALID" if not errors else "INVALID", "cue_count": len(cues),
            "fps": fps, "minimum_duration_seconds": min_duration,
            "minimum_gap_seconds": min_gap, "errors": errors, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("srt", type=Path)
    parser.add_argument("--fps", type=float, default=24)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate(parse_srt(args.srt), fps=args.fps)
    except (OSError, ValueError) as exc:
        result = {"status": "INVALID", "cue_count": 0, "errors": [str(exc)], "warnings": []}
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["status"] == "VALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
