"""Build an evidence-first audit of the previous and current short-drama cuts.

This is intentionally deterministic and read-only with respect to media.  It
does not call a provider, promote a model, or decide that a cut is deliverable.
The report is the small pre-work memory step used before another render.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _probe(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    command = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height,avg_frame_rate,sample_rate,channels",
        "-of", "json", str(path),
    ]
    try:
        raw = subprocess.run(command, capture_output=True, text=True, check=True).stdout
        value = json.loads(raw)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return {"exists": True, "path": str(path), "probe_error": str(exc)}
    streams = value.get("streams", [])
    return {
        "exists": True,
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "duration_seconds": float(value.get("format", {}).get("duration", 0) or 0),
        "video_streams": [s for s in streams if s.get("codec_type") == "video"],
        "audio_streams": [s for s in streams if s.get("codec_type") == "audio"],
    }


def _load(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"missing_or_invalid": relative}


def build(root: Path) -> dict[str, Any]:
    prior = root / "media_staging/episode_006_wenji_110s/video/episode_006_wenji_full_108s_subtitled.mp4"
    current = root / "media_staging/episode_007_virtual_data/video_camera_grammar_v2/episode_007_candidate_v7_subtitled.mp4"
    return {
        "contract_version": "ace.video_kingdom.previous_cut_audit.v1",
        "scope": "FREE_ZONE_RESEARCH_ONLY",
        "production_integration": False,
        "read_only": True,
        "generated_at_note": "deterministic local audit; timestamp supplied by caller",
        "cuts": {
            "previous_episode_006": _probe(prior),
            "current_episode_007": _probe(current),
        },
        "review_evidence": {
            "episode_006_receipt": _load(root, "research/episode_006_full_cut_receipt.v1.json"),
            "episode_007_quality": _load(root, "research/episode_007_quality_review.v1.json"),
            "episode_007_action_probe": _load(root, "research/episode_007_action_probe_review.v3.json"),
            "episode_007_subtitle": _load(root, "research/episode_007_subtitle_review_v7.json"),
        },
        "successes_to_reuse": [
            "episode_006 kept one coherent costume, lighting language, and scene vocabulary across the cut",
            "scene/action stills were used as motion starting states rather than isolated portraits",
            "longer reference chunks exposed less static-cover startup than fragmented portrait I2V",
            "episode_007 v7 has verified 704x1280 H.264/AAC media and bottom subtitle placement",
        ],
        "failures_to_prevent": [
            "provider completion or an AAC stream is not proof of dialogue, lip-sync, or acting quality",
            "episode_007 review found portrait-like shots, weak narrative actions, scene homogenisation, and costume/identity drift",
            "camera movement must not be added to dialogue or inner-monologue shots; actions need visible preparation, impact, and recovery",
            "subtitle timing must follow measured shot/audio timing, never a fixed character-count or fixed five-second grid",
            "a static fallback image may not be promoted as an action shot",
        ],
        "pre_render_checklist": [
            "Read this audit and the latest shot-level review before submitting any new provider request",
            "Reuse only hash-identified approved assets and branch from the last satisfactory scene/action state",
            "For each shot, bind dialogue/action type, camera movement, action beats, end state, and audio source",
            "Generate and measure the external master audio before locking duration; retain any provider-generated audio only as historical evidence, never as a formal candidate or deliverable",
            "Review one representative dialogue shot and one action shot before batch generation",
            "After rendering, compare against this audit and record new failures instead of silently overwriting the baseline",
        ],
        "decision": "AUDIT_ONLY_NO_AUTOMATIC_PROMOTION",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"audited=previous_and_current cuts={len(result['cuts'])} decision={result['decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
