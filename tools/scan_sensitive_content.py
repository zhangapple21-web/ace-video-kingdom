"""Scan a JSON/text input for secrets and personally identifiable information."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from production_control.privacy_scan import scan_value
except ImportError:
    from privacy_scan import scan_value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        raw = args.input.read_text(encoding="utf-8")
    except OSError as exc:
        parser.error(str(exc))
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = raw
    result = scan_value(value)
    print(json.dumps({"input": str(args.input), **result}, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "BLOCKED_PRIVACY" else 0


if __name__ == "__main__":
    raise SystemExit(main())
