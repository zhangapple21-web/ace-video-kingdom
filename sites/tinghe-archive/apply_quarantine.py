#!/usr/bin/env python3
"""Write quarantine.json from the current audit ledger, with real reasons.

Reasons are lifted from the auditor's own issue descriptions rather than
hand-written, so the hold-back list cannot drift from the evidence that caused
it. An episode is released only after a *settled* PASS — consecutive PASS verdicts
on unchanged content — not a single one, because the auditor is a model and its
verdicts have been observed flipping on identical text.

Only run this after verify_verdict_evidence.py has passed. That check exists
because the previous hold-back list was built from verdicts produced by a broken
audit context, and seven published episodes were withdrawn on that basis.
"""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
QUARANTINE = HERE / "quarantine.json"
sys.path.insert(0, str(HERE))
import verdict  # noqa: E402

NOTE = ("Episodes held out of publishing until they carry a settled PASS verdict "
        "(consecutive PASSes on unchanged text). Reasons are the auditor's own "
        "issue text. An episode is republished by deleting its entry; the authored "
        "text stays in originals_source/<work>/work.json either way, so nothing is "
        "destroyed by holding it back.")


def main() -> int:
    rows = json.loads((HERE / "audit_failures.json").read_text(encoding="utf-8"))
    authored = set()
    for wf in sorted((HERE / "originals_source").glob("*/work.json")):
        data = json.loads(wf.read_text(encoding="utf-8"))
        for ep in data.get("episodes", []):
            authored.add((data["id"], ep["id"]))

    # What is held *right now*. The previous state matters, because the stability
    # rule is deliberately asymmetric: settling is required to RELEASE an episode,
    # never to newly lock one. An earlier version applied it both ways and, because
    # pre-hashing ledger rows cannot prove stability, quietly held 26 published
    # episodes that nobody had objected to. Withdrawing content that is fine is not
    # a safe default; it is just a different bug.
    currently_held: set[tuple[str, str]] = set()
    qpath = QUARANTINE
    if qpath.is_file():
        try:
            existing = json.loads(qpath.read_text(encoding="utf-8-sig"))
            for item in (existing.get("held") if isinstance(existing, dict) else existing) or []:
                currently_held.add((item.get("work"), item.get("episode")))
        except (OSError, json.JSONDecodeError):
            currently_held = set()

    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        latest[(r.get("work"), r.get("episode"))] = r

    held = []
    released = []

    # A mechanical verdict belongs in the hold list, not in a pipeline-wide block.
    # The connective gate measures a fact (how many times the narrator reaches for
    # the same hinge) and it flagged four episodes. Wired into verify_originals_batch
    # it would have failed that gate and blocked all 46 live episodes from shipping —
    # four episodes with a verbal habit silencing the whole catalogue. The audit
    # path already answers this correctly: a failing episode is held, the rest ship.
    # The connective verdict now takes the same route.
    connective_failures: dict[tuple[str, str], dict] = {}
    try:
        import connective_gate

        for key, measured in connective_gate.check_all().items():
            if measured["fails"]:
                work_id, ep_id = key.split("/", 1)
                detail = measured.get("hinge_detail") or {}
                worst = max(detail, key=lambda k: detail[k]) if detail else ""
                times = detail.get(worst, measured.get("hinge_total", 0))
                # Written in Chinese, like every other instruction this pipeline
                # gives a model. An English reason dropped into a Chinese brief
                # weakens it, and this string is the ONLY thing the repairer knows
                # about why the episode is held when its audit verdict is PASS.
                reason = (
                    f"叙述重复使用同一个转折骨架（最严重的是「{worst}」，{times} 处；"
                    f"全片 {measured['hinge_total']} 处，密度 {measured['density_per_1k']}/千字）。"
                    f"合格线是同一骨架最多 2 处、全集最多 3 处——其余 43 集都是 0~2 处。"
                    f"换骨架：后半句直接顶上来不接头词，或断成独立短句。"
                    f"只改叙述句式，不要动剧情、人物、线索。"
                )
                if measured.get("banned_connectives"):
                    reason += f" 另需清除书面连接词：{'、'.join(measured['banned_connectives'])}。"
                reason += " 改完跑 py -3 connective_gate.py 自查，本集必须不再被报出。"
                connective_failures[(work_id, ep_id)] = {
                    **measured, "reason_zh": reason}
    except Exception as exc:
        print(f"[WARN] connective gate could not be read ({type(exc).__name__}: {exc}); "
              f"holding nothing on that basis")

    for (work, ep), measured in sorted(connective_failures.items()):
        held.append({
            "work": work, "episode": ep, "verdict": "STYLE_FAIL",
            "codes": ["CONNECTIVE_SKELETON"],
            "reason": measured.get("reason_zh", ""),
        })

    for (work, ep), row in sorted(latest.items()):
        if (work, ep) not in authored:
            continue
        if (work, ep) in connective_failures:
            continue          # already held above, on the stronger mechanical verdict
        audit = row.get("audit") or {}
        is_held_now = (work, ep) in currently_held

        if audit.get("status") == "PASS":
            if not is_held_now:
                continue                      # published and passing: leave it alone
            if verdict.settled_pass(work, ep):
                released.append(f"{work}/{ep}")
                continue
            streak = verdict.pass_streak(work, ep)
            held.append({
                "work": work, "episode": ep, "verdict": "PASS_UNSETTLED",
                "codes": ["PASS_STREAK"],
                "reason": (f"held back; repair scored PASS but not settled "
                           f"({streak}/{verdict.STABLE_PASSES} consecutive PASSes on "
                           f"unchanged text). The auditor's verdict was observed flipping "
                           f"on identical text, so one passing sample does not release it."),
            })
            continue

        issues = audit.get("issues") or []
        codes = []
        for issue in issues:
            code = issue.get("type") or issue.get("severity") or "ISSUE"
            if code not in codes:
                codes.append(code)

        # GENRE_DRIFT is the one criterion held back for corroboration rather
        # than acted on immediately. A single reading of "this episode is an
        # investigation, not a turnaround" is not enough to send an episode to a
        # writer: the auditor's verdict has been observed flipping on identical
        # text, and a wrong call here costs a rewrite. It holds the episode and
        # waits for a second reading on the same bytes — the same shape as an
        # unsettled PASS, which also holds rather than releases.
        #
        # Anything else in the issue list means there is a concrete defect, and
        # corroboration is not required for those.
        non_drift = [i for i in issues
                     if str(i.get("type", "")).upper() != verdict.DRIFT_TYPE]
        if issues and not non_drift and not verdict.drift_confirmed(work, ep):
            first = " ".join(str(issues[0].get("description", "")).split())
            if len(first) > 200:
                first = first[:197] + "..."
            held.append({
                "work": work, "episode": ep, "verdict": "DRIFT_UNSETTLED",
                "codes": ["GENRE_DRIFT"],
                "reason": ("held back; one audit named GENRE_DRIFT and the text is "
                           "unchanged. The auditor's verdict has been observed flipping "
                           "on identical text, so one reading does not send this to a "
                           "writer — a second reading on the same bytes is required. "
                           + first),
            })
            continue

        first = str(issues[0].get("description", "")).strip() if issues else ""
        first = " ".join(first.split())
        if len(first) > 220:
            first = first[:217] + "..."
        reason = f"{audit.get('status')} ({', '.join(codes) or 'unspecified'})"
        if first:
            reason += f": {first}"
        held.append({
            "work": work,
            "episode": ep,
            "verdict": audit.get("status"),
            "codes": codes,
            "reason": reason,
        })

    data = {
        "schema": "tinghe.quarantine.v1",
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "note": NOTE,
        "held": held,
    }
    QUARANTINE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    print(f"quarantine.json written: {len(held)} episode(s) held")
    for h in held:
        print(f"  {h['work']}/{h['episode']}  {','.join(h['codes']) or '-'}")
    if released:
        print(f"\nreleased (settled PASS, {verdict.STABLE_PASSES}x on unchanged text): {len(released)}")
        for item in released:
            print(f"  {item}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
