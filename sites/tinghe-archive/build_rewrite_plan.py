#!/usr/bin/env python3
"""Build the rewrite list for ep08-ep12, and record why each episode is in it.

The beat-based ranking found only four episodes whose spine is literally an
artifact comparison, which is far fewer than the drift actually is. Reading
zhenqianjin/ep10 showed the real shape: a whole scene given over to matching
copper filings against a scratch, with the beat describing only the paperwork part.
So the drift lives in the body, not in the authored spine, and a list built from
beats alone undercounts it.

The user chose to rewrite by arc rather than by signal: ep08-ep12 across the five
works. This builds that list, minus anything already held, and records the
measured reason for each so the choice is auditable rather than assumed.

Ordering: by work, then by episode number, so a partial run leaves a coherent
prefix rather than a scatter.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
QUARANTINE = HERE / "quarantine.json"
PLAN = HERE / "rewrite_plan.json"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")

FIRST, LAST = 8, 12
CJK = re.compile(r"[一-鿿]")
PROCEDURE = (
    "证据", "线索", "核查", "核实", "追溯", "比对", "笔录", "存根", "底册",
    "登记簿", "签收", "会签", "核验", "复核", "存档", "卷宗", "台账", "是谁",
    "归档", "移交", "注销", "备案", "台账", "签章", "用印", "编号", "批复",
)
REVERSAL = (
    "当场", "当众", "开价", "认输", "认出", "翻脸", "抖出", "亮出", "甩出",
    "反手", "夺回", "抢回", "怼", "顶回去", "砸", "撕", "掀", "拍", "押",
    "赌", "赢", "输", "服", "跪", "破例", "自证", "愣住", "骇然", "变色",
    "傻眼", "懵", "作废", "退回", "免了", "不用了", "滚", "跪了",
)


def narration(ep: dict) -> str:
    return "\n".join(b.get("t", "") for b in ep.get("blocks") or []
                     if isinstance(b, dict) and b.get("k") in {"para", "line", "hook"})


def main() -> int:
    held = set()
    if QUARANTINE.is_file():
        q = json.loads(QUARANTINE.read_text(encoding="utf-8-sig"))
        held = {(h.get("work"), h.get("episode")) for h in (q.get("held") or [])}

    entries = []
    for wid in DOMAIN:
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        for ep in sorted(data.get("episodes", []), key=lambda e: e.get("no") or 0):
            no = ep.get("no") or 0
            if not (FIRST <= no <= LAST):
                continue
            key = (wid, ep["id"])
            text = narration(ep)
            chars = len(CJK.findall(text)) or 1
            proc = sum(text.count(w) for w in PROCEDURE) * 1000 // chars
            pay = sum(text.count(w) for w in REVERSAL) * 1000 // chars
            entries.append({
                "work": wid, "episode": ep["id"], "no": no,
                "title": ep.get("title"), "beat": ep.get("beat"),
                "chars": chars, "procedure_per_1k": proc, "reversal_per_1k": pay,
                "already_held": key in held,
                "reason": (f"ep{FIRST}-ep{LAST} 区间内；正文程序词 {proc}/千字、"
                           f"爽感词 {pay}/千字"),
            })

    todo = [e for e in entries if not e["already_held"]]
    plan = {
        "schema": "tinghe.rewrite_plan.v1",
        "created_at": "2026-10-11",
        "arc": [FIRST, LAST],
        "why": ("用户选定按段落重写。beat 信号只抓出 4 集，但真正的漂移在正文层——"
                "读 zhenqianjin/ep10 看到整场铜屑比色，beat 只写了其中文书的��部分。"
                "ep08-ep12 是这五部作品集体转向调查的区间。"),
        "prerequisite": ("REPAIR_DIRECTIVE.md 已补 1b 节：重写型修复必须换脊梁并读压力轴，"
                         "否则会把 40 集重写成同样的程序味。"),
        "total_in_arc": len(entries),
        "already_held": [f"{e['work']}/{e['episode']}" for e in entries
                         if e["already_held"]],
        "to_rewrite": [f"{e['work']}/{e['episode']}" for e in todo],
        "entries": entries,
    }
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")

    print("=" * 78)
    print(f"重写名单：ep{FIRST}-ep{LAST}，5 部作品")
    print("=" * 78)
    print(f"  区间内总集数     : {len(entries)}")
    print(f"  已扣留（跳过）   : {len(plan['already_held'])}  "
          f"{', '.join(plan['already_held']) or '无'}")
    print(f"  待重写           : {len(todo)}")
    print()
    print(f"  {'work':<13}{'ep':<6}{'proc/1k':>9}{'pay/1k':>8}   title")
    print("  " + "-" * 62)
    for e in entries:
        mark = " [已扣留]" if e["already_held"] else ""
        print(f"  {e['work']:<13}{e['episode']:<6}{e['procedure_per_1k']:>9}"
              f"{e['reversal_per_1k']:>8}   {e['title']}{mark}")

    tot_p = sum(e["procedure_per_1k"] for e in todo) / max(1, len(todo))
    tot_r = sum(e["reversal_per_1k"] for e in todo) / max(1, len(todo))
    print()
    print(f"  待重写区间均值：程序词 {tot_p:.1f}/千字 · 爽感词 {tot_r:.1f}/千字"
          f"   比例 {tot_p / tot_r:.1f} : 1" if tot_r else "")
    print(f"\n  名单写入 {PLAN.name}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())