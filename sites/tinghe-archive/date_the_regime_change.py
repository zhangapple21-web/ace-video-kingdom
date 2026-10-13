#!/usr/bin/env python3
"""Date the regime change: when did the detective apparatus enter the gate?

Episodes carry no timestamps, but the verdict ledger does. Two questions:

  1. when was each episode first judged? That dates the writing.
  2. when did each issue type first appear? If CLUE_MISPLACED — a defect that
     only exists in fiction built around clues — starts appearing on a date, the
     gate did not merely fail to notice the drift, it started enforcing it.

The second is the one that matters. A gate that began rejecting on clue
placement is a gate that taught the writer to produce clues.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
CJK = re.compile(r"[一-鿿]")

PAYOFF = (
    "居然", "竟然", "没想到", "反转", "打脸", "当场", "逆转", "翻盘", "秒杀",
    "碾压", "震住", "傻眼", "倒吸", "全场", "底牌", "梭哈", "押注",
)
PROCEDURE = (
    "证据", "线索", "核查", "核实", "追溯", "比对", "笔录", "存根", "底册",
    "登记簿", "签收", "会签", "核验", "复核", "存档", "卷宗", "台账", "是谁",
)


def when(ts: str) -> dt.datetime | None:
    try:
        d = dt.datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    return d.replace(tzinfo=None) if d.tzinfo else d


def narration(ep: dict) -> str:
    return "\n".join(b.get("t", "") for b in ep.get("blocks") or []
                     if isinstance(b, dict) and b.get("k") in {"para", "line", "hook"})


def main() -> int:
    rows = json.loads((HERE / "audit_failures.json").read_text(encoding="utf-8"))

    print("=== 1. when each issue type was first raised ===\n")
    first: dict[str, dt.datetime] = {}
    counts: collections.Counter = collections.Counter()
    for r in rows:
        t = when(r.get("timestamp") or "")
        for issue in (r.get("audit") or {}).get("issues") or []:
            code = issue.get("type") or "?"
            counts[code] += 1
            if t and (code not in first or t < first[code]):
                first[code] = t
    for code, n in counts.most_common():
        seen = first.get(code)
        flag = "   <- only exists in clue-driven fiction" \
            if code in {"CLUE_MISPLACED", "TIMELINE_CONFLICT"} else ""
        print(f"  {code:<26} first seen {str(seen)[:16]:<18} {n:>4}x{flag}")

    print("\n=== 2. when each episode was first judged, and its vocabulary ===\n")
    judged: dict[tuple[str, str], dt.datetime] = {}
    for r in rows:
        t = when(r.get("timestamp") or "")
        key = (r.get("work"), r.get("episode"))
        if t and (key not in judged or t < judged[key]):
            judged[key] = t

    seq = []
    for wf in sorted(SOURCE.glob("*/work.json")):
        data = json.loads(wf.read_text(encoding="utf-8"))
        if data.get("id") not in {w for w, _ in judged}:
            continue
        for ep in sorted(data.get("episodes", []), key=lambda e: e.get("no") or 0):
            text = narration(ep)
            chars = len(CJK.findall(text)) or 1
            pay = sum(text.count(w) for w in PAYOFF)
            proc = sum(text.count(w) for w in PROCEDURE)
            seq.append((ep.get("no") or 0, data["id"], ep["id"],
                        judged.get((data["id"], ep["id"])), pay, proc, chars))

    print(f"  {'work':<12}{'ep':<6}{'first judged':<18}{'payoff':>8}{'procedure':>11}")
    print("  " + "-" * 55)
    for no, wid, eid, t, pay, proc, chars in sorted(seq, key=lambda r: (r[3] or dt.datetime.min)):
        print(f"  {wid:<12}{eid:<6}{str(t)[:16]:<18}{pay:>8}{proc:>11}")

    print("\n=== 3. the step, read directly ===\n")
    by_day: dict[str, list[int]] = collections.defaultdict(list)
    for no, wid, eid, t, pay, proc, chars in seq:
        if not t:
            continue
        by_day[t.date().isoformat()].append(pay * 1000 // chars)
    for day in sorted(by_day):
        vals = by_day[day]
        print(f"  {day}  episodes judged: {len(vals):<3} "
              f"payoff per 1k = {vals}  mean {sum(vals) / len(vals):.1f}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())