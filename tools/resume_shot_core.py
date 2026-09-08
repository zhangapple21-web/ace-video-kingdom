"""Poll-only recovery for an existing Shot Core submission."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.shot_core import resume_take


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--take-id", required=True)
    parser.add_argument("--output", type=Path, help="Optional new artifact path; never overwrites an existing file")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--poll-delay", type=int, default=3)
    args = parser.parse_args()
    result = resume_take(manifest_path=args.manifest, take_id=args.take_id, output_path=args.output, timeout=args.timeout, poll_delay=args.poll_delay)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("provider_status") == "SUCCESS" and result.get("status") == "REMOTE_COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
