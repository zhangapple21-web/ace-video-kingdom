"""Find every UTF-8 BOM this session's PowerShell edits left behind.

Editing source through the shell added a BOM in front of the shebang of
build_entry_covers.py, and the deploy gate caught the same thing in
public/index.html. Both came from the same command shape:

    (Get-Content f -Raw) -replace a,b | Set-Content f -Encoding UTF8

Windows PowerShell writes UTF-8 with a BOM. Python tolerates a BOM in a source
file only at the very start, and an HTML file carrying one is a defect the site
integrity check refuses to deploy past.

So this is not a one-file fix: anything touched that way needs checking. Scans
every tracked source and built file under the project and reports the offenders,
so the next deploy is not stopped by the second one.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
BOM = b"\xef\xbb\xbf"
SCAN_SUFFIXES = {".py", ".html", ".css", ".js", ".json", ".md"}

SKIP = {".git", ".public_snapshots", "__pycache__", ".venv", "node_modules",
        "backup_rewrite", ".wrangler"}

found: list[tuple[str, str]] = []
scanned = 0

for p in ROOT.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in SCAN_SUFFIXES:
        continue
    if any(part in SKIP for part in p.parts):
        continue
    try:
        head = p.open("rb").read(3)
    except OSError:
        continue
    scanned += 1
    if head == BOM:
        found.append((p.relative_to(ROOT).as_posix(),
                      p.open("rb").read(40).decode("utf-8", "replace")))

print(f"scanned {scanned} files under {ROOT.name}/")
print(f"BOM found: {len(found)}\n")
for rel, head in found:
    print(f"  {rel}")
    print(f"      {head!r}")

if not found:
    print("no BOM anywhere")
    sys.exit(0)

# Strip them. Only the BOM — never rewrite the body, so line endings and
# content are left exactly as they were.
for rel, _ in found:
    p = ROOT / rel
    raw = p.read_bytes()
    if raw.startswith(BOM):
        p.write_bytes(raw[len(BOM):])
        print(f"  stripped: {rel}")

# Re-verify from disk.
left = [rel for rel, _ in found if (ROOT / rel).read_bytes()[:3] == BOM]
print()
print("remaining:", left or "none")
sys.exit(1 if left else 0)