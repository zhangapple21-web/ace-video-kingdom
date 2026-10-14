#!/usr/bin/env python3
"""Shared verdict helpers: is this episode's PASS actually settled?

The auditor is a model, so its verdicts carry variance. The same text of
tingjijia/ep05 was audited PASS at 16:25 and FAIL at 16:35 on 2026-10-07. Acting on
a single PASS is therefore acting on one sample of a noisy judgement — which is
exactly the mistake of trusting one FAIL earlier and quarantining on it.

A PASS counts as settled only after STABLE_PASSES consecutive PASS verdicts *of the
same content*. A content change resets the streak, because a new text is a new
thing to judge and inherits none of the earlier confidence.

Kept in one place so the quarantine writer and the repair runner cannot disagree
about what "passed" means — two implementations of the same threshold is how a gate
quietly stops being a gate.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
LEDGER = HERE / "audit_failures.json"

# Two independent passes of identical text. One is not enough: the observed
# flip rate was 1 in 1 on a repaired episode, which is not a rate to bet on.
STABLE_PASSES = 2


def verdicts() -> dict[tuple[str, str], dict[str, Any]]:
    """Latest record per (work, episode)."""
    if not LEDGER.is_file():
        return {}
    rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        out[(r.get("work"), r.get("episode"))] = r
    return out


def status_of(work: str, episode: str) -> str:
    row = verdicts().get((work, episode))
    if not row:
        return "NO_VERDICT"
    return (row.get("audit") or {}).get("status", "?")


def issues_of(work: str, episode: str) -> list[dict]:
    row = verdicts().get((work, episode))
    return ((row or {}).get("audit") or {}).get("issues") or []


def settled_pass(work: str, episode: str, required: int = STABLE_PASSES) -> bool:
    """True only after `required` consecutive PASSes on unchanged content."""
    if not LEDGER.is_file():
        return False
    rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    same = [r for r in rows if r.get("work") == work and r.get("episode") == episode]
    if not same:
        return False
    # The ledger preserves order of arrival; judge the most recent verdicts.
    same.sort(key=lambda r: r.get("timestamp", ""))
    latest = same[-1]
    if (latest.get("audit") or {}).get("status") != "PASS":
        return False
    sha = latest.get("content_sha")
    if not sha:
        # Records written before content hashing existed cannot prove stability.
        return False
    streak = 0
    for row in reversed(same):
        if (row.get("audit") or {}).get("status") != "PASS":
            break
        if row.get("content_sha") != sha:
            break
        streak += 1
    return streak >= required


def pass_streak(work: str, episode: str) -> int:
    """Consecutive PASSes on unchanged text; 0 when stability cannot be proven.

    Records written before content hashing existed carry no ``content_sha``, so
    they cannot be shown to describe the same text as each other. Reporting a
    streak for them would be a number that means nothing, so it reports 0 and the
    episode must simply be audited again.
    """
    if not LEDGER.is_file():
        return 0
    rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    same = [r for r in rows if r.get("work") == work and r.get("episode") == episode]
    same.sort(key=lambda r: r.get("timestamp", ""))
    if not same:
        return 0
    latest = same[-1]
    if (latest.get("audit") or {}).get("status") != "PASS":
        return 0
    sha = latest.get("content_sha")
    if not sha:
        return 0
    streak = 0
    for row in reversed(same):
        if (row.get("audit") or {}).get("status") != "PASS":
            break
        if row.get("content_sha") != sha:
            break
        streak += 1
    return streak


# --- genre drift: the mirror of settled_pass -------------------------------
#
# GENRE_DRIFT is the one criterion that used to be explicitly forbidden from
# failing anything, on the sound grounds that a single verdict flips. The
# consequence was zero enforcement: across 342 audit records genre_drift appeared
# as an issue zero times, while the procedural-to-payoff ratio went from 5.5 to
# 6.1. The writer already receives §8b every run; the prompt was never the
# missing piece.
#
# A keyword gate cannot replace it. Two attempts on 2026-10-14 scored 80/80 and
# left 60% of beats unclassified, and the same instruments calibrated 45% to 45%
# on 2026-10-11, which is chance. So the block has to come from the auditor's
# reading, made safe by requiring agreement rather than by counting words.
#
# Mirroring settled_pass exactly: two consecutive FAILs naming GENRE_DRIFT on
# unchanged content. The sha requirement is what makes this agreement about the
# same text rather than about two versions of it.

DRIFT_TYPE = "GENRE_DRIFT"
DRIFT_CONFIRMATIONS = 2


def _names_drift(row: dict) -> bool:
    for issue in ((row.get("audit") or {}).get("issues") or []):
        if str(issue.get("type", "")).upper() == DRIFT_TYPE:
            return True
    return False


def drift_confirmed(work: str, episode: str, required: int = DRIFT_CONFIRMATIONS) -> bool:
    """True after `required` consecutive audits all named GENRE_DRIFT on the
    same, unchanged content.

    Returns False whenever stability cannot be proven — no record, no
    ``content_sha``, or a PASS or other-issue verdict in between. That is
    deliberate: a criterion that only blocks when it is certain is the right
    shape for one whose failure mode is a writer-pool outage, so a day when
    generation is down quarantines nothing.
    """
    if not LEDGER.is_file():
        return False
    try:
        rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    same = [r for r in rows if r.get("work") == work and r.get("episode") == episode]
    if not same:
        return False
    same.sort(key=lambda r: r.get("timestamp", ""))

    latest = same[-1]
    sha = latest.get("content_sha")
    if not sha or not _names_drift(latest):
        return False

    streak = 0
    for row in reversed(same):
        if row.get("content_sha") != sha:
            break
        if not _names_drift(row):
            break
        streak += 1
    return streak >= required


def drift_description(work: str, episode: str) -> str:
    """The latest GENRE_DRIFT wording, for handing to a repairer."""
    row = verdicts().get((work, episode))
    for issue in ((row or {}).get("audit") or {}).get("issues") or []:
        if str(issue.get("type", "")).upper() == DRIFT_TYPE:
            return str(issue.get("description", "")).strip()
    return ""
