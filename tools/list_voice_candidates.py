"""List registered voice candidates without silently changing a role binding."""

import argparse
import json
from pathlib import Path


DEFAULT_REGISTRY = Path(__file__).resolve().parents[1] / "research" / "voice_candidate_registry.v1.json"


def load_candidates(registry: Path, status: str | None = None) -> list[dict]:
    payload = json.loads(registry.read_text(encoding="utf-8"))
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("voice candidate registry has no candidates list")
    if status:
        candidates = [item for item in candidates if item.get("status") == status]
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="列出视频王国已登记的声音候选")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--status", help="按候选状态过滤")
    parser.add_argument("--id", dest="candidate_id", help="只显示一个候选 ID")
    args = parser.parse_args()
    candidates = load_candidates(args.registry, args.status)
    if args.candidate_id:
        candidates = [item for item in candidates if item.get("id") == args.candidate_id]
    print(json.dumps(candidates, ensure_ascii=False, indent=2))
    return 0 if candidates else 1


if __name__ == "__main__":
    raise SystemExit(main())
