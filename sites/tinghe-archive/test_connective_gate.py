#!/usr/bin/env python3
"""Pin the connective gate: it must catch the regression without false alarms.

Reading fanguan/ep11 showed a repeated 虽然…可… hinge. Measuring the corpus found
the split is wide: ep01–ep09 at zero, ep11 at 6–11. The threshold is read off
that gap, which means it is only meaningful if it still separates the two groups —
so this asserts both halves: the regressed episodes are caught, and the healthy
ones are not.

It also pins two design decisions that are easy to undo by accident:
narration is counted and dialogue is not (a character hedging aloud is a person),
and the gate counts rather than judging (an LLM cannot count reliably, and this
week two LLM judgements were wrong in ways that mattered).
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cg", HERE / "connective_gate.py")
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def para(t: str) -> dict:
    return {"k": "para", "t": t}


def line(t: str) -> dict:
    return {"k": "line", "t": t}


def main() -> int:
    print("--- a regressed episode must be caught ---")
    heavy = [para("虽然他嘴上说得像是替她们跑腿，可卢茨越看越觉得这人想独吞。")]
    heavy *= 5
    heavy.append(para("虽然这屋子只剩应急灯那层微蓝，可黑得这么干脆还是让她后脖子一凉。"))
    m = cg.measure_blocks(heavy)
    check(m["hinge_total"] >= 6, f"six hinges counted (got {m['hinge_total']})")
    check(m["skeletal"], "the same hinge repeating is flagged as skeletal")
    check(m["fails"], "a regressed episode fails the gate")

    print("\n--- the bare 但 is the form the gate was blind to ---")
    # Every earlier case here spelled the hinge 可, 却 or 但是. The pattern read
    # r"虽然[^。！？]{0,60}?(?:但是|可|却)" and so matched none of the four
    # sentences below, which are the actual sentences from liufang/ep11. That
    # episode counted 3 hinges against a >3 threshold, passed the gate built to
    # catch exactly this tic, and stayed live on the site.
    live = [para("虽然舱里什么光都没了，可她还是摸到了那排冰凉的按钮。"),
            para("虽然沈砺看着就来气，但账面上那笔款子确实是他签的字。"),
            para("虽然动作挺斯文的，但刀口一直压在那条旧接缝上。"),
            para("虽然样子挺赖的，但师傅没把钥匙递出去。"),
            para("索性心一横，他干脆把钥匙按在了柜面上。"),
            para("虽然舱已经黑透了，可苏青梧数到了第三排货架。"),
            para("虽然他看不懂整枚章，但落款的位置他记住了。")]
    m = cg.measure_blocks(live)
    check(m["hinge_total"] == 7,
          f"all seven hinges in liufang/ep11 are counted (got {m['hinge_total']})")
    check(m["fails"], "liufang/ep11 as published fails the gate")

    print("\n--- 但是 still matches as one word, not 但 plus something else ---")
    m = cg.measure_blocks([para("虽然他嘴上说得像是替她们跑腿��但是卢茨越看越觉得这人想独吞。")] * 4)
    check(m["hinge_total"] == 4,
          f"four 但是 hinges, not eight (got {m['hinge_total']})")

    print("\n--- and the blind spot is gone: no hinge form escapes ---")
    for form in ("但是", "但", "可是", "可", "却"):
        m = cg.measure_blocks([para(f"虽然风声一直没停，{form}账本还在她怀里。")] * 3)
        check(m["hinge_total"] == 3,
              f"the 「虽然…{form}」 form is counted three times (got {m['hinge_total']})")

    print("\n--- a clean episode must not be flagged ---")
    clean = [para("封签箱红字从三跳到零，咔哒一声落了锁。柜灯跟着灭了。")]
    clean *= 8
    m = cg.measure_blocks(clean)
    check(m["hinge_total"] == 0, f"no hinges counted (got {m['hinge_total']})")
    check(not m["fails"], "a clean episode passes the gate")

    print("\n--- dialogue is not counted ---")
    hedged = [line("虽然这样不对，可我也没别的法子。你先把话说完。")]
    hedged *= 6
    m = cg.measure_blocks(hedged)
    check(m["hinge_total"] == 0,
          f"a character saying 虽然 six times is not a narrator tic (got {m['hinge_total']})")
    check(not m["fails"], "heavy hedging in dialogue does not fail the gate")

    print("\n--- the same hinge N times fails even under the total threshold ---")
    three = [para("虽然屋里黑，可她还是听见了那句话。"),
             para("虽然灯灭了，可账本还在怀里。"),
             para("虽然人走了，可印留下了。")]
    m = cg.measure_blocks(three + [para("补一段正常叙述，不带转折词。")])
    check(m["hinge_total"] == 3, f"three hinges counted (got {m['hinge_total']})")
    check(m["fails"], "three of the same hinge fails even though the total is at the line")

    print("\n--- the action-doubling tic: 索性…干脆 in one clause ---")
    paired = [para("索性把话闷在肚子里，干脆先让纸自己开口。")]
    paired += [para("虽然屋里只剩应急灯那层微蓝，可黑得这么干脆还是让她后脖子一凉。")] * 2
    m = cg.measure_blocks(paired)
    check(any("索性" in k for k in m["hinge_detail"]),
          f"the 索性…干脆 pair is counted ({list(m['hinge_detail'])})")
    single = cg.measure_blocks([para("她索性没接话。"),
                                para("他干脆把纸按在油纸上。")])
    check(not any("索性" in k for k in single["hinge_detail"]),
          "either word alone is ordinary usage and is not counted")

    print("\n--- the margin between healthy and regressed ---")
    # The regressed group is constructed, not mined from the corpus. It used to be
    # mined, which meant the test proved the threshold only while a bad episode
    # happened to be lying around — and on 2026-10-11 all four of them had been
    # repaired, the bad group came back empty, and the test failed because its
    # calibration set had been cured. The healthy group is still read from the
    # corpus, because "real published prose stays under the line" is a live
    # property worth failing on.
    report2 = cg.check_all()
    healthy = [v["hinge_detail"].get(v["dominant_hinge"], 0)
               for v in report2.values() if not v["fails"]]
    print(f"  healthy episodes: {len(healthy)}, dominant max="
          f"{max(healthy) if healthy else 0}, skeletal_min={cg.SKELETAL_MIN}")

    regressed = []
    for count in range(cg.SKELETAL_MIN, cg.SKELETAL_MIN + 3):
        blocks = [para("虽然这一句看着没什么，可后头那半句才是要紧的。")] * count
        regressed.append(cg.measure_blocks(blocks)["hinge_detail"].get(
            "虽然…但是/但/可/却", 0))
    print(f"  constructed regressed dominant counts: {regressed}")

    check(bool(healthy),
          "the corpus still has episodes to check the healthy group against")
    check(max(healthy) < cg.SKELETAL_MIN,
          f"no healthy episode reaches the skeletal threshold "
          f"(max {max(healthy) if healthy else 0} < {cg.SKELETAL_MIN})")
    check(bool(regressed) and min(regressed) >= cg.SKELETAL_MIN,
          f"the threshold sits at or below the regressed group "
          f"({min(regressed) if regressed else 0} >= {cg.SKELETAL_MIN})")
    check(max(healthy) < cg.SKELETAL_MIN <= min(regressed) if regressed and healthy else False,
          f"the threshold separates the two groups with room on both sides "
          f"({max(healthy) if healthy else 0} < {cg.SKELETAL_MIN} <= "
          f"{min(regressed) if regressed else 0})")

    print("\n--- banned connectives fail outright ---")
    m = cg.measure_blocks([para("显然，屋里弥漫着紧张的气息。")])
    check(m["banned_connectives"], "banned connectives are recorded")
    check(m["fails"], "a banned connective fails the gate")

    print("\n--- the live corpus splits where the threshold says it should ---")
    report = cg.check_all()
    failing = {k: v for k, v in report.items() if v["fails"]}
    clean_counts = [v["hinge_total"] for v in report.values() if not v["fails"]]
    print(f"  {len(report)} episodes, {len(failing)} fail, "
          f"healthy max {max(clean_counts) if clean_counts else 0}")
    if failing:
        print(f"  currently failing: {', '.join(sorted(failing))}")
    else:
        print("  currently failing: none (all previously regressed episodes repaired)")
    # Previously this asserted len(failing) >= 1, mining the catalogue for a bad
    # episode. Every one of them got repaired on 2026-10-10, so the assertion
    # failed on 2026-10-11 — the corpus had been cured and the test read that as
    # a broken gate. Whether live content currently regresses is a report, not an
    # invariant; that the gate *would* catch a regression is the invariant, and it
    # is checked with fixed text instead of whatever is lying around tonight.
    check((max(clean_counts) if clean_counts else 0) <= cg.THRESHOLD,
          f"no healthy episode exceeds the threshold ({cg.THRESHOLD})")
    replay = [para("虽然舱里什么光都没了，可她还是摸到了那排冰凉的按钮。"),
              para("虽然沈砺看着就来气，但账面上那笔款子确实是他签的字。"),
              para("虽然动作挺斯文的，但刀口一直压在那条旧接缝上。"),
              para("索性心一横，他干脆把钥匙按在了柜面上。")]
    check(cg.measure_blocks(replay)["fails"],
          "the gate still fails the regression it exists to catch, on fixed text")

    print()
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: the gate separates regression from the healthy corpus")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
