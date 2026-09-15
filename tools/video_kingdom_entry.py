"""唯一公共入口：将视频王国需求送入统一控制面。

This facade never calls a media provider directly.  It classifies media
requests through the registered route or sends narrative work to the role
room.  Provider wrappers remain internal adapters and are not public workflow
entry points.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from production_control.media_routing import classify_media_intent, route_media_demand
from tools import role_room


def dispatch(*, text: str, out: Path, profile: str = "standard", project_id: str = "", execute: bool = False) -> dict[str, Any]:
    source = str(text or "").strip()
    if not source:
        raise ValueError("ENTRY_TEXT_REQUIRED")
    entry_id = "ENTRY-" + uuid.uuid4().hex[:12]
    intent = classify_media_intent(source)
    receipt: dict[str, Any] = {
        "schema": "video_kingdom.unified_entry_receipt.v1",
        "entry_id": entry_id,
        "entrypoint": "video-kingdom",
        "control_plane": "production_control",
        "request": source,
        "profile": profile,
        "project_id": project_id or None,
        "provider_submission": "NOT_PERFORMED",
    }
    if intent:
        route = route_media_demand(source, scope="current_control_plane")
        receipt.update({"dispatch": "media_route", "media_intent": intent, "route": route, "status": route.get("status") if route else "BLOCKED"})
    else:
        role_receipt = out.with_name(out.stem + ".role.json")
        role_args = ["--idea", source, "--out", str(role_receipt), "--profile", profile]
        if project_id:
            role_args.extend(["--project-id", project_id])
        if execute:
            role_args.append("--execute")
        role_status = role_room.main(role_args)
        receipt.update({"dispatch": "role_room", "role_receipt": str(role_receipt), "role_exit_code": role_status, "status": "COMPLETED" if role_status == 0 else "BLOCKED"})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", "--idea", dest="text", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--profile", choices=("rapid", "standard", "full_audit"), default="standard")
    parser.add_argument("--project-id", default="")
    parser.add_argument("--execute", action="store_true", help="仅对角色房间执行 OneAPI；媒体仍只生成路由收据")
    args = parser.parse_args(argv)
    try:
        receipt = dispatch(text=args.text, out=args.out, profile=args.profile, project_id=args.project_id, execute=args.execute)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": receipt["status"], "dispatch": receipt["dispatch"], "out": str(args.out)}, ensure_ascii=False))
    return 0 if receipt["status"] in {"COMPLETED", "ROUTED", "BLOCKED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
