#!/usr/bin/env python3
"""The genre gate must require agreement, and must not fire when nothing ran.

The design exists because of a measurement, not an opinion:

  - AUDIT_PROMPT once said genre_drift must not fail anything, because the
    auditor's verdict has been observed flipping. So genre_drift appeared as an
    issue zero times across 342 audit records while the procedural-to-payoff
    ratio went 5.5 → 6.1. The rule was defensible; zero enforcement was not.
  - Keyword gates cannot take over. One scored 80/80 on 2026-10-14 — it read
    fanguan/ep04 as having no turnaround when that episode opens the seal in
    front of everyone and walks out with the shop. Another left 60% of beats
    unclassified. The same instruments separated known-good from known-bad 45%
    to 45% on 2026-10-11.

So the block comes from the auditor's reading, made safe by repetition on
identical bytes. These checks pin the properties that make it safe, and they
run against synthetic ledgers — no model is called.
"""
from __future__ import annotations

import json
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def load_verdict():
    import importlib.util
    spec = importlib.util.spec_from_file_location("verdict_mod", HERE / "verdict.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def with_ledger(rows, tmp: pathlib.Path):
    """Point verdict.LEDGER at a synthetic ledger and return the module."""
    mod = load_verdict()
    mod.LEDGER = tmp
    tmp.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return mod


def row(work, ep, sha, issues, status="FAIL", ts="2026-10-14T10:00:00"):
    return {"work": work, "episode": ep, "timestamp": ts, "content_sha": sha,
            "audit": {"status": status, "issues": issues}}


DRIFT = [{"type": "GENRE_DRIFT", "severity": "MAJOR",
          "description": "本集靠查证推进，没有当场翻盘",
          "evidence_before": "", "evidence_after": ""}]
OTHER = [{"type": "CLUE_MISPLACED", "severity": "MAJOR",
          "description": "回执位置矛盾", "evidence_before": "", "evidence_after": ""}]

tmp = HERE / "_synthetic_ledger.json"
try:
    # 1. one drift is not enough
    m = with_ledger([row("w", "ep01", "shaA", DRIFT)], tmp)
    check("单次漂移不拦单", m.drift_confirmed("w", "ep01") is False,
          "两次确认是设计核心")

    # 2. two drift records on the same bytes do block
    m = with_ledger([row("w", "ep01", "shaA", DRIFT),
                     row("w", "ep01", "shaA", DRIFT, ts="2026-10-14T11:00:00")], tmp)
    check("同内容两次漂移拦单", m.drift_confirmed("w", "ep01") is True)

    # 3. content changed between the two readings -> no agreement
    m = with_ledger([row("w", "ep01", "shaA", DRIFT),
                     row("w", "ep01", "shaB", DRIFT, ts="2026-10-14T11:00:00")], tmp)
    check("内容变动则不算确认", m.drift_confirmed("w", "ep01") is False,
          "两次必须针对同一份正文")

    # 4. an intervening PASS resets it
    m = with_ledger([row("w", "ep01", "shaA", DRIFT),
                     row("w", "ep01", "shaA", [], status="PASS",
                         ts="2026-10-14T11:00:00"),
                     row("w", "ep01", "shaA", DRIFT, ts="2026-10-14T12:00:00")], tmp)
    check("中间一次 PASS 则重新计数", m.drift_confirmed("w", "ep01") is False)

    # 5. a different defect type does not count as drift agreement
    m = with_ledger([row("w", "ep01", "shaA", DRIFT),
                     row("w", "ep01", "shaA", OTHER, ts="2026-10-14T11:00:00")], tmp)
    check("别的缺陷不算漂移确认", m.drift_confirmed("w", "ep01") is False)

    # 6. records with no content_sha cannot prove stability
    r = row("w", "ep01", "shaA", DRIFT)
    r.pop("content_sha")
    m = with_ledger([r, row("w", "ep01", "shaA", DRIFT, ts="2026-10-14T11:00:00")], tmp)
    check("无 content_sha 不确认", m.drift_confirmed("w", "ep01") is False,
          "沿用 settled_pass 的老规矩")

    # 7. a pool outage must not fabricate a genre verdict
    m = with_ledger([], tmp)
    check("空账本不拦单", m.drift_confirmed("w", "ep01") is False,
          "范围：漂移判据不拦。OTHER 类故障仍会扣留，那是既有的 fail-closed 设计")
    m = with_ledger([row("w", "ep01", "shaA", [])], tmp)
    check("PASS 记录不拦单", m.drift_confirmed("w", "ep01") is False)

    # 8. type matching is case-insensitive: the model writes whatever case
    m = with_ledger([row("w", "ep01", "shaA", [{"type": "genre_drift"}]),
                     row("w", "ep01", "shaA", [{"type": "genre_drift"}],
                         ts="2026-10-14T11:00:00")], tmp)
    check("判据名大小写不敏感", m.drift_confirmed("w", "ep01") is True)

    # 9. the ledger is corrupt -> no block, not a crash
    mod = load_verdict()
    mod.LEDGER = tmp
    tmp.write_text("{not json", encoding="utf-8")
    check("账本损坏不拦单也不崩", mod.drift_confirmed("w", "ep01") is False)

    # 10. the prompt actually allows the type, and states the corroboration rule
    prompt = (HERE / "AUDIT_PROMPT.md").read_text(encoding="utf-8")
    check("GENRE_DRIFT 在输出 schema 里", "GENRE_DRIFT" in
          prompt.split("```json")[1].split("```")[0])
    check("旧的「只记录不拦单」已移除",
          "另记一条 `genre_drift`" not in prompt)
    check("要求两次确认写进了判据",
          "连续两次" in prompt and "未改动的同一份正文" in prompt)
    check("给了不判的例外，避免滥用",
          "不要判 GENRE_DRIFT" in prompt)
    check("点名了异象/鬼物这一项", "异象与鬼物" in prompt)

    # 11. the repair prompt tells the writer this is structural
    rep = (HERE / "repair_episodes.py").read_text(encoding="utf-8")
    check("修复提示词声明这是结构问题", "结构问题，不是句子问题" in rep)
    check("修复提示词禁用信息揭露模板", "线索A → 结论" in rep)

    # 12. routing: a settled drift reaches a writer
    check("已确认漂移直派写手", "confirmed_drift" in rep)
    check("未确认漂移走确认分支", "DRIFT_UNSETTLED" in rep)
    check("确认分支认得 DRIFT_UNSETTLED", '"DRIFT_UNSETTLED" in codes' in rep)

    # 13. quarantine holds an unconfirmed drift rather than releasing it
    q = (HERE / "apply_quarantine.py").read_text(encoding="utf-8")
    check("扣留名单有 DRIFT_UNSETTLED", "DRIFT_UNSETTLED" in q)
    check("单次漂移不当作已确认", "drift_confirmed" in q)

finally:
    tmp.unlink(missing_ok=True)

print()
print("=" * 72)
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("RESULT: 题材闸门需要两次一致，且在模型池故障时不会扣留任何东西")