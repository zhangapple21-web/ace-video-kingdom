"""Provider-free cross-process recovery rehearsal for Shot Core.

The rehearsal uses two real child Python processes and a deterministic fake
HTTP session.  Child one persists a poll checkpoint and then exits abruptly;
child two reloads the same manifest and completes the existing video_id using
poll-only recovery.  No network request is made and no Provider job is
created.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _response(body: dict[str, Any], *, content: bytes = b"", content_type: str = "video/mp4") -> Any:
    class Response:
        status_code = 200
        headers = {"content-type": content_type}
        text = json.dumps(body)

        def json(self) -> dict[str, Any]:
            return body

        @property
        def content(self) -> bytes:
            return content

    return Response()


class _FakeSession:
    def __init__(self, phase: str) -> None:
        self.phase = phase
        self.polls = 0
        self.posts = 0

    def post(self, *_args: Any, **_kwargs: Any) -> Any:
        self.posts += 1
        raise AssertionError("cross-process recovery must never POST")

    def get(self, url: str, *_args: Any, **_kwargs: Any) -> Any:
        if "agnesapi" in url:
            self.polls += 1
            if self.phase == "crash" and self.polls >= 2:
                raise SystemExit(17)
            if self.phase == "crash":
                return _response({"status": "processing"})
            return _response({"status": "completed", "url": "https://fake.invalid/recovered.mp4"})
        return _response({}, content=b"cross-process-recovered-video")


def _shot_snapshot() -> dict[str, Any]:
    return {
        "contract": {"render_seconds": 6, "camera": {"internal_cuts": 0}},
        "audio": {"dialogue": [], "dialogue_duration": 0, "action_duration": 4, "hold_duration": 1},
        "media_profile": {"width": 720, "height": 1280, "fps": 24},
    }


def _child(args: argparse.Namespace) -> int:
    import runtime.shot_core as core

    # The fake bytes are intentionally not a video.  This rehearsal validates
    # cross-process state/recovery semantics, so media parsing is deterministic
    # and explicitly isolated from the provider-free test.
    core._probe = lambda _path: {  # type: ignore[method-assign]
        "duration_seconds": 6.0,
        "width": 720,
        "height": 1280,
        "fps": "24/1",
        "has_audio": False,
    }
    core.machine_qc = lambda *_a, **_k: {  # type: ignore[method-assign]
        "file_integrity": "PASS",
        "resolution": "PASS",
        "fps": "PASS",
        "duration": "PASS",
        "black_frames": "PASS",
        "freeze_tail": "PASS",
        "internal_cuts": "PASS",
    }
    session = _FakeSession(args.phase)
    result = core.resume_take(
        manifest_path=Path(args.manifest),
        take_id=args.take_id,
        output_path=Path(args.output) if args.output else None,
        api_key="provider-free-test",
        timeout=5,
        poll_delay=1,
        session=session,
    )
    print(json.dumps({"polls": session.polls, "posts": session.posts, "result": result}, ensure_ascii=False))
    return 0


def _run_child(manifest: Path, take_id: str, *, phase: str, output: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(Path(__file__).resolve()), "--child", "--manifest", str(manifest), "--take-id", take_id, "--phase", phase]
    if output is not None:
        command.extend(["--output", str(output)])
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=False)


def run_rehearsal() -> dict[str, Any]:
    from runtime.shot_core import file_hash, load_manifest, save_manifest

    with tempfile.TemporaryDirectory(prefix="shot-core-cross-process-") as temp:
        work = Path(temp)
        manifest_path = work / "manifest.json"
        output_path = work / "recovered.mp4"
        take_id = "CROSS_PROCESS_T01"
        manifest = {
            "schema": "video_kingdom.shot_core_cross_process_recovery.v1",
            "shots": {"CROSS_PROCESS": {"shot_id": "CROSS_PROCESS", "lifecycle": "RECONCILE", "stale": False}},
            "takes": [{
                "take_id": take_id,
                "shot_id": "CROSS_PROCESS",
                "video_id": "vid-cross-process-existing",
                "provider_status": "UNKNOWN",
                "status": "RUNNING",
                "selected": False,
                "reconcile_required": True,
                "shot_snapshot": _shot_snapshot(),
            }],
            "events": [],
        }
        save_manifest(manifest_path, manifest)
        before = load_manifest(manifest_path)
        crash = _run_child(manifest_path, take_id, phase="crash")
        after_crash = load_manifest(manifest_path)
        crash_take = after_crash["takes"][0]
        final = _run_child(manifest_path, take_id, phase="finalize", output=output_path)
        after_final = load_manifest(manifest_path)
        final_take = after_final["takes"][0]
        final_stdout = final.stdout.strip().splitlines()[-1] if final.stdout.strip() else "{}"
        child_report = json.loads(final_stdout)
        return {
            "schema": "video_kingdom.shot_core_cross_process_recovery.v1",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "provider_calls": 0,
            "provider_submission": "NOT_SENT",
            "crash_child_exit_code": crash.returncode,
            "crash_child_expected_exit_code": 17,
            "manifest_revision_before": before.get("manifest_revision"),
            "manifest_revision_after_crash": after_crash.get("manifest_revision"),
            "checkpoint_after_crash": {
                "status": crash_take.get("status"),
                "provider_status": crash_take.get("provider_status"),
                "video_id": crash_take.get("video_id"),
                "last_state": crash_take.get("last_state"),
                "reconcile_required": crash_take.get("reconcile_required"),
            },
            "final_child_exit_code": final.returncode,
            "final_child": child_report,
            "manifest_revision_final": after_final.get("manifest_revision"),
            "final_take": {
                "status": final_take.get("status"),
                "provider_status": final_take.get("provider_status"),
                "video_id": final_take.get("video_id"),
                "artifact_finalize_status": final_take.get("artifact_finalize_status"),
                "artifact_hash": final_take.get("artifact_hash"),
                "selected": final_take.get("selected"),
                "reconcile_required": final_take.get("reconcile_required"),
            },
            "artifact_sha256": file_hash(output_path) if output_path.is_file() else None,
            "artifact_bytes": output_path.stat().st_size if output_path.is_file() else None,
            "assertions": {
                "crash_checkpoint_persisted": crash.returncode == 17 and crash_take.get("video_id") == "vid-cross-process-existing" and crash_take.get("last_state") == "processing",
                "resume_child_completed": final.returncode == 0 and final_take.get("status") == "GENERATED",
                "poll_only": child_report.get("posts") == 0,
                "artifact_finalized": final_take.get("artifact_finalize_status") == "PASS" and bool(final_take.get("artifact_hash")),
                "selection_boundary_preserved": final_take.get("selected") is False,
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--manifest")
    parser.add_argument("--take-id")
    parser.add_argument("--output")
    parser.add_argument("--phase", choices=("crash", "finalize"))
    args = parser.parse_args()
    if args.child:
        return _child(args)
    receipt = run_rehearsal()
    receipt_path = ROOT / "research" / "shot_core_cross_process_recovery.v1.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if all(receipt["assertions"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
