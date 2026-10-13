#!/usr/bin/env python3
"""Give the fact table the axis that 爽文 runs on and this catalogue did not have.

Measured on 2026-10-11: facts.json contains characters, numbers, timeline, props,
open_hooks, never and pending, and the strings 升级, 阶梯, 对手, 反派, 地图 and 阶段
appear zero times across all five works. Every field in the table pulls one way —
"do not break this" and "finish what is open" — and none pushes the other way:
"this must be harder than last time".

open_hooks is the strongest pull toward investigation. Every entry is a question
waiting to be answered, so an episode that honours them is an episode that looks
into something. That is how five works ran on the suspense template from ep05 on.

This adds a `pressure` section: where the opposition currently stands, what is at
stake, what she won last arc and — the load-bearing field — what that win cost
her, so the next arc presses harder instead of restarting at the same difficulty.
It renders in the bundle ABOVE open_hooks, so the escalation state is read before
the list of things to investigate.

It is deliberately additive. A missing or malformed section warns and skips; the
2026-10-07 crash came from hard-indexing a hand-edited record, so nothing here is
indexed without a check.

Idempotent.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
BUNDLE = HERE / "build_context_bundle.py"
failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


# ---------------------------------------------------------------- bundle side

BUNDLE_ANCHOR = 'lines.append("## 事实表（写新集与审核的硬约束，优先级高于临场发挥）")\n            lines.append("")'

PRESSURE_BLOCK = '''lines.append("## 事实表（写新集与审核的硬约束，优先级高于临场发挥）")
            lines.append("")

            # --- 压力轴（2026-10-11 新增）--------------------------------------------
            # Every other fact field says "do not break this" or "finish that".
            # None says "this must be harder than last time", so nothing stopped the
            # catalogue sliding from 爽文 into investigation once the premise grew a
            # conspiracy to uncover. Measured 2026-10-11: 升级/阶梯/对手/反派/地图/阶段
            # appear zero times in all five works' facts.json.
            #
            # Rendered ABOVE open_hooks on purpose. open_hooks is a list of questions
            # waiting to be answered, so an episode that honours it looks into
            # something; read after the pressure axis, the same hook becomes leverage
            # instead of an investigation.
            pressure = facts.get("pressure") or []
            if isinstance(pressure, dict):
                pressure = [pressure]
            if not pressure:
                lines.append("### ⚠ 压力轴未填写（pressure 段为空或缺失）")
                lines.append("")
                lines.append("本作品缺少「对手/赌注/上一轮赢下什么/代价是什么」的记录。")
                lines.append("按 DAILY_DIRECTIVE 8b：这一轴为空的期间，写新集容易退回"
                             "「继续查上一件事」。若要补，写成一段记录：")
                lines.append("")
                lines.append("```json")
                lines.append('"pressure": [{"arc": 2, "opponent": "谁在压她", '
                             '"stake": "拿什么做赌注", "deadline": "期限或时限", '
                             '"last_won": "上一轮她赢下了什么", '
                             '"cost": "这个赢的代价，下一轮要还", '
                             '"next_must_differ": "接下来 3 集里必须不同的那一项"}]')
                lines.append("```")
                lines.append("")
            else:
                lines.append("### 压力轴（爽文的引擎：压 → 当场翻回来 → 代价留到下一轮）")
                lines.append("")
                for rec in pressure:
                    norm = _flat(rec)
                    if not isinstance(norm, dict):
                        continue
                    bits = []
                    for key, label in (
                        ("arc", "轮次"), ("opponent", "对手"), ("stake", "赌注"),
                        ("deadline", "期限"), ("last_won", "上一轮赢下"),
                        ("cost", "代价（下一轮要还）"),
                        ("next_must_differ", "接下来必须不同的"),
                    ):
                        val = str(norm.get(key) or "").strip()
                        if val:
                            bits.append(f"{label}：{val}")
                    if bits:
                        lines.append("- " + "；".join(bits) + "。")
                lines.append("")'''

OLD_NEVER = 'lines.append("## 事实表（写新集与审核的硬约束，优先级高于临场发挥）")\n            lines.append("")'


def main() -> int:
    text = BUNDLE.read_text(encoding="utf-8")
    if "压力轴未填写" in text:
        print("already patched")
        return 0

    check(BUNDLE_ANCHOR in text, "found the fact-table heading in build_context_bundle.py")
    if BUNDLE_ANCHOR not in text:
        return 1
    BUNDLE.write_text(text.replace(BUNDLE_ANCHOR, PRESSURE_BLOCK, 1), encoding="utf-8")
    print("  patched build_context_bundle.py")

    import py_compile
    try:
        py_compile.compile(str(BUNDLE), doraise=True)
    except py_compile.PyCompileError as exc:
        print(f"[FAIL] bundle does not compile: {exc}")
        return 1
    print("[PASS] build_context_bundle.py compiles")

    print("\npatched")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())