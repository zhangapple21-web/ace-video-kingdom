#!/usr/bin/env python3
"""Prove an audit's prior context never contains a later episode.

Added 2026-10-07 after a quarter of the catalogue failed and seven episodes were
quarantined on verdicts that compared an episode against its own sequel. The
bundle is per-work and keeps the most recent chapters in full, so the defect was
invisible: the audit log said nothing wrong, it just fed the model the future as
backstory.

The requirement here is exact and negative — no episode numbered at or after the
audited one may appear in the audit context — so each case asserts absence, not
approximate ordering.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("b", HERE / "build_context_bundle.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

BUNDLE = """# 作品 叙事上下文包
生成时间戳：2026-10-07T00:00:00+08:00
已发布章节数：8
本包提供最近 3 集完整正文（ep06–ep08），其余只提供标题与简介。

## 剧情状态摘要表格

| 集 | 标题 | 出场 | 字数 | 阶段提示 |
|----|------|------|------|----------|
| ep01 | 一 | 甲 | 400 | 铺垫 |
| ep02 | 二 | 乙 | 420 | 铺垫 |
| ep03 | 三 | 丙 | 440 | 升级 |
| ep04 | 四 | 丁 | 460 | 升级 |
| ep05 | 五 | 戊 | 480 | 转折 |
| ep06 | 六 | 己 | 500 | 转折 |
| ep07 | 七 | 庚 | 520 | 高潮 |
| ep08 | 八 | 辛 | 540 | 收束 |

## 最近 3 集完整正文

### ep06 第06集 六

第六集正文。

### ep07 第07集 七

第七集正文。

### ep08 第08集 八

第八集正文。

## 更早的集（只提供标题与简介，勿按正文对待）

### ep01 第01集 一

第一集简介。

### ep02 第02集 二

第二集简介。

### ep03 第03集 三

第三集简介。

### ep04 第04集 四

第四集简介。

### ep05 第05集 五

第五集简介。
"""

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def remaining_eps(text: str) -> list[int]:
    nums = []
    for tok in re.findall(r"(?:^###\s*|\|\s*)(ep\d+)", text, re.MULTILINE):
        nums.append(int("".join(c for c in tok if c.isdigit())))
    return sorted(set(nums))


def main() -> int:
    # The headline case: auditing ep05 must not see ep06..ep08 as backstory.
    text, dropped = mod.prior_context(BUNDLE, "ep05", 5)
    left = remaining_eps(text)
    print(f"auditing ep05 -> kept {left}, dropped {dropped}\n")
    check(left == [1, 2, 3, 4], f"only episodes before 05 remain (kept {left})")
    check(all(n < 5 for n in left), "no episode numbered >= 05 survives")
    check("第六集正文" not in text, "no full text from a later episode")
    check("第八集正文" not in text, "no full text from the newest episode")
    check("第五集简介" not in text, "the audited episode's own summary is gone")
    check("第 5 集" in text and "之前" in text,
          "context is labelled as backstory preceding the audited episode")

    # Every earlier episode works the same way.
    for no in range(1, 9):
        t, _ = mod.prior_context(BUNDLE, f"ep{no:02d}", no)
        kept = remaining_eps(t)
        bad = [n for n in kept if n >= no]
        check(not bad, f"ep{no:02d}: nothing at or after it remains (kept {kept})")

    # The latest episode: nothing to drop, and its own text must still go.
    t8, d8 = mod.prior_context(BUNDLE, "ep08", 8)
    check(d8 == [8], f"auditing ep08 drops itself and nothing else (dropped {d8})")
    check(remaining_eps(t8) == [1, 2, 3, 4, 5, 6, 7], "ep08 keeps all earlier episodes")

    # Episode number inferred from the id when the caller does not pass one.
    t, _ = mod.prior_context(BUNDLE, "ep03")
    check(all(n < 3 for n in remaining_eps(t)), "id alone is enough to cut correctly")

    # Original single-episode stripping still behaves as before.
    single = mod.strip_episode(BUNDLE, "ep02")
    check("### ep02" not in single, "strip_episode still removes exactly its episode")
    check("### ep01" in single and "### ep03" in single,
          "strip_episode leaves its neighbours alone")

    print()
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: an audit can never see a later episode as prior context")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
