"""Normalize Volcengine/MediaKit ASR JSON into SRT and styled ASS files.

The cloud ASR step is intentionally outside this module.  This keeps provider
credentials out of the short-drama backend while allowing the transcript
payloads produced by the video-skills-toolkit subtitle pipeline to be reused.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(item: dict[str, Any]) -> str:
    for key in ("text", "subtitle_text", "content", "utterance", "transcript"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _segments_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract common MediaKit/AUC subtitle segment shapes."""
    candidates: list[Any] = [payload]
    for key in ("result", "data", "output"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidates.append(value)
    raw: list[Any] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for key in ("subtitles", "utterances", "segments", "items"):
            value = candidate.get(key)
            if isinstance(value, list):
                raw = value
                break
        if raw:
            break

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        start = _number(item.get("start_time", item.get("startTime", item.get("start"))))
        end = _number(item.get("end_time", item.get("endTime", item.get("end"))))
        text = _text(item)
        if start is None or end is None or not text or end <= start:
            continue
        normalized.append(
            {
                "index": index,
                "start": max(0.0, start),
                "end": max(start + 0.05, end),
                "text": text,
                "speaker": str(item.get("speaker") or item.get("speaker_name") or "").strip(),
            }
        )
    normalized.sort(key=lambda item: (item["start"], item["end"], item["index"]))
    for index, item in enumerate(normalized, start=1):
        item["index"] = index
    return normalized


def _srt_time(seconds: float) -> str:
    millis = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def render_srt(segments: list[dict[str, Any]]) -> str:
    blocks = []
    for item in segments:
        label = f"{item['speaker']}: " if item.get("speaker") else ""
        blocks.extend(
            [
                str(item["index"]),
                f"{_srt_time(item['start'])} --> {_srt_time(item['end'])}",
                f"{label}{item['text']}",
                "",
            ]
        )
    return "\n".join(blocks)


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def render_ass(
    segments: list[dict[str, Any]],
    *,
    font_name: str = "Microsoft YaHei",
    font_size: int = 54,
    alignment: int = 2,
    margin_v: int = 90,
) -> str:
    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font_name},{font_size},&H00FFFFFF,&H0000FFFF,&H00181818,&H80000000,0,0,0,0,100,100,0,0,1,3,1,{alignment},60,60,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = []
    for item in segments:
        label = f"{item['speaker']}: " if item.get("speaker") else ""
        text = f"{label}{item['text']}".replace("\n", r"\N")
        events.append(
            f"Dialogue: 0,{_ass_time(item['start'])},{_ass_time(item['end'])},Default,,0,0,0,,{text}"
        )
    return "\n".join(header + events) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Volcengine/MediaKit ASR JSON")
    parser.add_argument("--srt", type=Path, required=True)
    parser.add_argument("--ass", type=Path, required=True)
    parser.add_argument("--font-name", default="Microsoft YaHei")
    parser.add_argument("--font-size", type=int, default=54)
    parser.add_argument("--alignment", type=int, default=2)
    parser.add_argument("--margin-v", type=int, default=90)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("ASR JSON root must be an object")
    segments = _segments_from_payload(payload)
    if not segments:
        raise SystemExit("ASR JSON contains no usable timed subtitle segments")
    args.srt.parent.mkdir(parents=True, exist_ok=True)
    args.ass.parent.mkdir(parents=True, exist_ok=True)
    args.srt.write_text(render_srt(segments), encoding="utf-8")
    args.ass.write_text(
        render_ass(
            segments,
            font_name=args.font_name,
            font_size=args.font_size,
            alignment=args.alignment,
            margin_v=args.margin_v,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"segments": len(segments), "srt": str(args.srt), "ass": str(args.ass)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
