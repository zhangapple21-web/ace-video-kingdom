"""Bounded Shenwen route re-test with fail-closed health handling.

This performs at most one tiny chat request.  It never falls back to an image
key, never prints credentials, and records a result without claiming a route
is healthy when the correct ``SHENWEN_API_KEY`` is unavailable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from production_control import load_provider_health_snapshot, route_model_demand


DEFAULT_STATE = Path(r"C:\tmp\ace_core\06_RUNTIME\ace\data\miner_pool\provider_watchdog\watchdog_state.json")


def _request(base_url: str, key: str, model: str, timeout: float) -> tuple[bool, str, int]:
    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": "Return only OK."}], "max_tokens": 8}).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = str(body.get("choices", [{}])[0].get("message", {}).get("content", ""))
        return text.strip().upper() == "OK", "", int((time.perf_counter() - started) * 1000)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as exc:
        return False, type(exc).__name__, int((time.perf_counter() - started) * 1000)


def run(*, state_path: Path = DEFAULT_STATE, timeout: float = 20.0) -> dict[str, Any]:
    key = os.environ.get("SHENWEN_API_KEY", "").strip()
    snapshot = load_provider_health_snapshot(state_path)
    route = route_model_demand("请做复杂长链导演规划", scope="remote_shenwen", health_snapshot=snapshot)
    result: dict[str, Any] = {
        "schema": "video_kingdom.remote_route_retest.v1",
        "provider": "shenwen",
        "model": "gpt-6-astra",
        "state_path": str(state_path),
        "route_before_probe": {"status": route.get("status"), "reason": route.get("reason"), "health_action": route.get("health_action")},
        "attempted": False,
        "status": "BLOCKED_MISSING_SHENWEN_API_KEY" if not key else "PENDING",
        "secret_recorded": False,
    }
    if not key:
        return result
    ok, error, latency_ms = _request("https://api.shenwenai.com/v1", key, "gpt-6-astra", timeout)
    result.update({"attempted": True, "status": "PASS" if ok else "FAIL", "latency_ms": latency_ms, "error": error or None})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args(argv)
    result = run(state_path=args.state, timeout=args.timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "attempted": result["attempted"], "out": str(args.out)}, ensure_ascii=False))
    return 0 if result["status"] in {"PASS", "BLOCKED_MISSING_SHENWEN_API_KEY"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
