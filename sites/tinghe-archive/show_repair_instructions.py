#!/usr/bin/env python3
"""What does the repair prompt actually tell each held episode?

Three of tonight's episodes came back "blocks unchanged" from both models. A
repairer that is handed an episode it cannot act on will always do that, so the
question is whether the two hold types get two different instructions.

They should not get the same one:

  PASS_UNSETTLED  the audit passed once and has not been corroborated a second
                  time. Nothing is broken. The episode needs a second look, not
                  an edit. Asking a writer to repair it wastes an attempt and,
                  worse, invites a random change to a chapter that was fine.

  a real defect   connective skeleton, a failed audit — these need an edit.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("r", HERE / "repair_episodes.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def main() -> int:
    q = json.loads((HERE / "quarantine.json").read_text(encoding="utf-8-sig"))
    held = sorted(q.get("held") or [], key=lambda h: (h["work"], h["episode"]))

    by_type: dict[str, list[str]] = {}
    for h in held:
        w, e = h["work"], h["episode"]
        verdict = str(h.get("verdict") or "")
        reason = m.hold_reason(w, e) or ""
        by_type.setdefault(verdict, []).append(f"{w}/{e}")

        print(f"-- {w}/{e}   verdict={verdict}  codes={h.get('codes')}")
        print(f"   reason given to the model: {reason[:100]}")
        # Does the instruction contain anything the model can act on?
        actionable = any(k in reason for k in ("处", "改成", "改为", "删", "换", "修"))
        if verdict.endswith("UNSETTLED") or verdict == "PASS_STREAK":
            print(f"   verdict says: nothing is broken, needs corroboration")
            print(f"   actionable for a writer? {'yes' if actionable else 'NO'}")
        print()

    print("=== hold types and how many ===")
    for verdict, keys in sorted(by_type.items()):
        print(f"  {verdict:<16} {len(keys):>2}   {', '.join(keys)}")

    unsettled = [k for v, ks in by_type.items()
                 if v.endswith("UNSETTLED") or v == "PASS_STREAK" for k in ks]
    if unsettled:
        print(f"\n{len(unsettled)} episode(s) are held for want of a second "
              f"audit, not for a defect.")
        print("Sending these to a writer model asks it to repair a chapter that "
              "is not broken.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())