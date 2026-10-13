#!/usr/bin/env python3
"""Independently verify each verdict cites only strictly-earlier episodes.

The fix for the mis-ordered audit context (`prior_context`) is trusted here on
purpose suspicion only: it is the same code path that previously failed a quarter
of the catalogue. Quarantining 15 episodes is a destructive act, so before acting
on these verdicts, check the property that the old bug violated.

Every issue names the episode it is about and quotes `evidence_before`. If a
verdict for epN cites epM with M >= N as its *prior* evidence, the context is
still leaking the future and the verdict must not be acted on. A verdict whose
cited prior episodes are all strictly earlier is consistent with a correctly
ordered audit — necessary, not sufficient, but it is the check that would have
caught the original defect.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
LEDGER = HERE / "audit_failures.json"
QUARANTINE = HERE / "quarantine.json"


def ep_no(token: str) -> int | None:
    m = re.search(r"ep(\d+)", token or "")
    return int(m.group(1)) if m else None


def main() -> int:
    rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        latest[(r.get("work"), r.get("episode"))] = r

    suspicious: list[tuple[str, str, str]] = []
    clean_failures: list[tuple[str, str]] = []

    for (work, ep), row in sorted(latest.items()):
        audit = row.get("audit") or {}
        if audit.get("status") == "PASS":
            continue
        target = ep_no(ep)
        for issue in audit.get("issues") or []:
            # The issue's own `episode` field says which chapter it is about. That
            # must be the audited chapter (or later context leaking in).
            cited = ep_no(str(issue.get("episode", "")))
            if cited is not None and target is not None and cited > target:
                suspicious.append((work, ep,
                                   f"issue about ep{cited:02d} but audited ep{target:02d}"))
            for key in ("evidence_before", "evidence_after"):
                for token in re.findall(r"ep\d+", str(issue.get(key, ""))):
                    n = ep_no(token)
                    if n is not None and target is not None and n > target:
                        suspicious.append((work, ep, f"{key} cites {token} (later than ep{target:02d})"))
        clean_failures.append((work, ep))

    print(f"verdicts in ledger : {len(latest)}")
    print(f"failing            : {len(clean_failures)}")
    print(f"suspicious         : {len(suspicious)}")
    print()
    if suspicious:
        print("VERDICTS THAT STILL SEE THE FUTURE — do not act on them:")
        for work, ep, why in suspicious:
            print(f"  {work}/{ep}: {why}")
        print("\nThe context fix is not holding. Quarantining anything now would be")
        print("repeating the original mistake.")
        return 1

    print("every FAIL cites only strictly-earlier episodes as its prior evidence")
    print("so these verdicts are consistent with a correctly ordered audit.\n")
    held = []
    qpath = QUARANTINE
    if qpath.is_file():
        q = json.loads(qpath.read_text(encoding="utf-8-sig"))
        held = {(i.get("work"), i.get("episode")) for i in ((q.get("held") or []))}
    for work, ep in clean_failures:
        mark = " (already held)" if (work, ep) in held else ""
        print(f"  FAIL {work}/{ep}{mark}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
