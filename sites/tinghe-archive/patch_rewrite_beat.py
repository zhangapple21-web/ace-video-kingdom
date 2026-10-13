#!/usr/bin/env python3
"""Make the rewriter replace the beat, not only the blocks.

The first rewrite of zhenqianjin/ep09 came back genuinely good: a concrete stake
(a numbered mining permit with a nine-minute countdown), a win performed on stage,
a queue watching the owner fail to sign, and the 081723 number demoted from the
episode's spine to a single line of corroboration. The measurement agreed and the
reading agreed.

And the `beat` field was left untouched:

    三日期满产科封签送达矿务署 · 青梧在档案窗口当场拆开，手环编号对上空栏

That is the old procedural spine. The next episode's writer reads this episode's
beat in its context bundle, so a rewritten episode carrying its old spine pulls
the following episode straight back toward paperwork — undoing the rewrite one
step downstream. The beat is the authored decision about what an episode is FOR;
leaving it stale is leaving the rewrite half-applied.

Rewrites must therefore supply a new beat in the same shape: 压她的是什么 → 她
当场怎么翻回来, not what record matched what.

Also fixes this episode, whose blocks are already rewritten and whose beat is not.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent

# --- 1. the rewriter's prompt must ask for a new beat -----------------------
PROMPT_OLD = '"改完依次执行：build_originals.py → verify_originals_batch.py → "'
PROMPT_NEW = ('"【必须一并改写本集的 beat 字段】beat 是这一集的脊梁，'
              '下一集的作家会在上下文包里读到它。旧的 beat 写着「档案窗口拆封、'
              '手环编号对上空栏」这种比对任务，留着会把后面几集重新拉回程序腔。'
              '新 beat 要写成：谁在压她 · 她当场怎么翻回来（不要写成两份文件对上了）。'
              "格式与旧 beat 一致，用 `·` 分隔。\\n\"\n        "
              '"改完依次执行：build_originals.py → verify_originals_batch.py → "')

# --- 2. accept and validate the new beat ------------------------------------
ACCEPT_OLD = '''            now_ep = next((e for e in now_data["episodes"] if e["id"] == eid), None)
            if now_ep is None or now_ep.get("blocks") == ep.get("blocks"):
                print("    blocks unchanged; restoring and trying the next model")
                shutil.copy2(backup, work_path)
                continue'''

ACCEPT_NEW = '''            now_ep = next((e for e in now_data["episodes"] if e["id"] == eid), None)
            if now_ep is None or now_ep.get("blocks") == ep.get("blocks"):
                print("    blocks unchanged; restoring and trying the next model")
                shutil.copy2(backup, work_path)
                continue
            if str(now_ep.get("beat") or "").strip() == str(ep.get("beat") or "").strip():
                # A rewrite that leaves the old spine behind is half applied: the
                # next episode's writer reads this beat in its context bundle and
                # gets pulled back toward the paperwork register.
                print("    beat unchanged; the old spine would drag the next "
                      "episode back. restoring and trying the next model")
                shutil.copy2(backup, work_path)
                continue'''


def main() -> int:
    changed = 0

    runner = HERE / "rewrite_episodes.py"
    text = runner.read_text(encoding="utf-8")
    if "必须一并改写本集的 beat" not in text:
        if PROMPT_OLD not in text:
            print("[FAIL] prompt anchor not found in rewrite_episodes.py")
            return 1
        runner.write_text(text.replace(PROMPT_OLD, PROMPT_NEW, 1), encoding="utf-8")
        print("[PASS] the prompt now asks for a new beat")
        changed += 1
    else:
        print("[SKIP] prompt already asks for a new beat")

    text = runner.read_text(encoding="utf-8")
    if "beat unchanged; the old spine" not in text:
        if ACCEPT_OLD not in text:
            print("[FAIL] acceptance anchor not found")
            return 1
        runner.write_text(text.replace(ACCEPT_OLD, ACCEPT_NEW, 1), encoding="utf-8")
        print("[PASS] a rewrite that leaves the beat is rejected")
        changed += 1
    else:
        print("[SKIP] beat-change check already present")

    import py_compile
    try:
        py_compile.compile(str(runner), doraise=True)
    except py_compile.PyCompileError as exc:
        print(f"[FAIL] does not compile: {exc}")
        return 1
    print("[PASS] compiles")

    # --- 3. fix the episode that is already half-rewritten --------------------
    path = HERE / "originals_source" / "zhenqianjin" / "work.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    ep = next(e for e in data["episodes"] if e["id"] == "ep09")
    old_beat = str(ep.get("beat") or "")
    new_beat = ("矿务署念暂扣令停采三天 · 青梧拿阿禾的工牌当押 · "
                "抓起没干的章泥在担保单上手按下去 · 采掘牌归她，三天为限")

    if old_beat == new_beat:
        print("[SKIP] zhenqianjin/ep09 beat already current")
    else:
        ep["beat"] = new_beat
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print(f"[PASS] zhenqianjin/ep09 beat updated")
        print(f"       old: {old_beat}")
        print(f"       new: {new_beat}")

    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())