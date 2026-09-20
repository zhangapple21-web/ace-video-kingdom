"""Compile the canonical shot-lineage document from an episode and receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(value: Any, base: Path) -> Path | None:
    if isinstance(value, dict):
        value = value.get("path") or value.get("file")
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def _ref(path: Path | None, *, fallback: str = "") -> dict[str, str]:
    if path and path.is_file():
        return {"path": str(path), "sha256": _sha256(path), "status": "PRESENT"}
    return {"path": str(path) if path else fallback, "sha256": "", "status": "MISSING"}


def _load(path: Path | None) -> dict[str, Any]:
    if not path or not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _receipt_row(manifest: Any, shot_id: str) -> dict[str, Any]:
    rows = manifest if isinstance(manifest, list) else [manifest]
    return next((row for row in rows if isinstance(row, dict) and str(row.get("shot_id")) == shot_id), {})


def build_lineage(episode_path: Path, manifest_path: Path, *, review_path: Path | None = None, output_path: Path | None = None, overrides: dict[str, Path] | None = None) -> dict[str, Any]:
    episode = _load(episode_path)
    base = episode_path.parent.resolve()
    manifest = _load(manifest_path)
    contract_path = _resolve(episode.get("six_module_contract"), base)
    contract = _load(contract_path)
    sidecars = {str(row.get("shot_id")): row for row in contract.get("shots", []) if isinstance(row, dict) and row.get("shot_id")}
    review = _load(review_path)
    overrides = overrides or {}

    def candidate(name: str, *values: Any) -> Path | None:
        if name in overrides:
            return overrides[name]
        for value in values:
            path = _resolve(value, base)
            if path:
                return path
        return None

    screenplay = episode.get("screenplay_source") or episode.get("script")
    script_path = _resolve(screenplay, base)
    structure_path = candidate("script_structure", episode.get("script_structure"), episode.get("structure_path"))
    storyboard_path = candidate("storyboard", episode.get("storyboard"), episode.get("storyboard_path"))
    prompt_path = candidate("prompt_contract", episode.get("prompt_contract"), episode.get("generation_contract"), episode.get("contract_index"))
    asset_path = candidate("asset_manifest", episode.get("asset_manifest"), episode.get("identity_contract"))
    audio_path = candidate("audio_timeline", episode.get("audio_timeline"), episode.get("audio_contract"))
    review_path = review_path.resolve() if review_path else None

    lines: list[dict[str, Any]] = []
    shots = episode.get("shots") if isinstance(episode.get("shots"), list) else []
    for shot in shots:
        if not isinstance(shot, dict) or not shot.get("shot_id"):
            continue
        shot_id = str(shot["shot_id"])
        sidecar = sidecars.get(shot_id, {})
        merged = {**sidecar, **shot}
        audio = merged.get("audio_contract") if isinstance(merged.get("audio_contract"), dict) else {}
        if not audio and isinstance(merged.get("audio"), dict):
            audio = merged["audio"]
        tracks = [item for item in audio.get("dialogue_tracks", []) + audio.get("inner_monologue_tracks", []) if isinstance(item, dict)]
        if not tracks:
            # Current EP01 contracts call these candidate_tracks and keep the
            # exact transcript in receipt_text.  Treat them as source evidence
            # without pretending a candidate is already the selected take.
            tracks = [item for item in audio.get("candidate_tracks", []) if isinstance(item, dict)]
        dialogue_texts = [str(item) for item in merged.get("dialogue", []) if isinstance(item, str)]
        inner_texts = [str(item) for item in merged.get("inner_monologue", []) if isinstance(item, str)]
        row = _receipt_row(manifest, shot_id)
        artifact = str(row.get("artifact_path") or row.get("output") or "")
        artifact_path = _resolve(artifact, manifest_path.parent) if artifact else None
        artifact_hash = str(row.get("artifact_sha256") or "")
        if artifact_path and artifact_path.is_file() and not artifact_hash:
            artifact_hash = _sha256(artifact_path)
        receipt_id = str(row.get("receipt_id") or row.get("video_id") or row.get("request_hash") or "")
        qc = row.get("qc") if isinstance(row.get("qc"), dict) else {}
        review_status = "PASS" if qc and all(str(value).upper() == "PASS" for value in qc.values()) else "UNVERIFIED"
        selected = bool(row.get("selected") is True or row.get("lifecycle") == "SELECTED")
        take_id = str(row.get("take_id") or f"{shot_id}_PENDING")
        version_id = str(review.get("delivery_version_id") or review.get("version_id") or "PENDING")
        for index, track in enumerate(tracks, start=1):
            track_id = str(track.get("track_id") or f"{shot_id}_LINE_{index:02d}")
            track_path = _resolve(track.get("local_path") or track.get("path") or track.get("audio_path"), base)
            track_hash = str(track.get("sha256") or "")
            if track_path and track_path.is_file() and not track_hash:
                track_hash = _sha256(track_path)
            text = str(track.get("text") or track.get("transcript") or track.get("receipt_text") or "")
            if not text:
                source_texts = inner_texts if "inner" in str(track.get("role") or "").lower() else dialogue_texts
                if source_texts:
                    text = source_texts[min(index - 1, len(source_texts) - 1)]
            track_type = str(track.get("track_type") or ("INNER_MONOLOGUE" if "inner" in str(track.get("track_id", "")).lower() else "DIALOGUE")).upper()
            speaker = str(track.get("speaker") or merged.get("speaker") or "")
            lines.append({
                "line_id": track_id,
                "text": text,
                "track_type": track_type,
                "shot_id": shot_id,
                "character_id": str(track.get("character_id") or track.get("role_id") or speaker),
                "speaker": speaker,
                "voice_id": str(track.get("voice_id") or track.get("voice") or "UNKNOWN"),
                "audio_track_id": track_id,
                "audio": {
                    "path": str(track_path) if track_path else str(track.get("local_path") or ""),
                    "sha256": track_hash,
                    "duration_seconds": track.get("duration_seconds"),
                    "reference_audio_urls": (merged.get("render") or {}).get("reference_audio_urls", []) if isinstance(merged.get("render"), dict) else [],
                },
                "generation_receipt_id": receipt_id,
                "video_id": str(row.get("video_id") or ""),
                "video_artifact_path": artifact,
                "video_artifact_sha256": artifact_hash,
                "review_receipt_ids": [str((review_path or manifest_path).name)],
                "review_status": review_status,
                "take_id": take_id,
                "selected": selected,
                "delivery_version_id": version_id,
            })

    assembly = review.get("output") or review.get("assembly_path") or ""
    assembly_path = _resolve(assembly, review_path.parent if review_path else base) if assembly else None
    assembly_hash = str(review.get("artifact_sha256") or review.get("output_sha256") or "")
    if assembly_path and assembly_path.is_file() and not assembly_hash:
        assembly_hash = _sha256(assembly_path)
    status = str(review.get("delivery_status") or ("APPROVED_MASTER" if review.get("delivery_approved") is True else "BLOCKED")).upper()
    document = {
        "schema": "ace.video_kingdom.shot_lineage.v1",
        "episode_id": str(episode.get("project_id") or episode.get("title") or episode_path.stem),
        "script_revision_id": str(episode.get("revision_id") or episode.get("script_revision_id") or "UNKNOWN"),
        "script": _ref(script_path, fallback=str(screenplay.get("path") if isinstance(screenplay, dict) else screenplay or "")),
        "script_structure": _ref(structure_path),
        "storyboard": _ref(storyboard_path),
        "prompt_contract": _ref(prompt_path),
        "asset_manifest": _ref(asset_path),
        "audio_timeline": _ref(audio_path),
        "review_record": _ref(review_path),
        "generation_receipt": _ref(manifest_path.resolve()),
        "lines": lines,
        "delivery": {
            "status": status,
            "version_id": str(review.get("version_id") or review.get("delivery_version_id") or "PENDING"),
            "assembly_path": str(assembly_path) if assembly_path else str(assembly),
            "assembly_sha256": assembly_hash,
            "selected_take_ids": [line["take_id"] for line in lines if line.get("selected")],
        },
        "source_receipts": {"episode": str(episode_path.resolve()), "manifest": str(manifest_path.resolve())},
    }
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a canonical shot-lineage contract")
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--review-record", type=Path)
    parser.add_argument("--script-structure", type=Path)
    parser.add_argument("--storyboard", type=Path)
    parser.add_argument("--prompt-contract", type=Path)
    parser.add_argument("--asset-manifest", type=Path)
    parser.add_argument("--audio-timeline", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    overrides = {
        name: path for name, path in {
            "script_structure": args.script_structure,
            "storyboard": args.storyboard,
            "prompt_contract": args.prompt_contract,
            "asset_manifest": args.asset_manifest,
            "audio_timeline": args.audio_timeline,
        }.items() if path
    }
    document = build_lineage(args.episode, args.manifest, review_path=args.review_record, output_path=args.output, overrides=overrides)
    print(json.dumps({"status": "BUILT", "output": str(args.output.resolve()), "line_count": len(document["lines"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
