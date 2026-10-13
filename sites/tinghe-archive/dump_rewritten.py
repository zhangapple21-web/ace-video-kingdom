#!/usr/bin/env python3
"""Confirm the rewrites left no broken file behind, and dump two of them to read.

A rewrite that fails is supposed to restore the backup. That is a promise made
by the code, not an observed fact: the model for tingjijia/ep06 and the model
for zhenqianjin/ep06 both took the discard path tonight (one on a collateral
edit to the wrong episode, one on a timeout), so the restore ran three times
in a row on live files. A truncate-then-crash or a half-written read would show
up here as unreadable JSON.

Dumps the two rewritten episodes to _dump_<work>_<ep>.txt for a human to read.
The numbers the rewriter printed are not the verdict; reading the text is.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
WORKS = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")
DUMP = (("tingjijia", "ep06"), ("tuiqun", "ep04"))


def main() -> int:
    print("=" * 74)
    print("1. 每个 work.json 都还能解析吗（重写失败会 restore，这是验证不是假设）")
    print("=" * 74)
    broken = 0
    for wid in WORKS:
        p = SOURCE / wid / "work.json"
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  {wid:<12} BROKEN: {exc}")
            broken += 1
            continue
        eps = sorted(data.get("episodes") or [], key=lambda e: e.get("no") or 0)
        if not eps:
            print(f"  {wid:<12} BROKEN: no episodes")
            broken += 1
            continue
        print(f"  {wid:<12} OK  {len(eps)} eps  "
              f"{eps[0]['id']}..{eps[-1]['id']}")

    print()
    print("=" * 74)
    print("2. 把重写成功的两集导出来给人读")
    print("=" * 74)
    for wid, eid in DUMP:
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        ep = next((e for e in data["episodes"] if e.get("id") == eid), None)
        if ep is None:
            print(f"  {wid}/{eid} MISSING")
            broken += 1
            continue
        lines = [f"WORK: {wid}  {eid}", f"BEAT: {ep.get('beat')}", ""]
        for b in ep.get("blocks") or []:
            k = b.get("k")
            if k == "scene":
                lines.append(f"[场景] {b.get('place')} | {b.get('time')}")
            elif k == "cast":
                lines.append(f"[出场] {b.get('present')}")
            elif k in ("para", "hook"):
                lines.append(str(b.get("t", "")))
            elif k == "line":
                lines.append(f"{b.get('who')}：{b.get('t', '')}")
        out = HERE / f"_dump_{wid}_{eid}.txt"
        out.write_text("\n".join(lines), encoding="utf-8")
        chars = sum(len(l) for l in lines)
        print(f"  {wid}/{eid} -> {out.name}  ({chars} chars)")

    print()
    print("=" * 74)
    if broken:
        print(f"FAILED: {broken} file(s) broken after the rewrites")
        return 1
    print("PASS: nothing broken; read the two dumps before trusting them")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
