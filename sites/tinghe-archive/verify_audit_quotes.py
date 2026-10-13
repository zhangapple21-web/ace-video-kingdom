#!/usr/bin/env python3
"""Check that every quote an audit issue leans on actually exists in the text.

verify_verdict_evidence.py asks whether a verdict cites the future. It does not
ask whether the quoted words are there at all — and on 2026-10-13 an audit
reported, as MAJOR:

    新集将证物编号 KY-0155 误写为 KY-005

The episode contains "KY-0155" once and "KY-005" nowhere. The auditor had read
the real sentence (it reproduced the surrounding words correctly) and got the
digits wrong. That single invented defect was enough to put a passing episode
on the hold list and send a repairer to edit correct text.

So: pull each issue's evidence_after, split it on punctuation, normalise away
spacing and quote marks, and require every substantial fragment to appear in the
episode being audited. Report only — this reads model output and quotes may
legitimately be trimmed — but the numbers decide whether it ever becomes a gate.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
LEDGER = HERE / "audit_failures.json"
SOURCE = HERE / "originals_source"

# Punctuation and quote marks, ASCII and CJK: the auditor re-punctuates freely.
NOISE = re.compile(r"[\s，,。.；;：:、！!？?「」『』\"'“”‘’（）()【】\[\]—\-…·]+")
# A fragment shorter than this is not enough signal to accuse anyone.
MIN_FRAGMENT = 4

# The auditor appends its own annotations to quotes — （ep15开头）, (ep13结尾),
# ep11-ep12 and so on. Those are commentary, not quoted text; checking them
# flagged three perfectly honest quotes on 2026-10-13.
#
# Two passes, both requiring the "ep" plus digits to be present. An earlier
# version made every quantifier optional, which matches the empty string at
# every position — re.sub then "succeeds" everywhere and removes nothing, and
# the bug looks exactly like the strip simply not being applied.
PAREN_NOTE = re.compile(r"[（(][^）)）]{0,24}ep\s*\d[^）)）]{0,12}[）)]")
BARE_NOTE = re.compile(r"ep\s*\d+(?:\s*[-–~]\s*ep?\s*\d+)?\s*(?:开头|结尾|前文|后文)?\s*")
# The auditor quotes scene lines in their rendered form, "场景｜地点 ｜ 时间", while
# the data keeps place and time in separate fields. Joining them reproduces the
# rendered form, but the literal "场景" prefix is not stored anywhere.
SCENE_PREFIX = re.compile(r"^场景[｜|]\s*")


def normalise(text: str) -> str:
    return NOISE.sub("", text or "")


def clean_quote(quote: str) -> str:
    """Drop the auditor's own annotations and the rendered scene prefix."""
    out = PAREN_NOTE.sub("", quote or "")
    out = BARE_NOTE.sub("", out)
    out = SCENE_PREFIX.sub("", out.strip())
    return out


def episode_text(work: str, ep_id: str) -> str:
    p = SOURCE / work / "work.json"
    if not p.is_file():
        return ""
    data = json.loads(p.read_text(encoding="utf-8"))
    ep = next((e for e in data.get("episodes", []) if e.get("id") == ep_id), None)
    if ep is None:
        return ""
    out = []
    for b in ep.get("blocks") or []:
        if isinstance(b, dict):
            for key in ("t", "place", "time", "light"):
                v = b.get(key)
                if isinstance(v, str):
                    out.append(v)
    return "\n".join(out)


def fragments(quote: str) -> list[str]:
    parts = re.split(r"[，,。.；;：:、…\n]", clean_quote(quote))
    return [normalise(p) for p in parts if len(normalise(p)) >= MIN_FRAGMENT]


def main() -> int:
    rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        latest[(r.get("work"), r.get("episode"))] = r

    checked = 0
    bad: list[tuple[str, str, str, list[str]]] = []

    for (work, ep), row in sorted(latest.items()):
        audit = row.get("audit") or {}
        if audit.get("status") == "PASS":
            continue
        body = normalise(episode_text(work, ep))
        if not body:
            continue
        for issue in audit.get("issues") or []:
            quote = str(issue.get("evidence_after") or "")
            frags = fragments(quote)
            if not frags:
                continue
            checked += 1
            missing = [f for f in frags if f not in body]
            if missing:
                bad.append((work, ep, quote, missing))

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (HERE / f".audit_quote_check.{stamp}.json").write_text(
        json.dumps({"checked": checked,
                    "suspect": [{"work": w, "episode": e, "quote": q,
                                 "missing": m} for w, e, q, m in bad]},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"quotes checked : {checked}")
    print(f"not found      : {len(bad)}")
    print()
    for work, ep, quote, missing in bad:
        first_missing = missing[0]
        where = body_find(episode_text(work, ep), first_missing)
        print(f"[SUSPECT] {work}/{ep}")
        print(f"    quote   : {quote[:88]}")
        print(f"    missing : {missing}")
        if where:
            print(f"    nearest : …{where}…")
    print()
    if bad:
        print(f"{len(bad)} quote(s) do not appear in the audited episode.")
        print("Either the auditor invented them, or the text changed after the audit.")
        print("Do NOT hand these to a repairer without a human look.")
        return 1
    print("every evidence_after fragment appears in the episode it describes")
    return 0


def body_find(raw: str, missing: str) -> str:
    """Show what the episode says where the quote claimed something else."""
    idx = raw.find(missing)
    if idx >= 0:
        return raw[max(0, idx - 20):idx + 20]
    # Try the numeric core, e.g. KY-005 -> look for KY-
    m = re.match(r"^([A-Za-z]{1,4})", missing)
    if m:
        idx = raw.find(m.group(1))
        if idx >= 0:
            return raw[max(0, idx - 20):idx + 24]
    return ""


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
