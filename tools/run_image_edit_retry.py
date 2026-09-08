"""Run the bundled image-edit CLI with bounded, provider-aware retry.

Retries only transport/server failures.  Argument validation and authentication
failures stop immediately; every attempt is recorded in a JSON sidecar.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

def _transient(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in (
        "connection error", "server disconnected", "remoteprotocolerror",
        "timeout", "temporarily unavailable", "502", "503", "504",
        "rate limit", "429",
    ))


def _retry_after_seconds(text: str) -> float | None:
    """Extract a provider cooldown when a wrapped CLI surfaced one.

    The bundled image CLI normally does not expose response headers.  When a
    provider does surface ``Retry-After: N``, however, that value must win over
    a generic backoff interval rather than being ignored.
    """
    import re

    match = re.search(r"retry-after\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument(
        "--initial-delay", type=float, default=60,
        help="fallback cooldown when the provider does not return Retry-After (default: 60)",
    )
    parser.add_argument("--max-delay", type=float, default=900)
    parser.add_argument("--admission-receipt", type=Path,
                        help="hash-bound ADMITTED receipt required before invoking the wrapped Provider CLI")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    # This legacy wrapper cannot inspect or bind the payload of an arbitrary
    # child CLI to a canonical request.  A receipt by itself is therefore not
    # sufficient authority: keep the path explicitly closed until a bounded
    # adapter supplies the exact payload and asserts it immediately before the
    # child Provider call.
    raise SystemExit(
        "provider admission blocked: wrapped Provider CLI has no canonical payload adapter; "
        "no provider request submitted"
    )
    if args.max_attempts < 1 or args.initial_delay < 0 or args.max_delay < args.initial_delay:
        parser.error("invalid retry bounds")
    attempts: list[dict] = []
    for number in range(1, args.max_attempts + 1):
        started = datetime.now(timezone.utc).isoformat()
        result = subprocess.run(command, capture_output=True, text=True)
        combined = (result.stdout or "") + (result.stderr or "")
        row = {"attempt": number, "started_at": started, "returncode": result.returncode, "transient": result.returncode != 0 and _transient(combined), "output_tail": combined[-2000:]}
        attempts.append(row)
        args.log.parent.mkdir(parents=True, exist_ok=True)
        args.log.write_text(json.dumps({"command": command, "attempts": attempts, "status": "COMPLETED" if result.returncode == 0 else "RETRYING"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if result.returncode == 0:
            return 0
        if not row["transient"] or number == args.max_attempts:
            args.log.write_text(json.dumps({"command": command, "attempts": attempts, "status": "FAILED_FINAL"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return result.returncode or 1
        provider_delay = _retry_after_seconds(combined)
        delay = min(provider_delay if provider_delay is not None else args.initial_delay * (2 ** (number - 1)), args.max_delay)
        attempts[-1]["retry_delay_source"] = "provider_retry_after" if provider_delay is not None else "provider_profile_fallback"
        attempts[-1]["retry_in_seconds"] = delay
        args.log.write_text(json.dumps({"command": command, "attempts": attempts, "status": "RETRYING"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        time.sleep(delay)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
