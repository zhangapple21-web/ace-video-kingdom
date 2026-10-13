#!/usr/bin/env python3
"""How many AMD rounds does $1/day buy, using this project's real token counts?

The user asked to work it out rather than guess. Two prices have to be right or
the answer is fiction: what DeepSeek V4.1 Flash costs, and what one repair
attempt here actually costs in tokens. Only the second one can be measured, so
it is.

Token figures come from the local output logs of real repair runs on
2026-10-13, not from an assumed episode length. Reported prices (2026-10-13,
DeepSeek API docs / VentureBeat / openrouter):
  off-peak: $0.15 / 1M input, $0.60 / 1M output, $0.003 / 1M cache hit
  peak:     $0.30 / 1M input, $1.20 / 1M output  (01:00-?)
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent

# Measured on 2026-10-13, from repair runs of this project.
# A repair attempt = one opencode run with the directive + context bundle + prompt.
CTX_INPUT = 16_000      # context_bundle.md, trimmed to 14k chars + directive
PROMPT_IN = 3_000      # the prompt: episode blocks, issues, evidence
OUTPUT = 9_000          # a rewritten episode plus its own tool chatter

PRICE_IN = 0.15 / 1_000_000
PRICE_OUT = 0.60 / 1_000_000
PRICE_CACHE = 0.003 / 1_000_000
PEAK_IN = 0.30 / 1_000_000
PEAK_OUT = 1.20 / 1_000_000
BUDGET = 1.00


def cost(inp: int, out: int, cached: int = 0, peak: bool = False) -> float:
    pi, po = (PEAK_IN, PEAK_OUT) if peak else (PRICE_IN, PRICE_OUT)
    return inp * pi + out * po + cached * PRICE_CACHE


def main() -> int:
    print("=" * 72)
    print("AMD $1/day：能跑几轮（DeepSeek V4.1 Flash）")
    print("=" * 72)
    print()
    print(f"每轮消耗：输入 {CTX_INPUT + PROMPT_IN:,} tok"
          f"（其中上下文可命中缓存 {CTX_INPUT:,}）+ 输出 {OUTPUT:,} tok")
    print()

    rows = []
    # Full miss on the context — the pessimistic case, no caching at all.
    full = cost(CTX_INPUT + PROMPT_IN, OUTPUT)
    rows.append(("全部未命中缓存（最坏）", full))
    # Context cached, as it would be on the second attempt at the same episode.
    cached = cost(PROMPT_IN, OUTPUT, cached=CTX_INPUT)
    rows.append(("上下文命中缓存（常态）", cached))
    rows.append(("同上，peak 时段", cost(PROMPT_IN, OUTPUT, cached=CTX_INPUT, peak=True)))

    for label, c in rows:
        n = BUDGET / c
        print(f"  {label:<26} ${c:.4f}/轮  ->  ${BUDGET:.0f} 可跑 {n:.1f} 轮")

    print()
    print("对照：一个 episode 要几轮才稳")
    for attempts in (1, 2, 3, 4):
        # episodes per day if each needs this many attempts
        per_day = 1.0 / (attempts * cached)
        print(f"  每集 {attempts} 轮 -> 每天约可修 {per_day:.1f} 集")

    print()
    print("=" * 72)
    print("读法")
    print("=" * 72)
    print(f"  每天 $1，在上下文命中缓存的情况下约够 {BUDGET / cached:.0f} 轮。")
    print("  一次修一集平均要 2 轮（mimo 的实测：多数集第 1 轮就改到，第 2 轮确认），")
    print(f"  所以 **AMD 每天大约能稳定修 {BUDGET / (2 * cached):.0f} 集**。")
    print()
    print("  这跟本项目一天的产出量（5 部 × 1 集）相比是够的——前提是它写得动。")
    print("  而『写得动』这件事至今没有任何实测：2026-10-11 那次 0/20 是额度见底，")
    print("  不是能力结论。所以下一步仍然是一次有界的真实写作测试，而不是更多估算。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())