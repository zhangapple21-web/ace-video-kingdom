#!/usr/bin/env python3
"""Measure connective-skeleton inertia across the authored episodes.

Reading fanguan/ep11 showed the same sentence frame over and over — 虽然…可… —
six or more times, always bridging the same two halves. That is the most
reliable machine tell in the prose, and it is not a matter of taste: it is a
count.

It is also not something an LLM judge can be trusted with. Twice this week an
auditor's judgement was wrong in ways that mattered — a parser discarded a real
PASS, and the audit missed a contradiction *inside* one episode. A regex count is
a fact. So: measure mechanically, report the distribution, and let the number
decide whether this is one bad apple or endemic.

Counts are taken from NARRATION blocks only. Dialogue is allowed to say 虽然; a
character hedging aloud is a person. It is the narrator reaching for the same
hinge that gives it away.
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")

# The hinge patterns that, repeated, read as machine-written. Ordered roughly by
# how strongly each one signals a default transition rather than a chosen one.
HINGES = [
    ("虽然…但是/可/却", r"虽然[^。！？]{0,60}?(?:但是|可|却)"),
    ("尽管…还是/仍", r"尽管[^。！？]{0,60}?(?:还是|仍然|仍旧)"),
    ("不是…而是", r"不是[^。！？]{0,60}?而是"),
    ("与其…不如", r"与其[^。！？]{0,60}?不如"),
    ("既…又", r"既[^。！？]{0,60}?又"),
]
# Classic bookish connectives the writer directive already forbids.
BANNED = ["紧接着", "与此同时", "事实上", "显然", "毫无疑问", "众所周知",
          "弥漫着", "心中五味杂陈", "目光中闪过一丝", "嘴角勾起一抹"]

NARRATION = {"para", "hook"}


def narration_text(blocks: list[dict]) -> str:
    return "".join(b.get("t", "") for b in blocks
                   if isinstance(b, dict) and b.get("k") in NARRATION)


def measure(blocks: list[dict]) -> dict:
    text = narration_text(blocks)
    total = len(re.findall(r"[\u4e00-\u9fff]", text))
    hits: dict[str, int] = {}
    for label, pattern in HINGES:
        found = len(re.findall(pattern, text))
        if found:
            hits[label] = found
    banned_hits = [w for w in BANNED if w in text]
    hinge_total = sum(hits.values())
    # Density per 1000 characters of narration. 1000 chars is roughly one
    # paragraph, so this reads as "how often per paragraph does the narrator
    # reach for the same hinge".
    density = round(hinge_total / total * 1000, 1) if total else 0.0
    dominant = max(hits, key=lambda k: hits[k]) if hits else None
    return {
        "narration_chars": total,
        "hinge_total": hinge_total,
        "hinge_detail": hits,
        "dominant": dominant,
        "density_per_1k": density,
        "banned_hits": banned_hits,
        "skeletal": bool(dominant and hits[dominant] >= 3),
    }


def main() -> int:
    rows = []
    for wf in sorted(SOURCE.glob("*/work.json")):
        data = json.loads(wf.read_text(encoding="utf-8"))
        if data.get("id") not in DOMAIN:
            continue
        for ep in data.get("episodes", []):
            m = measure(ep.get("blocks", []))
            m["work"] = data["id"]
            m["ep"] = ep["id"]
            rows.append(m)

    rows.sort(key=lambda r: -r["hinge_total"])

    print(f"{'episode':<22}{'hinges':>7}{'per 1k':>8}  dominant / banned")
    print("-" * 92)
    for r in rows:
        flag = "  <-- same hinge 3+" if r["skeletal"] else ""
        banned = ",".join(r["banned_hits"]) if r["banned_hits"] else ""
        dom = f"{r['dominant']}x{r['hinge_detail'].get(r['dominant'], 0)}" if r["dominant"] else "-"
        print(f"{r['work']}/{r['ep']:<14}{r['hinge_total']:>7}{r['density_per_1k']:>8}  "
              f"{dom:<22} {banned}{flag}")

    skeletal = [r for r in rows if r["skeletal"]]
    banned_any = [r for r in rows if r["banned_hits"]]
    nonempty = [r for r in rows if r["narration_chars"] > 200]

    print()
    print(f"episodes with narration      : {len(nonempty)}")
    print(f"same hinge 3+ times          : {len(skeletal)}")
    print(f"any banned connective        : {len(banned_any)}")
    if nonempty:
        avg = sum(r["hinge_total"] for r in nonempty) / len(nonempty)
        print(f"average hinges per episode   : {avg:.1f}")
        worst = rows[0]
        print(f"worst                       : {worst['work']}/{worst['ep']} "
              f"({worst['hinge_total']} hinges, {worst['density_per_1k']}/1k)")

    (HERE / "connective_report.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
