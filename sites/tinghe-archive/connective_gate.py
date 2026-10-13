#!/usr/bin/env python3
"""Gate the connective tic before deploy, using a threshold taken from the corpus.

Reading fanguan/ep11 exposed a repeated sentence hinge — 虽然…可… — six or more
times, always bridging the same two halves. Measuring across all 55 authored
episodes showed this is a regression, not a house style:

    ep01-ep09   0 occurrences   (the bulk of the catalogue)
    ep10        1-2
    ep11        2-11            (four works at once)

So the threshold is not invented: the healthy corpus sits at 0-2 and the
regressed batch starts at 6. Three sits in the empty gap between them.

This is a mechanical count rather than an LLM opinion on purpose. Twice this week
an auditor judgement was wrong in ways that mattered — a parser discarded a real
PASS, and the audit missed a contradiction inside one episode. A regex count is a
fact. It measures narration only: dialogue is allowed to hedge, a character
saying 虽然 is a person; it is the narrator reaching for the same hinge that gives
it away.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")

# Derived from the corpus, not chosen by taste: healthy episodes measure 0-2,
# the regressed batch measures 6-11.
THRESHOLD = 3
SKELETAL_MIN = 3   # the same hinge this many times, whatever the total


def measure_blocks(blocks: list[dict]) -> dict:
    import re
    text = "".join(b.get("t", "") for b in blocks
                   if isinstance(b, dict) and b.get("k") in {"para", "hook"})
    total = len(re.findall(r"[\u4e00-\u9fff]", text))
    detail: dict[str, int] = {}
    for label, pattern in (
        ("虽然…但是/但/可/却", r"虽然[^。！？]{0,60}?(?:但是|但|可|却)"),
        ("尽管…还是/仍", r"尽管[^。！？]{0,60}?(?:还是|仍然|仍旧)"),
        ("不是…而是", r"不是[^。！？]{0,60}?而是"),
        ("与其…不如", r"与其[^。！？]{0,60}?不如"),
        # A second default move, found by reading zhenqianjin/ep11: the model
        # reaches for 索性/干脆 to chain one action onto the next, and pairs them
        # inside a single clause ("索性把话闷着，干脆让纸开口"). Scored on the PAIR,
        # because either word alone is ordinary usage and the tic is the doubling.
        ("索性…干脆（同句）", r"索性[^。！？]{0,60}?干脆"),
    ):
        n = len(re.findall(pattern, text))
        if n:
            detail[label] = n
    hinge_total = sum(detail.values())
    dominant = max(detail, key=lambda k: detail[k]) if detail else None
    banned = [w for w in ("紧接着", "与此同时", "事实上", "显然", "毫无疑问",
                          "众所周知", "弥漫着", "心中五味杂陈",
                          "目光中闪过一丝", "嘴角勾起一抹") if w in text]
    return {
        "narration_chars": total,
        "hinge_total": hinge_total,
        "hinge_detail": detail,
        "dominant_hinge": dominant,
        "density_per_1k": round(hinge_total / total * 1000, 1) if total else 0.0,
        "banned_connectives": banned,
        "skeletal": bool(dominant and detail[dominant] >= SKELETAL_MIN),
        "fails": hinge_total > THRESHOLD or bool(dominant and detail[dominant] >= SKELETAL_MIN)
                 or bool(banned),
    }


def check_all() -> dict:
    out: dict[str, dict] = {}
    for wf in sorted(SOURCE.glob("*/work.json")):
        data = json.loads(wf.read_text(encoding="utf-8"))
        if data.get("id") not in DOMAIN:
            continue
        for ep in data.get("episodes", []):
            m = measure_blocks(ep.get("blocks", []))
            if m["narration_chars"] < 200:
                continue
            out[f"{data['id']}/{ep['id']}"] = m
    return out


def main() -> int:
    report = check_all()
    failing = {k: v for k, v in report.items() if v["fails"]}
    print(f"threshold: >{THRESHOLD} hinges, or the same hinge {SKELETAL_MIN}+ times, "
          f"or a banned connective")
    print(f"checked {len(report)} episode(s); {len(failing)} fail\n")
    for key, v in sorted(failing.items(), key=lambda kv: -kv[1]["hinge_total"]):
        print(f"  [FAIL] {key:<22} hinges={v['hinge_total']:<3} "
              f"{v['density_per_1k']:>5}/1k  dominant={v['dominant_hinge']}"
              f"  banned={','.join(v['banned_connectives']) or '-'}")
    if not failing:
        print("  (none)")

    clean = [v["hinge_total"] for v in report.values() if not v["fails"]]
    print(f"\nhealthy episodes: {len(clean)}, hinges per episode: "
          f"max {max(clean) if clean else 0}, mean "
          f"{sum(clean) / len(clean):.2f}" if clean else "")

    (HERE / "connective_gate.json").write_text(
        json.dumps({"threshold": THRESHOLD, "skeletal_min": SKELETAL_MIN,
                    "failing": failing}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
