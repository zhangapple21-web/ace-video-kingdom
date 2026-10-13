#!/usr/bin/env python3
"""Flatten open_hooks records and prove no dict literal survives into a bundle.

Two problems, one fix.

First, facts.json is hand-edited and hooks arrive in three shapes — a bare string,
{"hook": ..., "source": ...}, and a {"entry": {...}} nested wrapper. build_context_
bundle formatted the record straight into an f-string, so the bundle the writer
reads contained Python dict literals:

    - 未回收钩子：{'hook': '四楼眉批主人是谁（ep08 …）'}
    - 未回收钩子：{'entry': {'hook': '回执背面第二行…'}}

Ten of them across the five works. The nested one is the same hand-edit accident
that killed the daily publish on 2026-10-07 in the pressure section; that path got
a guard, this one did not.

Second, the hooks were phrased entirely as questions ("who is X", "are these the
same"), which is the pull that turned the series from winning-and-being-pressed-
harder into investigating. The rendering now labels them as leverage rather than
as the episode's task, but the wording is the writer's to keep.

This flattens the stored records, then re-reads every generated bundle and fails if
a brace-quoted dict literal is still present. A mechanical check on generated
artefacts, not a judgement about prose.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
WORKS = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")

# Any rendered Python dict literal inside a bundle. The first version of this
# check only looked at lines starting "未回收钩子：" and therefore missed the
# entire pending section, which was also full of them.
DICT_LITERAL = re.compile(r"\{['\"][^}]{0,80}['\"]:")


def flatten(rec, depth: int = 0):
    """Unwrap nested {"entry": {...}} wrappers, deepest first."""
    if not isinstance(rec, dict) or depth > 4:
        return rec
    if isinstance(rec.get("entry"), dict):
        merged = dict(rec["entry"])
        merged.update({k: v for k, v in rec.items() if k != "entry"})
        return flatten(merged, depth + 1)
    return rec


def main() -> int:
    changed = 0
    for wid in WORKS:
        p = SOURCE / wid / "facts.json"
        if not p.is_file():
            continue
        facts = json.loads(p.read_text(encoding="utf-8-sig"))
        hooks = facts.get("open_hooks")
        if not isinstance(hooks, list):
            continue
        new = [flatten(h) for h in hooks]
        if new != hooks:
            facts["open_hooks"] = new
            p.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
            changed += 1
            print(f"[FIXED] {wid}: unwrapped open_hooks")

    print(f"\nflattened {changed} file(s); rebuilding bundles")
    import subprocess
    for wid in WORKS:
        r = subprocess.run([sys.executable, str(HERE / "build_context_bundle.py"), wid],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            print(f"[FAIL] bundle {wid}: {r.stderr.strip()[:120]}")
            return 1

    bad = 0
    for wid in WORKS:
        bp = SOURCE / wid / "context_bundle.md"
        if not bp.is_file():
            continue
        text = bp.read_text(encoding="utf-8")
        hits = DICT_LITERAL.findall(text)
        n = len(hits)
        bad += n
        print(f"  {wid:<12} 字典字面量残留 {n}")
        if n:
            for line in text.splitlines():
                if DICT_LITERAL.search(line):
                    print(f"      !! {line[:110]}")
    print()
    if bad:
        print(f"[FAIL] {bad} 处字典字面量仍在上下文包里")
        return 1
    print("[PASS] 五部上下文包内不再有字典字面量")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
