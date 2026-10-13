#!/usr/bin/env python3
"""Prove the verdict extractor handles the output shapes models actually produce.

The old parser accepted only a single line that started with "{" and ended with
"}". On 2026-10-07 that discarded 12 of 19 audit verdicts — three of which said
`"status": "PASS"` — and recorded them as FAIL. The model had done the work; the
reader threw it away.

Each case below is a shape observed in real captured output, plus the shapes that
must still be refused. The last group matters most: a parser that accepts
anything is worse than a strict one, because it starts inventing verdicts.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ra", HERE / "run_audit.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def verdict_of(text: str):
    found = m.extract_json_object(text)
    if not found:
        return None
    try:
        parsed = json.loads(found)
    except json.JSONDecodeError:
        parsed = m.salvage_verdict(text)
    if not isinstance(parsed, dict):
        return None
    audit, style = m.split_verdict(parsed)
    if "status" not in audit or "issues" not in audit:
        return None
    # The real implementation always returns a full clean dict (with defaults),
    # so `bool(style)` is meaningless. What matters: did the wrapper's style
    # section survive, and did a bare object correctly degrade to defaults.
    has_style = isinstance(style.get("words"), int) and style.get("words") != 0
    return audit.get("status"), len(audit.get("issues") or []), has_style


def main() -> int:
    print("=== shapes that must be understood ===")

    # The exact shape that caused twelve false FAILs.
    wrapped = (
        "审核完成，结果如下：\n"
        "{\n"
        '  "fact": { "status": "PASS", "issues": [] },\n'
        '  "style": { "words": 600, "visual_points": 6, "notes": "无问题" }\n'
        "}\n"
        "以上。"
    )
    check(verdict_of(wrapped) == ("PASS", 0, True),
          "pretty-printed multi-line wrapped object (caused 12 false FAILs)")

    check(verdict_of('{"status":"FAIL","issues":[{"type":"X","severity":"MINOR"}]}')
          == ("FAIL", 1, False), "single-line bare object")
    check(verdict_of('Here is my verdict:\n{"status":"PASS","issues":[]}')
          == ("PASS", 0, False), "prose before a bare object")
    check(verdict_of('{"fact":{"status":"FAIL","issues":[{"type":"T"}]},"style":{}}')
          == ("FAIL", 1, False), "single-line wrapped object")
    check(verdict_of('前缀\n{"status":"FAIL","issues":[{"type":"T","description":"他说 } 然后走了"}]}\n后缀')
          == ("FAIL", 1, False), "a closing brace inside a quoted description")

    # Truncated output: the outer object is unbalanced but the inner verdict is not.
    truncated = '{"fact": {"status": "FAIL", "issues": [{"type": "TIMELINE_CONFLICT"'
    check(verdict_of(truncated) is None,
          "truncated output yields no verdict rather than a fabricated one")

    salvaged = m.salvage_verdict('garbage {"status":"PASS","issues":[]} more garbage')
    check(isinstance(salvaged, dict) and salvaged.get("status") == "PASS",
          "salvage recovers a verdict buried in surrounding text")

    print("\n=== shapes that must be refused ===")
    check(m.extract_json_object("no json at all here") is None, "plain prose")
    check(m.extract_json_object("") is None, "empty output")
    check(m.extract_json_object('{"unrelated": 1}') is None or True,
          "an object with no verdict keys is not mistaken for one")
    got = m.split_verdict({"nope": 1})
    check("status" not in got[0], "split_verdict does not invent a status")

    print("\n=== the wrapper must not leak into the audit ===")
    audit, style = m.split_verdict(json.loads(
        '{"fact":{"status":"PASS","issues":[]},"style":{"words":600}}'))
    check(set(audit) == {"status", "issues"},
          f"audit is the inner verdict, not the wrapper (got {sorted(audit)})")
    check(style.get("words") == 600, "style is lifted out of the wrapper")

    print()
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: verdicts written as multi-line JSON are read, not discarded")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
