"""Measure dialogue audio for the short-drama shot contract.

The helper is intentionally local-first.  It can consume an existing manifest
of WAV/MP3 files, or synthesize a bounded research WAV with Windows
System.Speech and measure it with ffprobe.  It never treats character counts
as measured audio and never uploads the generated audio.
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def probe_audio(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    duration = float(result.stdout.strip())
    if duration <= 0:
        raise ValueError(f"audio duration is not positive: {path}")
    return round(duration, 3)


def _powershell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def synthesize_windows_speech(text: str, output: Path, *, voice: str | None = None, rate: int = -2) -> float:
    """Create a local WAV with System.Speech and return its measured duration."""
    shell = _powershell()
    if not shell:
        raise RuntimeError("PowerShell is unavailable; provide a measured TTS manifest")
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    voice_expr = ""
    if voice:
        encoded_voice = base64.b64encode(voice.encode("utf-8")).decode("ascii")
        voice_expr = (
            "$voice=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" +
            encoded_voice + "')); $s.SelectVoice($voice);"
        )
    script = (
        "$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.Speech; "
        "$text=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + encoded + "')); "
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        + voice_expr +
        "$s.Rate=" + str(rate) + "; $s.Volume=100; "
        "$s.SetOutputToWaveFile('" + str(output).replace("'", "''") + "'); "
        "$s.Speak($text); $s.Dispose()"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command", script], check=True, capture_output=True, text=True)
    return probe_audio(output)


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    """Load rows keyed by shot_id, or by one-based cue/index."""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = data.get("rows", []) if isinstance(data, dict) else data
    result: dict[str, dict[str, Any]] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        key = row.get("shot_id") or row.get("cue") or row.get("index")
        if key is not None:
            result[str(key)] = row
    return result


def measure_dialogue(
    dialogue: list[tuple[str, str]],
    *,
    audio_dir: Path,
    manifest_path: Path | None = None,
    synthesize: bool = True,
    voice: str | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Return measured rows keyed by shot id and a durable manifest document."""
    existing = load_manifest(manifest_path) if manifest_path and manifest_path.is_file() else {}
    measured: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for index, (shot_id, text) in enumerate(dialogue, start=1):
        candidate = existing.get(shot_id) or existing.get(str(index))
        audio_path = None
        duration = None
        if isinstance(candidate, dict):
            candidate_text = candidate.get("text")
            if isinstance(candidate_text, str) and candidate_text.strip() and candidate_text.strip() != text.strip():
                # A cue-indexed manifest from another episode is not safe to
                # reuse merely because the row number happens to match.
                candidate = None
        if isinstance(candidate, dict):
            raw_path = candidate.get("wav") or candidate.get("audio_path") or candidate.get("path")
            if raw_path:
                candidate_path = Path(str(raw_path))
                if not candidate_path.is_absolute() and manifest_path:
                    candidate_path = (manifest_path.parent / candidate_path).resolve()
                if candidate_path.is_file():
                    audio_path = candidate_path
            raw_duration = candidate.get("duration_seconds")
            if audio_path:
                duration = probe_audio(audio_path)
            elif isinstance(raw_duration, (int, float)) and raw_duration > 0 and candidate.get("status") == "MEASURED":
                duration = round(float(raw_duration), 3)
        if duration is None and synthesize:
            audio_path = audio_dir / f"{shot_id}.wav"
            duration = synthesize_windows_speech(text, audio_path, voice=voice)
        if duration is None:
            raise RuntimeError(f"no measured TTS available for {shot_id}; provide --tts-manifest or enable local synthesis")
        row = {
            "shot_id": shot_id,
            "text": text,
            "wav": str(audio_path) if audio_path else None,
            "duration_seconds": duration,
            "status": "MEASURED",
        }
        measured[shot_id] = row
        rows.append(row)
    manifest = {
        "schema": "ace.video_kingdom.tts_measurements.v1",
        "voice": voice or "system-default",
        "count": len(rows),
        "rows": rows,
        "production_boundary": "RESEARCH_ONLY",
    }
    return measured, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", action="append", required=True, help="dialogue text; repeat in shot order")
    parser.add_argument("--shot-id", action="append", help="shot id; repeat alongside --text")
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument("--voice")
    args = parser.parse_args()
    ids = args.shot_id or [f"S{i:02d}A" for i in range(1, len(args.text) + 1)]
    if len(ids) != len(args.text):
        raise SystemExit("--shot-id count must match --text count")
    _, manifest = measure_dialogue(list(zip(ids, args.text)), audio_dir=args.audio_dir, synthesize=True, voice=args.voice)
    args.output_manifest.parent.mkdir(parents=True, exist_ok=True)
    args.output_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
