"""Compile authored original-desk works into the public reader snapshot.

Authored source lives in ``originals_source/<work_id>/``. This script renders
each episode's structured blocks into reader HTML, writes the public episode
files, and reconciles ``data/originals/desk.json``.

Three properties matter more than convenience here:

1. Deterministic. Rendering the same source twice produces byte-identical
   output, so re-running is safe and a diff means a real change.
2. Idempotent and additive. Existing works in ``desk.json`` are never
   rewritten or reordered; only the works declared in ``originals_source``
   are reconciled. A work already listed keeps its catalog position and gains
   only new episodes.
3. Fail closed. A work missing a title, a log line, cast, or episode numbering
   is refused before anything is written. Publishing a half-formed original to
   a public reader is worse than not publishing it.

This is a publication boundary only. It does not enter the video production
chain, does not call any provider, and never reads sandbox output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from tools.atomic_io import atomic_write_text

sys.stdout.reconfigure(encoding="utf-8")  # Bug #1 fix: prevent UnicodeEncodeError on GBK console

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "originals_source"
PUBLIC = ROOT / "public" / "data" / "originals"
DESK = PUBLIC / "desk.json"

# Block kinds the renderer knows. An unknown kind is a source error, not
# something to pass through as text.
BLOCK_KINDS = {"scene", "cast", "para", "line", "hook", "note"}

EP_RE = re.compile(r"^ep\d{2,}$")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(path, text, encoding="utf-8")


def escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render_blocks(blocks: list[dict[str, Any]], work: dict[str, Any], ep: dict[str, Any]) -> str:
    """Render structured episode blocks into reader HTML.

    Block shapes:
      scene  {"k":"scene","place":str,"time":str,"light":str}
      cast   {"k":"cast","present":[str],"absent":[str]}
      para   {"k":"para","t":str}
      line   {"k":"line","who":str,"stage":str?,"t":str}
      hook   {"k":"hook","t":str}
      note   {"k":"note","t":str}
    """
    out: list[str] = []
    for index, block in enumerate(blocks, 1):
        kind = block.get("k")
        if kind not in BLOCK_KINDS:
            raise SystemExit(
                f"{work['id']}/{ep['id']}: block {index} has unknown kind {kind!r}; "
                f"allowed: {sorted(BLOCK_KINDS)}"
            )
        if kind == "scene":
            place = str(block["place"]).strip()
            time = str(block["time"]).strip()
            light = str(block.get("light", "")).strip()
            out.append(f"<h3>场景｜{escape(place)} · {escape(time)}</h3>")
            if light:
                out.append(f"<p><em>光｜{escape(light)}</em></p>")
        elif kind == "cast":
            present = "、".join(block.get("present", []))
            absent = "、".join(block.get("absent", []))
            out.append(f"<p><b>在场</b>：{escape(present)}</p>")
            if absent:
                out.append(f"<p><b>未出场</b>：{escape(absent)}</p>")
        elif kind == "para":
            out.append(f"<p>{escape(str(block['t']).strip())}</p>")
        elif kind == "line":
            who = escape(str(block["who"]).strip())
            stage = str(block.get("stage", "")).strip()
            head = f"<b>{who}</b>" + (f"（{escape(stage)}）" if stage else "")
            out.append(f"<p>{head}：{escape(str(block['t']).strip())}</p>")
        elif kind == "hook":
            out.append(f"<p><b>钩子</b>：{escape(str(block['t']).strip())}</p>")
        elif kind == "note":
            out.append(f"<p><em>{escape(str(block['t']).strip())}</em></p>")
    return "".join(out)


def validate_work(work: dict[str, Any]) -> None:
    work_id = work.get("id", "<missing id>")
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,31}", str(work_id)):
        raise SystemExit(f"{work_id}: work id must be lowercase alnum+dash, 3-32 chars")
    for field in ("title", "tone", "format", "status", "logline"):
        if not str(work.get(field, "")).strip():
            raise SystemExit(f"{work_id}: missing required field {field!r}")
    if not isinstance(work.get("chars"), list) or not work["chars"]:
        raise SystemExit(f"{work_id}: 'chars' must be a non-empty list")
    episodes = work.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        raise SystemExit(f"{work_id}: 'episodes' must be a non-empty list")
    seen_ids: set[str] = set()
    numbers: list[int] = []
    for ep in episodes:
        ep_id = str(ep.get("id", ""))
        if not EP_RE.match(ep_id):
            raise SystemExit(f"{work_id}: bad episode id {ep_id!r}; expected epNN")
        if ep_id in seen_ids:
            raise SystemExit(f"{work_id}: duplicate episode id {ep_id}")
        seen_ids.add(ep_id)
        if not str(ep.get("title", "")).strip():
            raise SystemExit(f"{work_id}/{ep_id}: missing 'title'")
        if not str(ep.get("beat", "")).strip():
            raise SystemExit(f"{work_id}/{ep_id}: missing 'beat' (one line of visible change)")
        blocks = ep.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            raise SystemExit(f"{work_id}/{ep_id}: 'blocks' must be a non-empty list")
        if not any(isinstance(b, dict) and b.get("k") == "hook" for b in blocks):
            raise SystemExit(f"{work_id}/{ep_id}: needs a closing 'hook' block")
        try:
            number = int(ep["no"])
        except (KeyError, TypeError, ValueError):
            raise SystemExit(f"{work_id}/{ep_id}: missing integer 'no'") from None
        numbers.append(number)
    if numbers != sorted(numbers):
        raise SystemExit(f"{work_id}: episodes must be listed in ascending 'no' order")
    if numbers != list(range(1, len(numbers) + 1)):
        raise SystemExit(f"{work_id}: episode numbering must be 1..{len(numbers)} with no gaps")


def load_sources() -> list[dict[str, Any]]:
    if not SOURCE.is_dir():
        raise SystemExit(f"authored source directory missing: {SOURCE}")
    works: list[dict[str, Any]] = []
    for work_file in sorted(SOURCE.glob("*/work.json")):
        work = read_json(work_file)
        work.setdefault("id", work_file.parent.name)
        validate_work(work)
        works.append(work)
    if not works:
        raise SystemExit(f"no works declared under {SOURCE}")
    ids = [w["id"] for w in works]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate work ids across originals_source")
    return works


def load_quarantine() -> dict[tuple[str, str], str]:
    """Return {(work_id, ep_id): reason} for episodes held back from publishing.

    Quarantine exists because the audit gate was found to have been bypassable
    (2026-10-07), which left eight episodes live carrying FAIL verdicts. Rather
    than delete authored work — it is the only copy, and a continuity defect is
    usually fixable — a failed episode is held out of the published tree and out
    of ``desk.json`` while staying in ``work.json`` to be repaired. Removing the
    entry from quarantine republishes it, which keeps the decision reversible and
    explicit instead of a manual edit someone has to remember to undo.

    A malformed quarantine file is fatal by design: silently publishing what a
    broken file failed to exclude is the exact failure mode being prevented.
    """
    path = ROOT / "quarantine.json"
    if not path.is_file():
        return {}
    try:
        # utf-8-sig, not utf-8: PowerShell's `Set-Content -Encoding UTF8` writes a
        # BOM, and a hand-edited control file on Windows is very likely to have
        # one. Genuinely broken JSON still fails below, which is the case that
        # matters — refusing to publish is correct there, refusing over a BOM is
        # just an outage waiting to happen.
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"quarantine.json unreadable ({exc}); refusing to publish "
                         "while the hold-back list cannot be read") from None
    entries = data.get("held") if isinstance(data, dict) else data
    out: dict[tuple[str, str], str] = {}
    for item in entries or []:
        work, episode = item.get("work"), item.get("episode")
        if not work or not episode:
            raise SystemExit(f"quarantine.json entry missing work/episode: {item!r}")
        out[(work, episode)] = item.get("reason", "")
    return out


def build(check_only: bool = False) -> dict[str, Any]:
    works = load_sources()
    quarantine = load_quarantine()
    desk = read_json(DESK)
    existing: dict[str, dict[str, Any]] = {w["id"]: w for w in desk.get("works", [])}

    receipts: list[dict[str, Any]] = []
    # Copy each slot dict so reconcile-in-place does not alias desk["works"];
    # otherwise planned_desk compares equal to the source and a changed episode
    # list is never written back.
    planned_desk: list[dict[str, Any]] = [dict(w) for w in desk.get("works", [])]

    for work in works:
        work_id = work["id"]
        live_eps = [ep for ep in work["episodes"] if (work_id, ep["id"]) not in quarantine]
        entry: dict[str, Any] = {
            "id": work_id,
            "title": work["title"],
            "tone": work["tone"],
            "format": work["format"],
            "status": work["status"],
            "logline": work["logline"],
            "chars": list(work["chars"]),
            "episodes": [
                {"id": ep["id"], "no": int(ep["no"]), "title": ep["title"], "beat": ep["beat"],
                 "file": f"data/originals/{work_id}/{ep['id']}.json"}
                for ep in live_eps
            ],
        }
        if work.get("packs"):
            entry["packs"] = work["packs"]
        if work.get("assets"):
            entry["assets"] = work["assets"]

        written: list[dict[str, Any]] = []
        for ep in work["episodes"]:
            # A held-back episode is never rendered into public/. An old file may
            # still be sitting there from before it was quarantined, so remove it
            # explicitly: leaving it would keep a FAIL episode reachable by direct
            # URL even though desk.json no longer lists it.
            if (work_id, ep["id"]) in quarantine:
                stale = PUBLIC / work_id / f"{ep['id']}.json"
                if stale.is_file():
                    if not check_only:
                        stale.unlink()
                    written.append({"episode": ep["id"], "action": "QUARANTINED"})
                continue
            html = render_blocks(ep["blocks"], work, ep)
            payload = {
                "id": ep["id"],
                "work_id": work_id,
                # `no` is what build_context_bundle.py sorts on and what the
                # bundle prints in its summary table. Without it every episode
                # fell back to 0 and the table read "ep00" for all of them,
                # which made the narrative auditor compare an episode against
                # itself.
                "no": int(ep["no"]),
                "title": f"第{int(ep['no']):02d}集 {ep['title']}",
                "html": html,
            }
            body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            target = PUBLIC / work_id / f"{ep['id']}.json"
            if check_only:
                current = target.read_text(encoding="utf-8") if target.is_file() else None
                if current != body:
                    written.append({"episode": ep["id"], "action": "WOULD_UPDATE", "sha256": digest})
                continue
            changed = not target.is_file() or target.read_text(encoding="utf-8") != body
            if changed:
                target.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_text(target, body, encoding="utf-8")
            written.append({
                "episode": ep["id"],
                "action": "UPDATED" if changed else "UNCHANGED",
                "sha256": digest,
            })

        if work_id in existing:
            # Keep the catalog slot, but take the fresh episode list and copy.
            slot = planned_desk[next(i for i, w in enumerate(planned_desk) if w["id"] == work_id)]
            slot.clear()
            slot.update(entry)
            action = "RECONCILED"
        else:
            planned_desk.append(entry)
            action = "ADDED"

        receipts.append({
            "work": work_id,
            "title": work["title"],
            "action": action if not check_only else action + "_CHECK_ONLY",
            "episodes": len(work["episodes"]),
            "files": written,
        })

    if check_only:
        return {"status": "CHECK_ONLY", "works": receipts}

    if planned_desk != desk.get("works", []):
        desk["works"] = planned_desk
        write_json(DESK, desk)
        desk_action = "UPDATED"
    else:
        desk_action = "UNCHANGED"

    return {
        "status": "PUBLISHED",
        "desk": desk_action,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "works": receipts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true",
                        help="validate sources and report drift without writing")
    args = parser.parse_args()
    result = build(check_only=args.check_only)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())