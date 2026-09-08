"""Read-only handshake across ACE/R1/Video Kingdom evidence bases.

This is a diagnostic, not a scheduler or router. It proves that the bases are
reachable and that their identity/receipt files can be read without copying
private payloads or starting provider work.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def git_head(path: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "log", "-1", "--format=%H"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def file_digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    bases = {
        "video_kingdom": root,
        "ace_core": Path("C:/tmp/ace_core"),
        "r1": Path("C:/tmp/R1"),
        "r1_archaeology": Path("C:/tmp/r1-archaeology"),
        "mine_seed": Path("C:/tmp/mine-seed"),
    }
    files = {
        "video_kingdom_index": root / "research/R1_DISTRIBUTED_BASE_INDEX.v1.json",
        "street_ledger": root / "research/street_visit_ledger.v1.json",
        "dispatch_receipts": root / "research/dispatch_receipts.v1.jsonl",
        "ace_registry": Path("C:/tmp/ace_core/08_GOVERNANCE/provider_registry/registry.json"),
    }
    result = {
        "contract_version": "ace.video_kingdom.cross_base_handshake.v1",
        "at": datetime.now(timezone.utc).isoformat(),
        "production_integration": False,
        "bases": {
            name: {"exists": path.is_dir(), "git_head": git_head(path)}
            for name, path in bases.items()
        },
        "files": {
            name: {"exists": path.is_file(), "sha256": file_digest(path)}
            for name, path in files.items()
        },
        "local_handshakes": {
            "oneapi_127_0_0_1_3000": port_open("127.0.0.1", 3000),
            "ace_proxy_127_0_0_1_3001": port_open("127.0.0.1", 3001),
        },
        "status": "HANDSHAKE_OK",
        "notes": [
            "Reachability and hash continuity only; no provider call was made.",
            "A closed local port is recorded as a failed live handshake, not hidden by historical registry metadata.",
        ],
    }
    if not all(item["exists"] for item in result["bases"].values()):
        result["status"] = "HANDSHAKE_PARTIAL"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{result['status']} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

