#!/usr/bin/env python3
"""Print the beat and the opening scene of each rewritten episode.

The numbers moved a long way, and reading one episode confirmed the move was
real. This checks the remaining ones without dumping four full texts, and
specifically verifies that each `beat` was replaced — a rewrite that leaves the
old spine behind pulls the following episode back toward paperwork, which is how
the first rewrite was nearly wasted.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
PAIRS = [("fanguan", "ep08"), ("fanguan", "ep09"),
         ("zhenqianjin", "ep08"), ("zhenqianjin", "ep09")]

OLD_BEATS = {
    ("fanguan", "ep08"): "总务处门口开第二家灶 · 存根眉批八个字牵出供应署旧楼四楼",
    ("fanguan", "ep09"): "供应署旧楼四楼文书房 · 眉批与半印的来源在等人来拿",
    ("zhenqianjin", "ep08"): "矿务署把转出册案本送到老宅 · 井下二十上来十九 · 封条与医院手环同号",
    ("zhenqianjin", "ep09"): "三日期满产科封签送达矿务署 · 青梧在档案窗口当场拆开，手环编号对上空栏",
}


def main() -> int:
    print("=" * 88)
    print("四集重写结果 —— 逐集核对 beat 是否换掉，并看开场")
    print("=" * 88)
    stale = 0
    for wid, eid in PAIRS:
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        ep = next(e for e in data["episodes"] if e["id"] == eid)
        beat = str(ep.get("beat") or "")
        old = OLD_BEATS.get((wid, eid))
        changed = bool(old) and beat != old
        if not changed:
            stale += 1
        flag = "beat 已换" if changed else "!! BEAT 未换"
        print(f"\n{wid}/{eid}  《{ep.get('title')}》   {flag}")
        print(f"  beat: {beat}")
        if old and changed:
            print(f"  旧  : {old}")
        paras = [b for b in ep.get("blocks") or []
                 if isinstance(b, dict) and b.get("k") == "para"]
        if paras:
            print(f"  开场: {paras[0].get('t','')[:110]}")
        hook = next((b.get("t", "") for b in ep.get("blocks") or []
                     if isinstance(b, dict) and b.get("k") == "hook"), "")
        if hook:
            print(f"  钩子: {' '.join(hook.split())[:110]}")

    print()
    print("=" * 88)
    print(f"beat 未换的：{stale}/4 —— 非零就说明有一集的重写是半应用的")
    return 0 if stale == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())