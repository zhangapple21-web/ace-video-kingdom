#!/usr/bin/env python3
"""Stop sending episodes that only need a second audit to a writer model.

Two kinds of episode sit on the hold list and they want opposite handling:

  a real defect         connective skeleton, a failed audit. Needs an edit.
  PASS_UNSETTLED        the auditor passed it once, and one pass is not enough
                        to trust a judgement that has been observed flipping.
                        Nothing is wrong with the chapter. It needs looking at
                        again, not rewriting.

The repair runner treated both as "held", so the second kind was handed to a
writer with the instruction that it was held and needed fixing. The writer
correctly found nothing to fix, changed nothing, and the runner moved to the next
model — see repair_one's `blocks unchanged` branch, which `continue`s past the
audit entirely. On 2026-10-10 that was 5 episodes x 2 models, roughly fifty
minutes of generation on chapters that were fine, and a standing chance that a
writer would "improve" a passing chapter and break it.

The hold reason made it worse rather than better. Until now those episodes were
told "审核判词是 PASS… 真正的问题是下面这条，按它修" and then given
"held back; repair scored PASS but not settled" — an English sentence that is not
a problem anyone can act on.

This adds the split: corroboration holds go to run_audit.py on unchanged text
until the PASS settles, and only reach a writer if they come back FAIL with real
issues. The misleading prompt wording is softened so it cannot claim a defect
that was never found.

Idempotent.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE / "repair_episodes.py"

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


# ---------------------------------------------------------------- 1. new functions

NEW_FUNCS = '''def hold_codes(work_id: str, ep_id: str) -> list[str]:
    """The codes on the hold list for this episode, lowercased."""
    q = HERE / "quarantine.json"
    if not q.is_file():
        return []
    try:
        data = json.loads(q.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []
    for item in (data.get("held") if isinstance(data, dict) else data) or []:
        if item.get("work") == work_id and item.get("episode") == ep_id:
            return [str(c).upper() for c in (item.get("codes") or [])]
    return []


def needs_corroboration(work_id: str, ep_id: str) -> bool:
    """True when this episode is held only for want of a second PASS.

    Nothing is wrong with the text in this case. The auditor passed it once and
    one sample of a judgement that has been measured flipping is not enough to
    let it ship, so it is held pending a second look at the same bytes.

    These must not be handed to a writer. Told that an episode is held and needs
    fixing, with nothing actually wrong, a writer has only two moves: do nothing
    (wasting the attempt) or invent an edit to a chapter that passed.
    """
    return "PASS_STREAK" in hold_codes(work_id, ep_id)


def confirm_only(work_id: str, ep_id: str, rounds: int = 2) -> str:
    """Re-audit an unchanged episode until its PASS settles, or it fails for real.

    Returns PASS when the second consecutive PASS lands on identical text, and
    STILL_FAILING otherwise. A FAIL here is useful rather than a dead end: it
    carries issues, so the next repair round has something concrete to work from.
    """
    import verdict as verdict_mod

    for i in range(1, rounds + 1):
        log(f"  {work_id}/{ep_id}: no defect recorded; audit {i}/{rounds} on unchanged text")
        try:
            proc = subprocess.run(
                [sys.executable, "-u", str(HERE / "run_audit.py"), work_id, ep_id],
                cwd=HERE, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=900)
        except subprocess.TimeoutExpired:
            log(f"    audit {i} timed out")
            continue
        status = verdict_mod.status_of(work_id, ep_id)
        log(f"    audit {i}: exit={proc.returncode} verdict={status}")
        if status != "PASS":
            if status != "NO_VERDICT":
                issues = verdict_mod.issues_of(work_id, ep_id)
                log(f"    came back FAIL with {len(issues)} issue(s); "
                    f"now it has something to repair")
            return "STILL_FAILING"
        if verdict_mod.settled_pass(work_id, ep_id):
            log("    settled PASS on unchanged text; hold can be lifted")
            return "PASS"
    log("    still not settled; stays held")
    return "STILL_FAILING"


'''

ANCHOR_FN = "def repair_one(work_id: str, ep_id: str, models: list[str], timeout: int) -> str:"

# ------------------------------------------------- 2. honest prompt wording

OLD_WORDING = ('''            return ("【注意】审核判词是 PASS，本集被扣下"
                    "**不是因为剧情不合格**。真正的问题"
                    "是下面这条，按它修，不要动剧情：\\n\\n"
                    + reason)''')

NEW_WORDING = ('''            return ("【注意】审核判词是 PASS，本集没有被指出剧情缺陷。"
                    "下面这段只是解释它为什么还在扣留名单上——"
                    "**按它说的那一条改，不要凭空发挥，也不要动剧情**：\\n\\n"
                    + reason)''')

# ------------------------------------------------------------- 3. route in main

OLD_ROUTE = '''    if not targets:
        log("nothing is held back; nothing to repair")
        return 0
'''
NEW_ROUTE = '''    if not targets:
        log("nothing is held back; nothing to repair")
        return 0

    # Split by what the hold is actually for. An episode held for want of a
    # second audit has nothing to repair; sending it to a writer spends the
    # attempt and risks an edit to a chapter that passed.
    to_confirm = [t for t in targets if needs_corroboration(*t)]
    to_repair = [t for t in targets if t not in to_confirm]
    if to_confirm:
        log(f"{len(to_confirm)} held episode(s) await corroboration, not repair: "
            f"{', '.join(f'{w}/{e}' for w, e in to_confirm)}")
'''

OLD_LOOP = '''    for work, ep in targets:
        results.setdefault(repair_one(work, ep, models, args.timeout), []).append(f"{work}/{ep}")
'''
NEW_LOOP = '''    for work, ep in to_confirm:
        results.setdefault(confirm_only(work, ep), []).append(f"{work}/{ep}")

    for work, ep in to_repair:
        results.setdefault(repair_one(work, ep, models, args.timeout), []).append(f"{work}/{ep}")
'''

OLD_CALL = "        return _run_repairs(args, models, targets)"
NEW_CALL = "        return _run_repairs(args, models, targets, to_confirm, to_repair)"

OLD_SIG = "def _run_repairs(args, models: list[str], targets: list[tuple[str, str]]) -> int:"
NEW_SIG = ("def _run_repairs(args, models: list[str], targets: list[tuple[str, str]],\n"
           "                 to_confirm: list[tuple[str, str]],\n"
           "                 to_repair: list[tuple[str, str]]) -> int:")


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if "def needs_corroboration(" in text:
        print("already patched")
        return 0

    for old, new, label in (
        (ANCHOR_FN, NEW_FUNCS + ANCHOR_FN, "inserted the corroboration functions"),
        (OLD_WORDING, NEW_WORDING, "softened the misleading prompt wording"),
        (OLD_ROUTE, NEW_ROUTE, "added the split in main()"),
        (OLD_LOOP, NEW_LOOP, "routed each group to its own handler"),
        (OLD_CALL, NEW_CALL, "passed the split into _run_repairs"),
        (OLD_SIG, NEW_SIG, "widened _run_repairs' signature"),
    ):
        check(old in text, f"found anchor: {label}")
        if old not in text:
            return 1
        text = text.replace(old, new, 1)

    TARGET.write_text(text, encoding="utf-8")
    print("\npatched")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())