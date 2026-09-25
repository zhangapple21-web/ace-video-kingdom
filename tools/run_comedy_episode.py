"""Run one explicit, finite short-drama plan through the durable clip utility.

This is a manual episode executor, not a scheduler: it has no clock, daemon,
or task-discovery authority. It stops on a failed shot and leaves the durable
manifest intact for an operator or later Free Zone turn to resume.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    from runtime.provider_admission import delivery_gate
except ImportError:  # pragma: no cover
    from tools.runtime.provider_admission import delivery_gate  # type: ignore

from tools.replace_audio_track import replace_audio_track, strip_audio_track
from tools.validate_creative_slice import load_and_validate


def _append_option(command: list[str], flag: str, value: object | None) -> None:
    if value is not None and value != "":
        command.extend([flag, str(value)])


def _append_repeated_option(command: list[str], flag: str, values: object | None) -> None:
    """Forward plan-owned URL collections without accepting ambiguous strings.

    Flash references are deliberately URL-only: this keeps the episode plan
    auditable and prevents a local path from being silently uploaded by the
    wrong renderer contract.
    """
    if values is None:
        return
    if not isinstance(values, list) or not all(isinstance(value, str) and value for value in values):
        raise SystemExit(f"{flag} must be a non-empty-string list when supplied")
    for value in values:
        command.extend([flag, value])


def _validate_asset_graph(shots: list[dict]) -> None:
    """Prevent accidental reuse of a scene's start image across a cut.

    Text-only episodes remain supported.  Once a plan chooses image-to-video,
    though, every shot must name a scene asset and two shots cannot silently
    share one unless the plan is explicitly a continuous action.
    """
    render_images: list[tuple[str, str, bool]] = []
    for shot in shots:
        render = shot.get("render", {}) if isinstance(shot.get("render"), dict) else {}
        image = render.get("image")
        references = render.get("reference_image_urls")
        if image and references:
            raise SystemExit("a shot cannot mix local image and Flash reference_image_urls")
        if references is not None:
            if not isinstance(references, list) or len(references) != 1 or not isinstance(references[0], str) or not references[0]:
                raise SystemExit("each Flash reference shot must declare exactly one scene-anchor URL")
            image = references[0]
        if image:
            render_images.append((str(shot.get("shot_id", "unknown")), str(image), bool(shot.get("continuous_action"))))
    if not render_images:
        return
    if len(render_images) != len(shots):
        raise SystemExit("asset-first episode mixes image-backed and unanchored shots")
    seen: dict[str, tuple[str, bool]] = {}
    for shot_id, image, continuous_action in render_images:
        prior = seen.get(image)
        if prior and not (continuous_action and prior[1]):
            raise SystemExit(
                f"asset graph reuses start image for {prior[0]} and {shot_id}; "
                "set continuous_action=true on both only for one uninterrupted action"
            )
        seen[image] = (shot_id, continuous_action)


def _quota_exhausted(manifest: Path, shot_id: str) -> bool:
    try:
        records = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    rows = records if isinstance(records, list) else [records]
    record = next((row for row in rows if isinstance(row, dict) and row.get("shot_id") == shot_id), {})
    return (
        record.get("error_class") == "HTTP_CREATE_ERROR"
        and "insufficient_user_quota" in str(record.get("error_body_excerpt", ""))
    )


def _run_pacing_audit(
    video: Path,
    output: Path,
    *,
    tts_duration: float | None = None,
    expected_duration: float | None = None,
    dialogue: bool = True,
    max_internal_cuts: int = 0,
) -> dict:
    """Run the mandatory per-shot pacing gate and return its receipt."""
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, str(Path(__file__).with_name("audit_video_pacing.py")),
        "--video", str(video), "--max-internal-cuts", str(max_internal_cuts), "--output", str(output),
    ]
    if dialogue:
        command.extend(["--require-audio", "--dialogue"])
    if tts_duration is not None:
        command.extend(["--tts-duration", str(tts_duration)])
    if expected_duration is not None:
        command.extend(["--expected-duration", str(expected_duration)])
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)
    if output.is_file():
        try:
            report = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            report = {"status": "FAIL", "error": "pacing audit did not produce valid JSON"}
    else:
        report = {"status": "FAIL", "error": result.stderr[-1000:] or "pacing audit did not produce a report"}
    report["returncode"] = result.returncode
    return report


def _run_continuity_audit(video: Path, output: Path) -> dict:
    """Persist the conservative frame-continuity signal for every clip."""
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([
        sys.executable, str(Path(__file__).with_name("audit_frame_continuity.py")),
        "--video", str(video), "--output", str(output),
    ], cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)
    if output.is_file():
        try:
            report = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            report = {"status": "FAIL", "error": "frame continuity audit did not produce valid JSON"}
    else:
        report = {"status": "FAIL", "error": result.stderr[-1000:] or "frame continuity audit did not produce a report"}
    report["returncode"] = result.returncode
    return report


def _review_continuity(shot_id: str, pacing_report: dict, continuity_report: dict) -> dict:
    """Separate conservative frame spikes from an actual internal re-cut.

    The frame scanner intentionally over-flags high-contrast hand/screen
    motion.  A shot is still eligible for delivery only when pacing has passed
    and scene detection found no internal cut; the spike signal remains in the
    receipt for later director review instead of being silently discarded.
    """
    if pacing_report.get("status") != "PASS":
        return {"status": "FAIL", "reason": "pacing gate failed"}
    if int(pacing_report.get("internal_scene_cut_count", 0) or 0) != 0:
        return {"status": "FAIL", "reason": "internal scene cut detected"}
    spikes = int(continuity_report.get("spike_count", 0) or 0)
    if spikes:
        # A conservative scanner spike is a review request, not evidence that
        # a human/director accepted the shot.  Never synthesize a reviewer or
        # upgrade REVIEW_REQUIRED to PASS here.
        return {
            "status": "REVIEW_REQUIRED",
            "reason": "frame continuity spikes require explicit director review",
            "spike_count": spikes,
        }
    return {"status": "PASS", "reason": "no frame spikes detected", "spike_count": 0}


def _contract_shots(episode: dict) -> dict[str, dict]:
    """Load linked sidecar metadata without making the sidecar a second runner."""
    value = episode.get("six_module_contract")
    if not isinstance(value, str) or not value.strip():
        return {}
    path = (Path(episode["__episode_path"]).parent / value).resolve() if episode.get("__episode_path") else None
    if not path or not path.is_file():
        return {}
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(row.get("shot_id")): row for row in contract.get("shots", []) if isinstance(row, dict) and row.get("shot_id")}


def _episode_is_new_drama(episode: dict) -> bool:
    """Detect new-drama semantics without trusting a single legacy marker."""
    if episode.get("new_drama") is True or str(episode.get("production_semantics") or "") == "new_drama":
        return True
    brief = episode.get("creator_brief") if isinstance(episode.get("creator_brief"), dict) else {}
    if str(brief.get("production_semantics") or "") == "new_drama":
        return True
    shots = episode.get("shots") if isinstance(episode.get("shots"), list) else []
    return any(
        isinstance(shot, dict)
        and (shot.get("new_drama") is True or str(shot.get("production_semantics") or "") == "new_drama")
        for shot in shots
    )


def _validate_episode_creative_slice(episode: dict) -> dict:
    """Require a passed three-beat creative slice before new-drama expansion.

    This is intentionally an admission gate, not a creative evaluator.  The
    slice must already contain a local evidence clip and remain independent of
    Provider completion; without it the canonical executor must not fan out
    into a full episode.
    """
    if not _episode_is_new_drama(episode):
        return {"status": "SKIPPED", "reason": "episode is not marked new_drama"}
    acceptance = episode.get("acceptance") if isinstance(episode.get("acceptance"), dict) else {}
    candidates = [
        episode.get("creative_slice_receipt"),
        acceptance.get("creative_slice_receipt"),
    ]
    receipt_value = next((item for item in candidates if isinstance(item, str) and item.strip()), None)
    if not receipt_value:
        return {
            "status": "BLOCKED",
            "errors": ["new_drama episode requires acceptance.creative_slice_receipt before expansion"],
        }
    episode_path = Path(str(episode.get("__episode_path"))).resolve()
    receipt_path = (episode_path.parent / receipt_value).resolve()
    try:
        receipt_path.relative_to(episode_path.parent)
    except ValueError:
        return {"status": "BLOCKED", "errors": ["creative_slice_receipt escapes episode directory"]}
    if not receipt_path.is_file():
        return {"status": "BLOCKED", "errors": [f"creative_slice_receipt does not exist: {receipt_path}"]}
    try:
        result = load_and_validate(receipt_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return {"status": "BLOCKED", "errors": [f"creative_slice_receipt unreadable: {error}"]}
    return {"status": result.get("status", "BLOCKED"), "receipt": str(receipt_path), "errors": result.get("errors", [])}


def _audio_tracks(shot: dict) -> tuple[dict, list[dict], list[dict]]:
    audio = shot.get("audio_contract") if isinstance(shot.get("audio_contract"), dict) else {}
    dialogue = [item for item in audio.get("dialogue_tracks", []) if isinstance(item, dict)]
    inner = [item for item in audio.get("inner_monologue_tracks", []) if isinstance(item, dict)]
    return audio, dialogue, inner


def _external_master_path(shot: dict) -> Path | None:
    audio, dialogue, inner = _audio_tracks(shot)
    value = audio.get("master_audio_path") or audio.get("mixdown_path")
    if not value and len(dialogue) + len(inner) == 1:
        track = (dialogue + inner)[0]
        value = track.get("local_path") or track.get("path") or track.get("audio_path")
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value).expanduser()
    return path if path.is_file() else None


def _update_manifest_audio_master(manifest: Path, shot_id: str, receipt: dict) -> None:
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"audio master applied but manifest is unreadable: {manifest}") from exc
    rows = value if isinstance(value, list) else [value]
    found = False
    for row in rows:
        if isinstance(row, dict) and row.get("shot_id") == shot_id:
            row["artifact_sha256"] = receipt["output_sha256"]
            row["bytes"] = Path(str(receipt["output"])).stat().st_size
            row["audio_master"] = receipt
            found = True
            break
    if not found:
        raise SystemExit(f"audio master applied but manifest has no shot: {shot_id}")
    payload = rows if isinstance(value, list) else rows[0]
    fd, temp_name = tempfile.mkstemp(prefix=f".{manifest.name}.", suffix=".tmp", dir=str(manifest.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, manifest)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def _apply_external_audio_master(video: Path, shot: dict, manifest: Path, shot_id: str) -> dict:
    """Replace or strip Provider audio before any pacing or assembly audit."""
    audio, dialogue, inner = _audio_tracks(shot)
    has_spoken_audio = bool(dialogue or inner)
    master = _external_master_path(shot)
    if has_spoken_audio and master is None:
        raise SystemExit(f"{shot_id} has spoken audio but no local external master; Provider audio cannot be final")
    temp = video.with_name(f".{video.stem}.external-audio.mp4")
    if has_spoken_audio:
        receipt = replace_audio_track(video, master, temp)
    else:
        receipt = strip_audio_track(video, temp)
    os.replace(temp, video)
    receipt["output"] = str(video)
    _update_manifest_audio_master(manifest, shot_id, receipt)
    return receipt


def _validate_renderer_policy(episode: dict, render: dict) -> None:
    """Keep every production episode on the single verified Flash route."""
    model = str(render.get("model", ""))
    fallback = str(render.get("fallback_model", ""))
    if model and model != "agnes-video-2.5-flash":
        raise SystemExit(
            "production renderer is locked to agnes-video-2.5-flash; "
            f"received {model!r}"
        )
    if fallback:
        raise SystemExit(
            "production renderer fallback is disabled; retry or block on "
            f"agnes-video-2.5-flash instead of {fallback!r}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--identity-contract", type=Path, required=True,
                        help="validated asset/identity contract bound to this formal episode")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--media-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, help="optional local media-integrity review JSON")
    parser.add_argument("--preflight-output", type=Path,
                        help="where to persist the mandatory deterministic preflight receipt")
    parser.add_argument("--pacing-audit-dir", type=Path,
                        help="directory for mandatory per-shot audit_video_pacing receipts")
    parser.add_argument("--timeout", type=int, default=480)
    parser.add_argument(
        "--shot-retry-rounds", type=int, default=2,
        help="additional durable resume rounds after a transient clip failure",
    )
    parser.add_argument(
        "--shot-retry-delay", type=int, default=60,
        help="seconds between durable resume rounds",
    )
    args = parser.parse_args()
    contract_check = subprocess.run([
        sys.executable, str(Path(__file__).with_name("validate_short_drama_contract.py")),
        str(args.identity_contract),
    ], cwd=Path(__file__).resolve().parents[1])
    if contract_check.returncode:
        raise SystemExit("identity contract is invalid; no provider request submitted")
    episode_identity = json.loads(args.episode.read_text(encoding="utf-8"))
    episode_identity["__episode_path"] = str(args.episode.resolve())
    contract_identity = json.loads(args.identity_contract.read_text(encoding="utf-8"))
    if episode_identity.get("project_id") != contract_identity.get("project_id"):
        raise SystemExit("identity contract project_id does not match episode; no provider request submitted")
    creative_slice = _validate_episode_creative_slice(episode_identity)
    if creative_slice.get("status") not in {"PASS", "SKIPPED"}:
        raise SystemExit(
            "creative slice admission is BLOCKED; no provider request submitted. "
            + "; ".join(str(item) for item in creative_slice.get("errors", []))
        )
    preflight_output = args.preflight_output or args.manifest.with_name(args.manifest.stem + ".preflight.json")
    preflight = subprocess.run([
        sys.executable, str(Path(__file__).with_name("preflight_episode.py")), "--episode", str(args.episode),
        "--output", str(preflight_output), "--require-formal", "--require-measured-tts",
    ], cwd=Path(__file__).resolve().parents[1])
    if preflight.returncode:
        raise SystemExit(
            "episode preflight is BLOCKED/REWORK; no provider request submitted. "
            f"See {preflight_output}"
        )
    episode = episode_identity
    shots = episode.get("shots", [])
    defaults = episode.get("render_defaults", {})
    if not isinstance(defaults, dict):
        raise SystemExit("render_defaults must be an object when supplied")
    if not shots:
        raise SystemExit("episode has no shots")
    if args.shot_retry_rounds < 0 or args.shot_retry_delay < 1:
        raise SystemExit("shot retry rounds must be >= 0 and retry delay must be >= 1")
    _validate_asset_graph(shots)
    contract_shots = _contract_shots(episode)
    args.media_dir.mkdir(parents=True, exist_ok=True)
    shot_ids: list[str] = []
    for shot in shots:
        shot_id, prompt = shot.get("shot_id"), shot.get("prompt")
        if not shot_id or not prompt:
            raise SystemExit("every episode shot requires shot_id and prompt")
        shot_ids.append(shot_id)
        command = [
            sys.executable, "tools/run_short_clip.py", "--shot-id", shot_id,
            "--prompt", prompt, "--episode-contract", str(args.episode),
            "--manifest", str(args.manifest), "--output",
            str(args.media_dir / f"{shot_id}.mp4"), "--timeout", str(args.timeout),
            "--admission-scope", "production",
        ]
        render = {**defaults, **(shot.get("render", {}) if isinstance(shot.get("render"), dict) else {})}
        _validate_renderer_policy(episode, render)
        _append_option(command, "--model", render.get("model"))
        image = render.get("image")
        if image:
            image_path = (args.episode.parent / image).resolve() if not str(image).startswith(("http://", "https://", "data:")) else image
            _append_option(command, "--image", image_path)
        for field, flag in (
            ("width", "--width"), ("height", "--height"), ("num_frames", "--num-frames"),
            ("frame_rate", "--frame-rate"), ("seed", "--seed"),
            ("negative_prompt", "--negative-prompt"), ("seconds", "--seconds"),
            ("size", "--size"), ("aspect_ratio", "--aspect-ratio"),
            ("flash_mode", "--flash-mode"),
        ):
            _append_option(command, flag, render.get(field))
        _append_option(command, "--flash-first-frame-url", render.get("flash_first_frame_url"))
        _append_option(command, "--flash-last-frame-url", render.get("flash_last_frame_url"))
        _append_repeated_option(command, "--flash-reference-image-url", render.get("reference_image_urls"))
        _append_repeated_option(command, "--flash-reference-audio-url", render.get("reference_audio_urls"))
        result = subprocess.run(command)
        fallback_model = render.get("fallback_model")
        fallback_reason = _quota_exhausted(args.manifest, shot_id)
        fallback_on_failure = bool(render.get("fallback_on_failure"))
        if result.returncode and fallback_model and (fallback_reason or fallback_on_failure):
            raise SystemExit(
                "production renderer fallback is disabled; preserve the "
                "agnes-video-2.5-flash route and retry durably"
            )
        for retry_round in range(1, args.shot_retry_rounds + 1):
            if not result.returncode:
                break
            print(json.dumps({
                "status": "RETRYING_DURABLE_SHOT",
                "shot_id": shot_id,
                "retry_round": retry_round,
                "retry_in_seconds": args.shot_retry_delay,
            }, ensure_ascii=False), flush=True)
            time.sleep(args.shot_retry_delay)
            # run_short_clip reads the persisted manifest first: a task that
            # received a video_id resumes polling instead of submitting a
            # duplicate provider request.
            result = subprocess.run(command)
        if result.returncode:
            print(json.dumps({"status": "STOPPED", "failed_shot": shot_id}, ensure_ascii=False))
            return result.returncode
        # Agnes may return an AAC stream even when an external reference was
        # supplied, and may omit it on another take.  Neither outcome is a
        # deliverable audio policy.  Apply the contract-owned external master
        # (or strip audio for an explicitly silent shot) before any pacing/QC
        # or episode assembly reads the artifact.
        audio_contract_shot = dict(contract_shots.get(str(shot_id), {}))
        audio_contract_shot.update(shot)
        try:
            audio_receipt = _apply_external_audio_master(
                args.media_dir / f"{shot_id}.mp4", audio_contract_shot, args.manifest, str(shot_id)
            )
        except (OSError, ValueError, subprocess.CalledProcessError, SystemExit) as error:
            print(json.dumps({"status": "STOPPED", "failed_shot": shot_id, "reason": f"external audio master failed: {error}"}, ensure_ascii=False))
            return 1
        print(json.dumps({"status": "EXTERNAL_AUDIO_MASTER_APPLIED", "shot_id": shot_id, "receipt": audio_receipt}, ensure_ascii=False), flush=True)
        pacing_dir = args.pacing_audit_dir or args.manifest.parent / "pacing_audits"
        sidecar = contract_shots.get(str(shot_id), {})
        script = sidecar.get("script", {}) if isinstance(sidecar.get("script"), dict) else {}
        edit = sidecar.get("edit", {}) if isinstance(sidecar.get("edit"), dict) else {}
        tts_duration = script.get("tts_duration_seconds") if script.get("audio_status") == "MEASURED" else None
        expected_duration = edit.get("duration_seconds") if isinstance(edit.get("duration_seconds"), (int, float)) else None
        pacing_report = _run_pacing_audit(
            args.media_dir / f"{shot_id}.mp4", pacing_dir / f"{shot_id}.json",
            tts_duration=tts_duration, expected_duration=expected_duration,
            dialogue=script.get("audio_status") == "MEASURED",
            max_internal_cuts=0,
        )
        continuity_report = _run_continuity_audit(
            args.media_dir / f"{shot_id}.mp4", pacing_dir.parent / "continuity_audits" / f"{shot_id}.json"
        )
        continuity_review = _review_continuity(shot_id, pacing_report, continuity_report)
        print(json.dumps({"status": "SHOT_ACCEPTANCE_AUDIT", "shot_id": shot_id, "pacing": pacing_report.get("status"), "continuity": continuity_report.get("status"), "internal_scene_cut_count": pacing_report.get("internal_scene_cut_count"), "tts_duration_seconds": tts_duration}, ensure_ascii=False), flush=True)
        if pacing_report.get("status") != "PASS":
            print(json.dumps({"status": "STOPPED", "failed_shot": shot_id, "reason": "audit_video_pacing failed"}, ensure_ascii=False))
            return 1
        if continuity_review.get("status") != "PASS":
            print(json.dumps({"status": "STOPPED", "failed_shot": shot_id, "reason": "frame continuity audit failed"}, ensure_ascii=False))
            return 1
    duration_window = episode.get("acceptance", {}).get("duration_window_seconds", [45, 60])
    assembly_command = [
        sys.executable, "tools/assemble_episode.py", "--manifest", str(args.manifest),
        "--shot-ids", *shot_ids, "--output", str(args.output), "--min-seconds",
        str(duration_window[0]), "--max-seconds", str(duration_window[1]),
    ]
    if args.review_output:
        assembly_command.extend(["--review-output", str(args.review_output)])
    result = subprocess.run(assembly_command)
    if result.returncode == 0:
        pacing_dir = args.pacing_audit_dir or args.manifest.parent / "pacing_audits"
        final_report = _run_pacing_audit(
            args.output, pacing_dir / "final.json", dialogue=False,
            max_internal_cuts=max(0, len(shot_ids) - 1),
        )
        final_continuity = _run_continuity_audit(args.output, pacing_dir.parent / "continuity_audits" / "final.json")
        print(json.dumps({"status": "FINAL_ACCEPTANCE_AUDIT", "pacing": final_report.get("status"), "continuity": final_continuity.get("status"), "internal_scene_cut_count": final_report.get("internal_scene_cut_count")}, ensure_ascii=False), flush=True)
        if final_report.get("status") != "PASS":
            return 1
        if final_continuity.get("status") == "FAIL":
            return 1
        shot_pacing = []
        shot_continuity = []
        for shot_id in shot_ids:
            pacing_path = pacing_dir / f"{shot_id}.json"
            continuity_path = pacing_dir.parent / "continuity_audits" / f"{shot_id}.json"
            try:
                pacing = json.loads(pacing_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pacing = {"status": "FAIL", "error": "missing pacing receipt"}
            try:
                continuity = json.loads(continuity_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continuity = {"status": "FAIL", "error": "missing continuity receipt"}
            shot_pacing.append({"shot_id": shot_id, "status": pacing.get("status"), "receipt": str(pacing_path)})
            shot_continuity.append({"shot_id": shot_id, "status": continuity.get("status"), "spike_count": continuity.get("spike_count"), "receipt": str(continuity_path)})
        # Assembly boundaries can legitimately create a cross-shot luminance
        # spike.  The continuity gate therefore keys delivery on the
        # single-shot audits; the full-cut audit remains recorded for review.
        reviewed_shots = []
        for shot_id in shot_ids:
            pacing_path = pacing_dir / f"{shot_id}.json"
            continuity_path = pacing_dir.parent / "continuity_audits" / f"{shot_id}.json"
            try:
                pacing = json.loads(pacing_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pacing = {"status": "FAIL"}
            try:
                continuity = json.loads(continuity_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continuity = {"status": "FAIL"}
            reviewed_shots.append({"shot_id": shot_id, **_review_continuity(shot_id, pacing, continuity)})
        continuity_review = "PASS" if all(item["status"] == "PASS" for item in reviewed_shots) else "REVIEW_REQUIRED"
        contract_sidecars = list(contract_shots.values())
        audio_status = "PASS" if all(
            (item.get("script", {}).get("audio_status") in {"MEASURED", "NO_DIALOGUE"})
            for item in contract_sidecars
        ) else "UNKNOWN"
        delivery = delivery_gate({
            "media_integrity": "PASS" if final_report.get("status") == "PASS" else "FAIL",
            "continuity": continuity_review,
            "subtitle": episode.get("subtitle_status", "UNKNOWN"),
            "audio": episode.get("audio_status", audio_status),
            "creative": episode.get("creative_status", "UNKNOWN"),
        })
        acceptance = {
            "contract_version": "ace.video_kingdom.acceptance_receipt.v1",
            "status": delivery["status"],
            "delivery_approved": delivery["delivery_approved"],
            "output": str(args.output),
            "pacing": {"status": final_report.get("status"), "receipt": str(pacing_dir / "final.json"), "shots": shot_pacing},
            "continuity": {"status": continuity_review, "final_receipt": str(pacing_dir.parent / "continuity_audits" / "final.json"), "shots": shot_continuity, "review": reviewed_shots},
            "subtitle": delivery["statuses"]["subtitle"],
            "audio": delivery["statuses"]["audio"],
            "creative": delivery["statuses"]["creative"],
            "delivery_gate": delivery,
            "rule_summary": [
                "每镜必须通过 audit_video_pacing（内部切镜0、音频存在、TTS覆盖）",
                "每镜必须绑定 measured TTS 与 TTS+recovery hold 时长",
                "shot contract 锁定 single_action/max_primary_actions=1/internal_cuts_allowed=0",
                "逐帧连续性按单镜门禁；任何 spike 都保持 REVIEW_REQUIRED，等待显式导演决定",
            ],
        }
        acceptance_path = args.output.with_name("acceptance_receipt.json")
        acceptance_path.write_text(json.dumps(acceptance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "ACCEPTANCE_RECEIPT", "acceptance": acceptance["status"], "receipt": str(acceptance_path)}, ensure_ascii=False), flush=True)
        if not delivery["delivery_approved"]:
            return 1
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
