#!/usr/bin/env python3
"""Assert the bundle never prints a fact record as a Python dict literal.

Two separate defects reached the bundle the writer reads, both found on
2026-10-11 and neither caught by anything:

  - 未回收钩子：{'hook': '四楼眉批主人是谁（ep08 …）'}
  - [?] {'entry': '回执背面第二行已兑现…'}

Ten hooks and all 65 pending entries were affected. The cause in both places was
the same: facts.json is hand-edited and the author model was never told which
shape to write, so records arrive as a bare string, as {"hook": ...}, as
{"fact": ...}, or wrapped one level deeper as {"entry": {...}} — and the renderer
formatted the record itself rather than the text inside it.

This uses constructed records, not production data. A test that reads the live
facts rots the moment someone fixes a typo in one, which has already happened
three times in this project (test_repair_routing, check_audit_evidence,
test_connective_gate). Every shape below is one that appears in the real files,
so the test still covers what actually breaks.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bcb", HERE / "build_context_bundle.py")
bcb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bcb)

# A rendered fact record is always a bullet line, which is the only place this
# ever went wrong: "- 未回收钩子：{'hook': …}" and "- [?] {'entry': …}". Restricting
# to bullet lines matters because the pressure-axis template block legitimately
# contains JSON like {"arc": 2, "opponent": "谁在压她", …} and is not a record.
DICT_LITERAL = re.compile(r"^[-*]\s.*\{['\"][^}]{0,120}['\"]\s*:", re.M)

FACTS = {
    "work": "demo",
    "note": "constructed for the rendering test",
    "open_hooks": [
        "裸字符串钩子",
        {"hook": "字典形钩子", "source": "ep02"},
        {"entry": {"hook": "双层包裹钩子", "source": "ep03"}},
    ],
    "pending": [
        {"fact": "fact 键的待确认事实", "source": "ep01", "awaiting": "ep02"},
        {"entry": "entry 键的待确认事实", "source": "ep01", "awaiting": "ep02"},
        {"hook": "hook 键的待确认钩子", "source": "ep01", "awaiting": "ep02"},
        {"section": "props", "item": "封签箱", "holder": "白鲛",
         "awaiting": "ep02"},
    ],
}

EPISODE = {
    "id": "ep01", "no": 1, "title": "第01集 构造",
    "html": "<p>构造用途的一集，用来让 bundle 有位可写。</p>",
}

failures: list[str] = []
root = pathlib.Path(tempfile.mkdtemp(prefix="bundle-render-"))
try:
    src = root / "originals_source" / "demo"
    pub = root / "public" / "data" / "originals" / "demo"
    src.mkdir(parents=True)
    pub.mkdir(parents=True)
    (src / "facts.json").write_text(
        json.dumps(FACTS, ensure_ascii=False, indent=2), encoding="utf-8")
    (pub / "ep01.json").write_text(
        json.dumps(EPISODE, ensure_ascii=False, indent=2), encoding="utf-8")

    bcb.SOURCE = root / "originals_source"
    bcb.PUBLIC_ORIGINALS = root / "public" / "data" / "originals"

    path = bcb.build_context_bundle("demo")
    if path is None or not path.is_file():
        print("FAIL: bundle was not written")
        sys.exit(1)
    text = path.read_text(encoding="utf-8")

    literals = DICT_LITERAL.findall(text)
    if literals:
        for line in text.splitlines():
            if DICT_LITERAL.search(line):
                failures.append(f"dict literal in bundle: {line.strip()[:120]}")

    for needle in ("裸字符串钩子", "字典形钩子", "双层包裹钩子",
                   "fact 键的待确认事实", "entry 键的待确认事实",
                   "hook 键的待确认钩子"):
        if needle not in text:
            failures.append(f"text missing from bundle: {needle}")

    if "None" in text.replace("NoneType", ""):
        # The first version of the hook loop fed bare strings to a helper that
        # returns None for non-dicts and rendered five "- None" bullets.
        if re.search(r"^-\s*None\s*$", text, re.M):
            failures.append("bundle contains a bare '- None' bullet")

    if "（来自 ep02）" not in text:
        failures.append("hook source suffix not rendered")
finally:
    shutil.rmtree(root, ignore_errors=True)

print(f"checks: 4 shapes of hook, 4 shapes of pending, no dict literals"
      f" (literal matches: {len(literals)})")
print()
if failures:
    print(f"FAILED {len(failures)} check(s):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("RESULT: every fact record renders as text, never as a Python dict")
