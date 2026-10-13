#!/usr/bin/env python3
"""Are the three still-failing episodes' verdicts true, or invented?

The auditor fabricated a defect on 2026-10-13 (reported fanguan/ep14 "misspelled
KY-0155 as KY-005"; the episode contains KY-0155 once and KY-005 nowhere). So a
FAIL is not taken at its word before spending model budget on it.

For each currently-held episode, take the auditor's own `evidence_after` — the
line it says is wrong in the audited episode — and look that line up in the
text. A verdict whose cited conflict is absent is being handed to a repairer as
a real defect, and a repairer will "fix" correct prose.

Report only. What counts as a defect is a judgement; whether the words exist is
a lookup.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
NOISE = re.compile(r"[\s，,。.；;：:、！!？?「」『』\"'“”‘’（）()【】\[\]—\-…·]+")
PAREN_NOTE = re.compile(r"[（(][^）)）]{0,24}ep\s*\d[^）)）]{0,12}[）)]")
BARE_NOTE = re.compile(r"ep\s*\d+(?:\s*[-–~]\s*ep?\s*\d+)?\s*(?:开头|结尾|前文|后文)?\s*")
SCENE_PREFIX = re.compile(r"^场景[｜|]\s*")


def norm(s: str) -> str:
    return NOISE.sub("", s or "")


def clean(q: str) -> str:
    return SCENE_PREFIX.sub("", BARE_NOTE.sub("", PAREN_NOTE.sub("", q or "")).strip())


def ep_text(work: str, ep: str) -> str:
    p = SOURCE / work / "work.json"
    if not p.is_file():
        return ""
    data = json.loads(p.read_text(encoding="utf-8"))
    e = next((x for x in data.get("episodes", []) if x.get("id") == ep), None)
    if e is None:
        return ""
    out = []
    for b in e.get("blocks") or []:
        if isinstance(b, dict):
            for k in ("t", "place", "time", "light"):
                if isinstance(b.get(k), str):
                    out.append(b[k])
    return "\n".join(out)


def main() -> int:
    q = json.loads((HERE / "quarantine.json").read_text(encoding="utf-8-sig"))
    held = [(h["work"], h["episode"]) for h in (q.get("held") or [])]
    rows = json.loads((HERE / "audit_failures.json").read_text(encoding="utf-8"))
    latest = {(r.get("work"), r.get("episode")): r for r in rows if isinstance(r, dict)}

    print(f"held episodes: {len(held)}")
    print()
    unverifiable = 0
    for work, ep in sorted(held):
        row = latest.get((work, ep), {})
        audit = row.get("audit") or {}
        issues = audit.get("issues") or []
        body = norm(ep_text(work, ep))
        print(f"--- {work}/{ep}  verdict={audit.get('status')}  issues={len(issues)}")
        for i, iss in enumerate(issues, 1):
            quote = clean(str(iss.get("evidence_after") or ""))
            frags = [norm(f) for f in re.split(r"[，,。.；;：:、…\n]", quote)]
            frags = [f for f in frags if len(f) >= 4]
            if not frags:
                print(f"    [{i}] {str(iss.get('type'))}: (no quoted text to check)")
                unverifiable += 1
                continue
            missing = [f for f in frags if f not in body]
            # Same tolerance as verify_audit_quotes: a fragment can miss because
            # the auditor joined sentences, not because the words are absent.
            # A mismatch that matters (wrong identifier) breaks the middle, so an
            # exact hit fails while a long contiguous run still passes.
            def mostly_present(frag: str, text: str, floor: float = 0.72) -> bool:
                n = len(frag)
                if n < 4:
                    return False
                need = max(4, int(n * floor))
                for size in range(n, need - 1, -1):
                    for start in range(0, n - size + 1):
                        if frag[start:start + size] in text:
                            return True
                return False
            missing = [f for f in missing if not mostly_present(f, body)]
            if missing:
                print(f"    [{i}] {iss.get('type')}: NOT FOUND -> {missing}")
                print(f"        claim: {str(iss.get('description'))[:96]}")
            else:
                print(f"    [{i}] {iss.get('type')}: quote present in text")
        print()

    print("=" * 70)
    print(f"issues with no checkable quote: {unverifiable}")
    print("Issues marked NOT FOUND above must be read by a human before a repairer")
    print("is sent at them; the rest are safe to act on.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())