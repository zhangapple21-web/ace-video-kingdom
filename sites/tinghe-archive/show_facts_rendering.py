#!/usr/bin/env python3
"""Show how build_context_bundle.py renders each facts.json section."""
from __future__ import annotations

import pathlib
import re
import sys

TARGET = pathlib.Path(__file__).resolve().parent / "build_context_bundle.py"
text = TARGET.read_text(encoding="utf-8")
i = text.find("facts_path = SOURCE")
seg = text[i:i + 5200]

print("=== headings emitted from facts.json ===")
for m in re.finditer(r'lines\.append\((["\'])(.*?)\1', seg):
    if "###" in m.group(2) or "事实" in m.group(2):
        print(f"  {m.group(2)}")

print("\n=== section keys read out of facts ===")
for m in re.finditer(r'facts\.get\((["\'])(.*?)\1', seg):
    print(f"  {m.group(2)}")

print("\n=== _rows / render calls ===")
for m in re.finditer(r'^\s*(?:lines\.append\()?_?(?:rows|_rows|_sec)\(([^\n]{0,110})', seg, re.M):
    print(f"  {m.group(1)[:108]}")

print("\n=== the raw block, for reading ===")
print(seg[600:3400])