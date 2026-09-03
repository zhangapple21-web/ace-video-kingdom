"""Build a deterministic short-drama preflight report before provider submission.

This tool is deliberately model-free.  It checks executable facts first and
emits reviewer packets for a 5.6 Terra main review and an optional Grok 4.6
red-team pass.  A model review can improve a story, but cannot waive a failed
asset, continuity, or renderer-contract check.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

try:
    from validate_motion_diversity import validate as validate_motion
except ImportError:  # support ``python -m tools.preflight_episode`` as well
    from tools.validate_motion_diversity import validate as validate_motion
try:
    from validate_episode_quality import validate as validate_quality
except ImportError:  # support ``python -m tools.preflight_episode`` as well
    from tools.validate_episode_quality import validate as validate_quality


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _local_path(plan_path: Path, value: str) -> Path:
    return (plan_path.parent / value).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("governance/short_drama_review_policy.v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--grok-health", choices=["verified", "unavailable", "unknown"], default="unknown")
    parser.add_argument("--require-formal", action="store_true",
                        help="fail closed when the seven-layer quality plan is only experimental")
    args = parser.parse_args()
    plan = _load(args.episode)
    policy = _load(args.policy)
    hard_failures: list[str] = []
    rework: list[str] = []
    warnings: list[str] = []
    if plan.get("scope") != "FREE_ZONE_RESEARCH_ONLY":
        hard_failures.append("scope must be FREE_ZONE_RESEARCH_ONLY")
    if plan.get("production_integration") is not False:
        hard_failures.append("production_integration must be false")
    shots = plan.get("shots")
    if not isinstance(shots, list) or not shots:
        hard_failures.append("episode must declare at least one shot")
        shots = []
    motion_contract = validate_motion({"shots": shots})
    hard_failures.extend(f"motion: {error}" for error in motion_contract.get("errors", []))
    warnings.extend(f"motion: {warning}" for warning in motion_contract.get("warnings", []))
    quality_contract = validate_quality(plan)
    if quality_contract.get("status") == "INVALID":
        hard_failures.extend(f"quality: {error}" for error in quality_contract.get("errors", []))
    else:
        warnings.extend(quality_contract.get("warnings", []))
    if args.require_formal and quality_contract.get("status") != "VALID":
        hard_failures.append("quality: a provider run requires a complete FORMAL seven-layer contract")
    defaults = plan.get("render_defaults") if isinstance(plan.get("render_defaults"), dict) else {}
    model = defaults.get("model")
    if model != "agnes-video-2.5-flash":
        warnings.append(f"primary renderer is {model!r}; current default policy expects agnes-video-2.5-flash")
    seconds = defaults.get("seconds")
    if not isinstance(seconds, int) or not 4 <= seconds <= 12:
        rework.append("Flash duration must be an integer from 4 through 12 seconds")
    references: set[str] = set()
    shot_packets: list[dict] = []
    for index, shot in enumerate(shots, start=1):
        shot_id = shot.get("shot_id") if isinstance(shot, dict) else None
        prompt = shot.get("prompt") if isinstance(shot, dict) else None
        render = shot.get("render") if isinstance(shot, dict) and isinstance(shot.get("render"), dict) else {}
        if not shot_id or not prompt:
            rework.append(f"shot {index} needs shot_id and prompt")
            continue
        urls = render.get("reference_image_urls")
        if not isinstance(urls, list) or len(urls) != 1 or not isinstance(urls[0], str):
            hard_failures.append(f"{shot_id}: exactly one public scene-anchor URL is required")
            continue
        url = urls[0]
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            hard_failures.append(f"{shot_id}: scene-anchor URL must be HTTPS")
        if url in references and not shot.get("continuous_action"):
            rework.append(f"{shot_id}: reuses a non-continuous scene anchor")
        references.add(url)
        fallback = render.get("fallback_image")
        if not isinstance(fallback, str) or not _local_path(args.episode, fallback).is_file():
            hard_failures.append(f"{shot_id}: fallback_image is missing locally")
        shot_packets.append({"shot_id": shot_id, "prompt": prompt, "scene_anchor_url": url, "fallback_image": fallback})
    estimate_seconds = len(shots) * seconds if isinstance(seconds, int) else None
    acceptance = plan.get("acceptance") if isinstance(plan.get("acceptance"), dict) else {}
    window = acceptance.get("duration_window_seconds")
    if isinstance(window, list) and len(window) == 2 and estimate_seconds is not None:
        if not window[0] <= estimate_seconds <= window[1]:
            rework.append(f"planned duration {estimate_seconds}s lies outside declared acceptance window {window}")
    if hard_failures:
        verdict = "BLOCKED"
    elif rework:
        verdict = "REWORK"
    elif args.grok_health != "verified":
        verdict = "CONDITIONAL"
        warnings.append("Grok 4.6 red-team is not freshly health-verified; continue only with a bounded first shot after 5.6 Terra review")
    else:
        verdict = "READY"
    report = {
        "contract_version": "ace.video_kingdom.episode_preflight.v1",
        "scope": "FREE_ZONE_RESEARCH_ONLY",
        "production_integration": False,
        "episode": str(args.episode),
        "project_id": plan.get("project_id"),
        "verdict": verdict,
        "hard_failures": hard_failures,
        "rework": rework,
        "warnings": warnings,
        "planned_shot_count": len(shots),
        "planned_duration_seconds": estimate_seconds,
        "motion_contract": motion_contract,
        "quality_contract": quality_contract,
        "review_policy": policy.get("review_order"),
        "primary_review_packet": {"reviewer": "5.6 Terra", "shots": shot_packets, "questions": ["Does each shot advance the causal chain?", "Does the character state change visibly?", "Can the stated action be filmed in one short clip?", "Are the first three seconds and end state clear?"]},
        "red_team_packet": {"reviewer": "Grok 4.6", "enabled": args.grok_health == "verified", "questions": ["What would confuse a first-time viewer?", "Where is a motive or causal bridge missing?", "Which beat feels generic or repetitive?", "Which image/video constraint will make this shot look like a repeated cover?"]},
        "escalation": {"reviewer": "5.6 Sol", "only_if": "primary and red-team recommendations materially conflict"},
        "packaging": {"reviewer": "5.6 Luna", "only_after": "an approved review result; no approval or provider authority"}
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "hard_failures": len(hard_failures), "rework": len(rework), "warnings": len(warnings), "output": str(args.output)}, ensure_ascii=False))
    return 0 if verdict in {"READY", "CONDITIONAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
