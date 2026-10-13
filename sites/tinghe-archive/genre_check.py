#!/usr/bin/env python3
"""Watch for the drift that happened on 2026-10-11, using the external standard.

By 2026-10-11 the five works had read as detective fiction: CLUE_MISPLACED was 25%
of all audit rejections, TIMELINE_CONFLICT 15%, and across 52,871 characters the
procedure vocabulary outweighed the payoff vocabulary 5.47 to 1. Five works turned
over at ep05 and never turned back. Nothing in the pipeline noticed, because the
gate rewarded clue placement and nothing anywhere rewarded a reversal.

This measures the signals the external craft sources in
research/REFERENCE_MINES.md say matter, and compares them against the previous
run.

What this deliberately does NOT do: report a pass/fail verdict on quality.

  Its instruments are word lists written by the party arguing for the conclusion.
  On 2026-10-11 beat_shape.py — a classifier for exactly this — failed its own
  calibration, separating the known-good and known-bad groups only 45%/45%. So the
  numbers here are smoke, not fire. A gate built on them would have been worse than
  no gate.

What it does instead: compare each signal to the last snapshot and report the
DIRECTION. Weak instruments are still useful for noticing that something moved,
which is exactly the failure that went unnoticed here — nothing was watching.

It also reports how stale research/REFERENCE_MINES.md is, because the underlying
problem was not a missing rule but that nobody had checked the work against an
outside source at all.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")
REFERENCE = HERE / "research" / "REFERENCE_MINES.md"
STATUS = HERE / "genre_status.json"
SNAPSHOTS = HERE / ".genre_snapshots"

CJK = re.compile(r"[一-鿿]")

# Reversal / pressure — the external sources call these 爽点, 打脸, 压制, 情绪缺口.
REVERSAL = (
    "当场", "当众", "开价", "认输", "认出", "翻脸", "抖出", "亮出", "甩出",
    "反手", "夺回", "抢回", "怼", "顶回去", "砸", "撕", "掀", "拍", "押",
    "赌", "赢", "输", "服", "跪", "破例", "自证", "愣住", "骇然", "变色",
    "傻眼", "懵", "跪了", "抖了一下", "收回去", "不用了", "免了", "作废",
)
# Evidence work — the engine of a mystery.
COMPARISON = (
    "对上", "比对", "一致", "吻合", "同一", "笔迹", "笔锋", "指纹", "页脚",
    "眉批", "回执", "存根", "底册", "登记", "签收", "会签", "核验", "复核",
    "台账", "卷宗", "编号", "封签", "原件", "抄件", "副本", "溯源", "属实",
    "指向", "查实", "核实", "核对", "证据", "线索", "封条", "存疑",
)
PROCEDURE = (
    "证据", "线索", "核查", "核实", "追溯", "比对", "笔录", "存根", "底册",
    "登记簿", "签收", "会签", "核验", "复核", "存档", "卷宗", "台账", "是谁",
)

# Physical action. The user asked on 2026-10-11 for fight scenes and fantasy
# events, and until now nothing measured whether any existed. Measured on that
# date: 43 action words across all 60 episodes, only 4 of them in tingjijia.
# Same caveat as the lists above — self-written, direction only, not a gate.
ACTION = (
    "一拳", "一巴掌", "掐", "踹", "踢", "扑上去", "扭打", "抽出", "抄起",
    "砸", "撞开", "推倒", "揪住", "抡", "劈", "夺", "抢", "撕", "掀",
    "按住", "扳", "踉跄", "闪身", "砸过去", "掀翻", "血",
)

STALE_DAYS = 60


def narration(ep: dict) -> str:
    return "\n".join(b.get("t", "") for b in ep.get("blocks") or []
                     if isinstance(b, dict) and b.get("k") in {"para", "line", "hook"})


def measure() -> dict:
    chars = rev = comp = proc = act = 0
    beats_rev = beats_cmp = beats_plain = 0
    eps_without_action = 0
    places: set[str] = set()
    per_ep: list[dict] = []
    for wid in DOMAIN:
        wf = SOURCE / wid / "work.json"
        if not wf.is_file():
            continue
        data = json.loads(wf.read_text(encoding="utf-8"))
        for ep in sorted(data.get("episodes", []), key=lambda e: e.get("no") or 0):
            text = narration(ep)
            c = len(CJK.findall(text)) or 1
            chars += c
            r = sum(text.count(w) for w in REVERSAL)
            m = sum(text.count(w) for w in COMPARISON)
            p = sum(text.count(w) for w in PROCEDURE)
            a = sum(text.count(w) for w in ACTION)
            rev += r
            comp += m
            proc += p
            act += a
            if not a:
                eps_without_action += 1
            for b in ep.get("blocks") or []:
                if isinstance(b, dict) and b.get("k") == "scene":
                    place = str(b.get("place") or "").strip()
                    if place:
                        places.add(place)

            beat = str(ep.get("beat") or "")
            br = sum(beat.count(w) for w in REVERSAL)
            bm = sum(beat.count(w) for w in COMPARISON)
            if bm and not br:
                beats_cmp += 1
                shape = "comparison"
            elif br:
                beats_rev += 1
                shape = "reversal"
            else:
                beats_plain += 1
                shape = "plain"
            per_ep.append({
                "key": f"{wid}/{ep['id']}", "no": ep.get("no") or 0,
                "chars": c, "reversal_per_1k": round(r / c * 1000, 2),
                "comparison_per_1k": round(m / c * 1000, 2),
                "action_per_1k": round(a / c * 1000, 2),
                "beat_shape": shape,
            })

    n_eps = len(per_ep)
    beats_total = beats_rev + beats_cmp + beats_plain or 1
    return {
        "episodes": n_eps,
        "chars": chars,
        "reversal_per_1k": round(rev / chars * 1000, 2) if chars else 0.0,
        "comparison_per_1k": round(comp / chars * 1000, 2) if chars else 0.0,
        "procedure_per_1k": round(proc / chars * 1000, 2) if chars else 0.0,
        "action_per_1k": round(act / chars * 1000, 2) if chars else 0.0,
        "episodes_without_action": eps_without_action,
        "distinct_places": len(places),
        "beat_reversal_share": round(beats_rev / beats_total, 3),
        "beat_comparison_share": round(beats_cmp / beats_total, 3),
        "beats": {"reversal": beats_rev, "comparison": beats_cmp,
                  "plain": beats_plain},
        "per_episode": per_ep,
    }


def reference_age_days() -> int | None:
    if not REFERENCE.is_file():
        return None
    dates = re.findall(r"(20\d\d)-(\d\d)-(\d\d)", REFERENCE.read_text(encoding="utf-8"))
    if not dates:
        return None
    newest = max(dt.date(int(y), int(m), int(d)) for y, m, d in dates)
    return (dt.date.today() - newest).days


def compare(now: dict, before: dict | None) -> list[str]:
    if not before:
        return ["first run — nothing to compare against yet"]
    notes = []
    for key, label, worse_when in (
        ("reversal_per_1k", "reversal words per 1k", "down"),
        ("beat_reversal_share", "share of beats shaped like a reversal", "down"),
        ("action_per_1k", "action words per 1k", "down"),
    ):
        a, b = before.get(key), now.get(key)
        if a is None or b is None:
            continue
        delta = b - a
        rel = delta / a * 100 if a else 0.0
        arrow = "DOWN" if delta < 0 else ("up" if delta > 0 else "flat")
        note = f"{label}: {a} -> {b} ({arrow} {rel:+.0f}%)"
        if worse_when == "down" and delta < 0 and abs(rel) >= 15:
            note += "   <- worse than last snapshot"
        notes.append(note)
    for key, label in (
        ("comparison_per_1k", "comparison words per 1k"),
        ("beat_comparison_share", "share of beats shaped like evidence work"),
    ):
        a, b = before.get(key), now.get(key)
        if a is None or b is None:
            continue
        rel = (b - a) / a * 100 if a else 0.0
        note = f"{label}: {a} -> {b} ({rel:+.0f}%)"
        if rel >= 15:
            note += "   <- moving back toward investigation"
        notes.append(note)
    for key, label, worse_when in (
        ("episodes_without_action", "episodes with no action words", "up"),
        ("distinct_places", "distinct scene places", "down"),
    ):
        a, b = before.get(key), now.get(key)
        if a is None or b is None:
            continue
        delta = b - a
        rel = delta / a * 100 if a else 0.0
        arrow = "UP" if delta > 0 else ("down" if delta < 0 else "flat")
        note = f"{label}: {a} -> {b} ({arrow} {rel:+.0f}%)"
        if worse_when == "up" and delta > 0 and abs(rel) >= 15:
            note += "   <- worse than last snapshot"
        notes.append(note)
    if now.get("episodes", 0) > before.get("episodes", 0):
        notes.append(f"new episodes since last snapshot: "
                     f"{now['episodes'] - before['episodes']}")
    return notes


def main() -> int:
    now = measure()
    SNAPSHOTS.mkdir(exist_ok=True)
    history = sorted(SNAPSHOTS.glob("*.json"))
    before = json.loads(history[-1].read_text(encoding="utf-8")) if history else None

    age = reference_age_days()
    print("=" * 70)
    print("genre drift check — external standard, trend only, no verdict")
    print("=" * 70)
    print(f"  episodes measured        : {now['episodes']}")
    print(f"  characters               : {now['chars']}")
    print(f"  reversal words /1k       : {now['reversal_per_1k']}")
    print(f"  comparison words /1k     : {now['comparison_per_1k']}")
    print(f"  procedure words /1k      : {now['procedure_per_1k']}")
    print(f"  action words /1k         : {now['action_per_1k']}   "
          f"(episodes with none: {now['episodes_without_action']}/{now['episodes']})")
    print(f"  distinct scene places    : {now['distinct_places']}")
    print(f"  beats shaped as reversal : {now['beat_reversal_share']:.0%} "
          f"({now['beats']['reversal']})")
    print(f"  beats shaped as evidence : {now['beat_comparison_share']:.0%} "
          f"({now['beats']['comparison']})")
    print(f"  beats plain              : {now['beats']['plain']}")
    print()
    print("  --- versus the previous snapshot ---")
    for n in compare(now, before):
        print("   " + n)
    if before is None:
        print("   (nothing to compare against; run it again next week)")
    print()
    print("  --- external reference freshness ---")
    if age is None:
        print("   research/REFERENCE_MINES.md missing or undated")
    else:
        print(f"   newest external source: {age} days old"
              + ("   <- STALE, go and read something new" if age > STALE_DAYS else ""))
    print()
    print("  --- the leading indicator: is the pressure axis filled in? ---")
    # An empty facts.json `pressure` section is the structural condition that made
    # the drift possible: nothing in the fact table said "this must be harder than
    # last time", and open_hooks kept pulling toward investigation. It went
    # unnoticed for eight episodes. This is the thing to watch before the word
    # counts move, not after.
    empty = []
    for wid in DOMAIN:
        f = SOURCE / wid / "facts.json"
        if not f.is_file():
            empty.append(f"{wid} (no facts.json)")
            continue
        try:
            facts = json.loads(f.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            empty.append(f"{wid} (unreadable: {exc})")
            continue
        pressure = facts.get("pressure")
        if not pressure:
            empty.append(wid)
    if empty:
        print(f"   {len(empty)} of {len(DOMAIN)} works have an EMPTY pressure axis: "
              f"{', '.join(empty)}")
        print("   While it is empty the writer has nothing pushing toward escalation,")
        print("   so episodes drift back toward investigation. This is the cause, not")
        print("   the symptom — fill it in before tuning any measurement.")
    else:
        print(f"   all {len(DOMAIN)} works carry a pressure axis")
    print()
    print("  The instruments are word lists. They were measured to be weak in")
    print("  absolute terms on 2026-10-11 and are used only because a direction")
    print("  change is easier to notice than a level — which was the actual failure.")

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    snapshot = {k: v for k, v in now.items() if k != "per_episode"}
    (SNAPSHOTS / f"{stamp}.json").write_text(
        json.dumps(now, ensure_ascii=False, indent=2), encoding="utf-8")
    for old in sorted(SNAPSHOTS.glob("*.json"))[:-12]:
        old.unlink(missing_ok=True)

    STATUS.write_text(json.dumps({
        "checked_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "measures": snapshot,
        "pressure_axis_empty": empty,
        "reference_age_days": age,
        "reference_stale": bool(age and age > STALE_DAYS),
        "has_baseline": before is not None,
        "verdict": "REPORT_ONLY",
        "note": ("signals only; instruments are word lists and are not fit to gate "
                 "publication. See the module docstring."),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())