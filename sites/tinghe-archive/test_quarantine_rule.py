#!/usr/bin/env python3
"""Pin the asymmetry: settling is required to RELEASE, never to LOCK.

The stability rule ("release only after N consecutive PASSes on unchanged text")
was briefly applied in both directions. Because pre-hashing ledger rows cannot
prove stability, that quietly held 26 published episodes that had passed and that
nobody had objected to. Both mistakes look like caution; only one of them is.

So this test drives `apply_quarantine.main()` against synthetic ledgers and states
and asserts the exact rule:

  * published + PASS + not settled -> stays published
  * held     + PASS + not settled -> stays held
  * held     + PASS + settled     -> released
  * published + FAIL              -> held
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("aq", HERE / "apply_quarantine.py")
aq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aq)
spec2 = importlib.util.spec_from_file_location("vd", HERE / "verdict.py")
vd = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(vd)
# apply_quarantine imports `verdict` through sys.path, which yields a different
# module object than the one loaded above. Redirect the one it actually uses,
# otherwise the patched LEDGER is ignored and the release case cannot pass.
aq.verdict.LEDGER = vd.LEDGER

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="aq_rule_"))
    original = {k: getattr(aq, k) for k in ("HERE", "QUARANTINE")}
    try:
        aq.HERE = tmp
        aq.QUARANTINE = tmp / "quarantine.json"
        src = tmp / "originals_source" / "wtest"
        src.mkdir(parents=True)
        (src / "work.json").write_text(json.dumps({
            "id": "wtest", "title": "T", "tone": "t", "format": "f",
            "status": "s", "logline": "l", "chars": ["a"],
            "episodes": [{"id": f"ep0{i}", "no": i, "title": "t", "beat": "b",
                          "blocks": [{"k": "scene", "place": "p", "time": "t", "light": "l"},
                                     {"k": "cast", "present": ["a"]},
                                     {"k": "para", "t": "x"}, {"k": "hook", "t": "y"}]}
                         for i in (1, 2, 3, 4)],
        }, ensure_ascii=False), encoding="utf-8")
        vd.LEDGER = tmp / "audit_failures.json"
        aq.verdict.LEDGER = tmp / "audit_failures.json"

        def write_ledger(rows, held):
            (tmp / "audit_failures.json").write_text(
                json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            (tmp / "quarantine.json").write_text(
                json.dumps({"held": held}, ensure_ascii=False), encoding="utf-8")

        def verdict_row(ep, status, sha=None):
            return {"work": "wtest", "episode": ep, "timestamp": "2026-10-07T10:00:00+08:00",
                    "content_sha": sha, "audit": {"status": status, "issues": []}}

        def held_set():
            q = json.loads((tmp / "quarantine.json").read_text(encoding="utf-8"))
            return {(h["work"], h["episode"]) for h in q["held"]}

        # 1. published + PASS + not settled -> must NOT be held
        write_ledger([verdict_row("ep01", "PASS")], [])
        aq.main()
        check(("wtest", "ep01") not in held_set(),
              "published + single PASS is not locked (the 26-episode regression)")

        # 2. held + PASS + not settled -> stays held
        write_ledger([verdict_row("ep01", "PASS")],
                     [{"work": "wtest", "episode": "ep01", "verdict": "FAIL"}])
        aq.main()
        check(("wtest", "ep01") in held_set(), "held + single PASS stays held")

        # 3. held + two PASSes on the same text -> released
        write_ledger([verdict_row("ep01", "PASS", "aaa"),
                      dict(verdict_row("ep01", "PASS", "aaa"),
                           timestamp="2026-10-07T11:00:00+08:00")],
                     [{"work": "wtest", "episode": "ep01", "verdict": "FAIL"}])
        aq.main()
        check(("wtest", "ep01") not in held_set(),
              f"held + {vd.STABLE_PASSES} PASSes on unchanged text is released")

        # 4. held + two PASSes but the text changed -> stays held
        write_ledger([verdict_row("ep01", "PASS", "aaa"),
                      dict(verdict_row("ep01", "PASS", "bbb"),
                           timestamp="2026-10-07T11:00:00+08:00")],
                     [{"work": "wtest", "episode": "ep01", "verdict": "PASS_UNSETTLED"}])
        aq.main()
        check(("wtest", "ep01") in held_set(),
              "a PASS on changed text does not release (new text is a new question)")

        # 5. published + FAIL -> held
        write_ledger([verdict_row("ep02", "FAIL")], [])
        aq.main()
        check(("wtest", "ep02") in held_set(), "published + FAIL is locked")

        print()
        if failures:
            print(f"FAILED {len(failures)} check(s):")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("RESULT: settling gates release only; it never locks passing content")
        return 0
    finally:
        for k, v in original.items():
            setattr(aq, k, v)
        vd.LEDGER = HERE / "audit_failures.json"
        aq.verdict.LEDGER = HERE / "audit_failures.json"
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
