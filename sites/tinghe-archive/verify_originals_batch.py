"""Ad-hoc verification for today's originals batch.

Checks the rendered public snapshot against the contract the reader relies on:
every episode file exists, is valid UTF-8 JSON, has the expected identity
fields, exactly one scene heading, and a closing hook. Also confirms the
existing catalogue survived untouched and that a rebuild is a no-op.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public" / "data" / "originals"
SOURCE = ROOT / "originals_source"
# Legacy works predate originals_source and exist only inside desk.json. The
# builder never rewrites their slots, so they are checked for presence and
# relative order only — never against a fixed episode count.
LEGACY = ["shuangdu", "tuixi", "shigong", "bieying", "dibao"]

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


desk = json.loads((PUBLIC / "desk.json").read_text(encoding="utf-8"))
by_id = {w["id"]: w for w in desk["works"]}
published_ids = [w["id"] for w in desk["works"]]

for legacy in LEGACY:
    check(legacy in by_id, f"legacy work lost: {legacy}")
legacy_positions = [published_ids.index(w) for w in LEGACY if w in by_id]
check(legacy_positions == sorted(legacy_positions),
      f"legacy works were reordered: {published_ids}")

# Every authored work must be published and match its source exactly. Deriving
# the expectation from originals_source keeps this correct as the daily batch
# appends episodes, instead of asserting a count that goes stale every day.
authored: dict[str, dict] = {}
for work_file in sorted(SOURCE.glob("*/work.json")):
    data = json.loads(work_file.read_text(encoding="utf-8"))
    authored[data.get("id", work_file.parent.name)] = data

check(set(authored) <= set(by_id),
      f"authored works missing from desk: {sorted(set(authored) - set(by_id))}")
check(set(by_id) == set(authored) | set(LEGACY),
      f"unexpected works in desk: {sorted(set(by_id) - set(authored) - set(LEGACY))}")

episodes = 0
for work_id, source_work in authored.items():
    work = by_id.get(work_id)
    check(work is not None, f"missing from desk: {work_id}")
    if not work:
        continue
    source_eps = source_work.get("episodes", [])
    check(len(work["episodes"]) == len(source_eps),
          f"{work_id}: desk has {len(work['episodes'])} episodes, source has {len(source_eps)}")
    check([e["id"] for e in work["episodes"]] == [e["id"] for e in source_eps],
          f"{work_id}: episode ids diverge from source")
    check([e["title"] for e in work["episodes"]] == [e["title"] for e in source_eps],
          f"{work_id}: episode titles diverge from source")
    cover = (work.get("assets") or {}).get("cover")
    if cover:
        check((ROOT / "public" / cover).is_file(), f"{work_id}: missing cover {cover}")
    for ep in work["episodes"]:
        episodes += 1
        path = ROOT / "public" / ep["file"]
        check(path.is_file(), f"missing episode file: {ep['file']}")
        if not path.is_file():
            continue
        raw = path.read_bytes()
        try:
            raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            failures.append(f"{ep['file']}: not valid UTF-8 ({exc})")
            continue
        payload = json.loads(raw.decode("utf-8"))
        check(payload.get("id") == ep["id"], f"{ep['file']}: id mismatch")
        check(payload.get("work_id") == work_id, f"{ep['file']}: work_id mismatch")
        check(payload.get("title") == f"第{int(ep['no']):02d}集 {ep['title']}",
              f"{ep['file']}: title mismatch")
        html = payload.get("html", "")
        check(html.count("<h3>") == 1, f"{ep['file']}: expected exactly one scene heading")
        check(html.count("<b>钩子</b>") == 1, f"{ep['file']}: expected exactly one hook block")
        check(html.rstrip().endswith("</p>"), f"{ep['file']}: hook must be the closing block")
        check("<script" not in html.lower(), f"{ep['file']}: script tag in reader HTML")

# Reverse direction: every episode file on disk must be listed in desk.json.
# The builder never deletes, so a removed episode would otherwise haunt public/
# forever and ship again on the next deploy (seen with a probe file, 2026-10-05).
for work_dir in sorted(PUBLIC.iterdir()):
    if not work_dir.is_dir():
        continue
    listed = {e["id"] for e in (by_id.get(work_dir.name) or {}).get("episodes", [])}
    if work_dir.name not in by_id:
        check(not list(work_dir.glob("ep*.json")),
              f"orphan work dir with episode files: {work_dir.name}")
        continue
    for path in sorted(work_dir.glob("ep*.json")):
        check(path.stem in listed, f"stale episode file not in desk: {work_dir.name}/{path.name}")

# Idempotence: a second build must report no file changes and leave desk.json alone.
before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted(PUBLIC.rglob("*.json"))}
result = subprocess.run(
    [sys.executable, str(ROOT / "build_originals.py"), "--check-only"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    timeout=300,
)
check(result.returncode == 0, f"check-only failed: {result.stderr[:300]}")
after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(PUBLIC.rglob("*.json"))}
check(before == after, "rebuild is not idempotent")

print(f"works checked: {len(authored)} authored + {len(LEGACY)} legacy")
print(f"episodes checked: {episodes}")
print(f"desk works: {len(desk['works'])}")
if failures:
    print("\nFAILURES:")
    for item in failures:
        print(f"  - {item}")
    raise SystemExit(1)
print("\nOK: all checks passed")