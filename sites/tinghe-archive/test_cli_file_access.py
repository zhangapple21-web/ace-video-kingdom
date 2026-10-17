#!/usr/bin/env python3
"""Check whether the opencode CLI can actually open the files we hand it.

The audit failed with `File not found: ...\\originals_source\\fanguan\\` — note the
trailing separator, which is what you get when a path is truncated at a byte
boundary. Every path this project passes contains non-ASCII segments
(`D:\\视频创作\\...`), so whether the CLI reads them is a load-bearing assumption,
not a detail. It has to be checked, because a CLI that silently cannot read the
context bundle produces audits with no context at all — which look like verdicts.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent
CLI = pathlib.Path(os.environ.get("USERPROFILE", "")) / ".local" / "bin" / "opencode.exe"
# This file tests whether the CLI can read a bundle, not which model is best, so
# it only needs a model that actually answers. It named muse-spark-1.3, which was
# delisted on 2026-10-17 ("Model unavailable" on 6 of 6 real calls), so all three
# access checks failed as though file access were broken - the test blamed the
# thing it was measuring for a fault in its own fixture.
MODEL = "opencode/mimo-v2.6-flash-free"

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def ask(prompt: str, extra: list[str]) -> tuple[int, str]:
    cmd = [str(CLI), "run", "--model", MODEL, *extra, prompt]
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=240)
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    return p.returncode, ((p.stdout or "") + (p.stderr or ""))


def main() -> int:
    if not CLI.is_file():
        print(f"opencode CLI missing at {CLI}")
        return 2

    bundle = ROOT / "originals_source" / "fanguan" / "context_bundle.md"
    check(bundle.is_file(), f"bundle exists locally: {bundle.name}")
    print(f"  path contains non-ASCII: {not str(ROOT).isascii()}")

    # 1. ASCII path, same content. Isolates "CLI cannot read files" from "CLI
    #    cannot read paths with non-ASCII segments".
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as tf:
        tf.write(bundle.read_text(encoding="utf-8")[:4000])
        ascii_copy = pathlib.Path(tf.name)

    rc, out = ask("只回答：这个文件的第一行标题是什么？不要做别的。",
                  ["--file", str(ascii_copy)])
    answered = any(h in out for h in ("前文上下文包", "fanguan"))
    check(answered, f"CLI reads a file at an ASCII path (exit {rc})")

    # 2. The real non-ASCII path.
    rc, out = ask("只回答：这个文件的第一行标题是什么？不要做别的。",
                  ["--file", str(bundle)])
    answered = any(h in out for h in ("前文上下文包", "fanguan"))
    check(answered, f"CLI reads the real non-ASCII path (exit {rc})")
    if not answered:
        print("  --- last 500 chars of output ---")
        print("  " + out[-500:].replace("\n", "\n  "))

    # 3. Relative path from cwd, which is how the pipeline usually invokes it.
    rel = os.path.relpath(bundle, ROOT)
    rc, out = ask("只回答：这个文件的第一行标题是什么？不要做别的。",
                  ["--file", rel])
    answered = any(h in out for h in ("前文上下文包", "fanguan"))
    check(answered, f"CLI reads it via a relative path (exit {rc})")

    ascii_copy.unlink(missing_ok=True)
    print()
    if failures:
        print(f"FAILED {len(failures)} check(s) — an audit that cannot read the bundle")
        print("is an audit with no context, which is worse than no audit at all.")
        return 1
    print("RESULT: the CLI can read the context bundle at every path form we use")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
