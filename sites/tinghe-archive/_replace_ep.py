"""Replace one work's ep07 with a corrected draft, in place and additively.

Used when the narrative audit rejects an episode: the whole episode is swapped
rather than patched, so the audited text and the published text stay identical.
Only the ep07 slot is touched; ep01-ep06 and every metadata field are verified
unchanged afterwards.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tools.atomic_io import atomic_write_text

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
SRC = HERE / "originals_source"
ALLOWED = {"scene", "cast", "para", "line", "hook", "note"}

wid = sys.argv[1]
ep_id = sys.argv[2]
fix_file = Path(sys.argv[3])

draft = json.loads(fix_file.read_text(encoding="utf-8"))
if wid not in draft:
    raise SystemExit(f"{wid} not in {fix_file.name}")
draft = draft[wid]

scene = draft["scene"]
cast = {"k": "cast", "present": list(draft["present"])}
if draft.get("absent"):
    cast["absent"] = list(draft["absent"])
blocks = [
    {"k": "scene", "place": scene["place"], "time": scene["time"], "light": scene["light"]},
    cast,
    *draft["blocks"],
]

kinds = [b["k"] for b in blocks]
problems = []
if kinds.count("scene") != 1:
    problems.append(f"scene={kinds.count('scene')}")
if kinds.count("hook") != 1 or kinds[-1] != "hook":
    problems.append(f"hook={kinds.count('hook')} last={kinds[-1]}")
if kinds[1] != "cast":
    problems.append(f"second={kinds[1]}")
for b in blocks:
    if b["k"] not in ALLOWED:
        problems.append(f"kind {b['k']}")
if problems:
    raise SystemExit("refusing to write: " + "; ".join(problems))

path = SRC / wid / "work.json"
data = json.loads(path.read_text(encoding="utf-8"))
episodes = data["episodes"]
index = next((i for i, e in enumerate(episodes) if e["id"] == ep_id), None)
if index is None:
    raise SystemExit(f"{wid}/{ep_id} not found")

before_others = json.dumps([e for i, e in enumerate(episodes) if i != index],
                           ensure_ascii=False, sort_keys=True)
before_meta = json.dumps({k: v for k, v in data.items() if k != "episodes"},
                         ensure_ascii=False, sort_keys=True)

episodes[index] = {
    "id": ep_id,
    "no": episodes[index]["no"],
    "title": draft["title"],
    "beat": draft["beat"],
    "blocks": blocks,
}

after_others = json.dumps([e for i, e in enumerate(episodes) if i != index],
                          ensure_ascii=False, sort_keys=True)
after_meta = json.dumps({k: v for k, v in data.items() if k != "episodes"},
                        ensure_ascii=False, sort_keys=True)
if before_others != after_others:
    raise SystemExit("ABORT: a sibling episode changed")
if before_meta != after_meta:
    raise SystemExit("ABORT: a metadata field changed")

atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{wid}/{ep_id} replaced: 「{draft['title']}」 {len(blocks)} blocks")

# Drop this episode's stale audit records so a re-audit starts clean.
audit_path = HERE / "audit_failures.json"
if audit_path.is_file():
    rows = json.loads(audit_path.read_text(encoding="utf-8"))
    kept = [r for r in rows
            if not (r.get("work") == wid and r.get("episode") == ep_id)]
    atomic_write_text(audit_path, json.dumps(kept, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    print(f"audit_failures.json: removed {len(rows) - len(kept)} stale record(s)")