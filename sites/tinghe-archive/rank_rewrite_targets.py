#!/usr/bin/env python3
"""Rank episodes by how procedural they read, to choose what to rewrite first.

Choosing by eye is how the wrong twenty episodes get rewritten. So measure.

Three signals, all from the published text, none of them a verdict on quality:

  spine      the episode's own `beat`. A beat whose verb is "match artifact A to
             artifact B" makes the episode a forensic procedure whatever the prose
             does. That is the single strongest signal and it is authored, not
             inferred.
  body       procedure vocabulary per 1000 characters of narration.
  payoff     reversal vocabulary per 1000, for contrast.

The rewrite list is drawn from `spine` first, because it is the thing the writer
chose on purpose, then body. Episodes that win on payoff are excluded however
procedural their vocabulary looks — a good reversal scene happens to contain
paperwork.

Read-only.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
QUARANTINE = HERE / "quarantine.json"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")

CJK = re.compile(r"[一-鿿]")
PROCEDURE = (
    "证据", "线索", "核查", "核实", "追溯", "比对", "笔录", "存根", "底册",
    "登记簿", "签收", "会签", "核验", "复核", "存档", "卷宗", "台账", "是谁",
)
REVERSAL = (
    "当场", "当众", "开价", "认输", "认出", "翻脸", "抖出", "亮出", "甩出",
    "反手", "夺回", "抢回", "怼", "顶回去", "砸", "撕", "掀", "拍", "押",
    "赌", "赢", "输", "服", "跪", "破例", "自证", "愣住", "骇然", "变色",
)
FORENSIC_SPINE = (
    "对上", "比对", "一致", "吻合", "同一", "笔迹", "笔锋", "指纹", "页脚",
    "眉批", "回执", "存根", "底册", "编号", "封签", "原件", "抄件", "副本",
    "溯源", "指向", "属实", "查实", "核实", "核对", "证据", "线索", "封条",
)
TURN_SPINE = (
    "当场", "当众", "开价", "认输", "认出", "翻脸", "抖出", "亮出", "反手",
    "夺回", "抢回", "怼", "砸", "撕", "掀", "押", "赌", "赢", "输", "服",
    "破例", "自证", "认输", "点名",
)


def narration(ep: dict) -> str:
    return "\n".join(b.get("t", "") for b in ep.get("blocks") or []
                     if isinstance(b, dict) and b.get("k") in {"para", "line", "hook"})


def main() -> int:
    held = set()
    if QUARANTINE.is_file():
        q = json.loads(QUARANTINE.read_text(encoding="utf-8-sig"))
        held = {(h.get("work"), h.get("episode")) for h in (q.get("held") or [])}

    rows = []
    for wid in DOMAIN:
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        for ep in data.get("episodes", []):
            key = (wid, ep["id"])
            text = narration(ep)
            chars = len(CJK.findall(text)) or 1
            beat = str(ep.get("beat") or "")
            proc = sum(text.count(w) for w in PROCEDURE) * 1000 // chars
            pay = sum(text.count(w) for w in REVERSAL) * 1000 // chars
            spine_f = sum(beat.count(w) for w in FORENSIC_SPINE)
            spine_t = sum(beat.count(w) for w in TURN_SPINE)
            rows.append({
                "key": f"{wid}/{ep['id']}", "wid": wid, "no": ep.get("no") or 0,
                "held": key in held, "chars": chars, "proc": proc, "pay": pay,
                "spine_f": spine_f, "spine_t": spine_t, "beat": beat,
                "title": ep.get("title"),
            })

    print("=" * 96)
    print("按程序味排序（先看作者自己写的 beat，再看正文词频）")
    print("=" * 96)
    print(f"  {'episode':<20}{'no':>3}{'beat对物证':>10}{'beat翻盘':>9}"
          f"{'proc/1k':>9}{'pay/1k':>9}  title")
    print("  " + "-" * 92)
    ranked = sorted(rows, key=lambda r: (-(r["spine_f"] * 3 + r["proc"]),
                                         -r["spine_f"], r["no"]))
    for r in ranked:
        flag = " [已扣留]" if r["held"] else ""
        mark = " <<<" if (r["spine_f"] >= 2 and r["spine_f"] > r["spine_t"]) else ""
        print(f"  {r['key']:<20}{r['no']:>3}{r['spine_f']:>10}{r['spine_t']:>9}"
              f"{r['proc']:>9}{r['pay']:>9}  {r['title']}{flag}{mark}")

    print()
    cand = [r for r in ranked
            if not r["held"] and r["spine_f"] >= 2 and r["spine_f"] > r["spine_t"]]
    print(f"beat 是比对任务、且当前未被扣留：{len(cand)} 集")
    per_work: dict[str, list[dict]] = {}
    for r in cand:
        per_work.setdefault(r["wid"], []).append(r)

    print()
    print("=" * 96)
    print("建议的重写顺序（每部取程序味最重的一到两集）")
    print("=" * 96)
    chosen = []
    for wid in DOMAIN:
        picks = per_work.get(wid, [])[:2]
        for p in picks:
            chosen.append(p["key"])
        print(f"\n  {wid}")
        if picks:
            for p in picks:
                print(f"    {p['key']} 《{p['title']}》")
                print(f"        beat: {p['beat'][:100]}")
        else:
            near = [r for r in ranked if r["wid"] == wid][:2]
            print(f"    （beat 不算比对任务，改取词频最高的：）")
            for p in near:
                print(f"    {p['key']} 《{p['title']}》 proc={p['proc']}/1k  "
                      f"beat: {p['beat'][:80]}")

    print()
    print("=" * 96)
    print(f"重写名单（{len(chosen)} 集）: {', '.join(chosen)}")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())