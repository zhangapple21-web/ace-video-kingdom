#!/usr/bin/env python3
"""Terminate the model and everything it spawned, not just the child.

`opencode run` forks. The direct child is the CLI; the pair of python processes
underneath it outlive it. Every termination path here called proc.kill() or
proc.terminate(), which reach only the direct child, so each abandoned attempt
left two orphans behind.

Twenty-two of them were found on 2026-10-10 at 21:00, the oldest nine hours old,
holding 166 MB. The prompt files were cleaned up, so they looked harmless — but an
orphaned `opencode run` was invoked with a prompt whose instruction is to edit
work.json, and nothing was holding it back from doing so.

taskkill /T walks the tree. Each call site already has a live child, which is the
case taskkill needs: once the direct child exits there is no tree left to walk,
and that is exactly why the orphans survived.

Idempotent.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE / "repair_episodes.py"

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


KILL_TREE = '''def kill_tree(pid: int) -> None:
    """Kill a process and everything it spawned.

    `opencode run` forks: the direct child is the CLI, and the python pair beneath
    it outlives it. Killing only the direct child has left those orphaned — 22 of
    them were alive on 2026-10-10 at 21:00, the oldest nine hours old, holding
    166 MB. Each was launched with a prompt instructing it to edit work.json, and
    nothing was stopping it.

    taskkill /T walks the tree on Windows. There is no tree walk available on the
    other platforms this runs on, so the caller's own kill remains the fallback.
    A process that has already exited yields a non-zero status and no harm.
    """
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=30)
        except (subprocess.TimeoutExpired, OSError):
            pass


'''

ANCHOR = "def run_model("

REPLACEMENTS = [
    # timeout path
    ('                    proc.kill()\n'
     '                    log(f"    model exceeded {timeout}s; killed")',
     '                    kill_tree(proc.pid)\n'
     '                    log(f"    model exceeded {timeout}s; killed with its children")'),
    # no-progress path
    ('                    proc.kill()\n'
     '                    log(f"    model wrote nothing in {NO_PROGRESS_SECONDS}s; killed")',
     '                    kill_tree(proc.pid)\n'
     '                    log(f"    model wrote nothing in {NO_PROGRESS_SECONDS}s; '
     'killed with its children")'),
    # quiet-period path: the child is still alive here, which is the case that
    # matters — taskkill can still walk the tree.
    ('                    proc.terminate()\n'
     '                    try:\n'
     '                        proc.wait(timeout=30)\n'
     '                    except subprocess.TimeoutExpired:\n'
     '                        proc.kill()\n'
     '                    log(f"    model finished its edit but did not exit; terminated "\n'
     '                        f"after {int(time.time() - started)}s")',
     '                    kill_tree(proc.pid)\n'
     '                    try:\n'
     '                        proc.wait(timeout=30)\n'
     '                    except subprocess.TimeoutExpired:\n'
     '                        proc.kill()\n'
     '                    log(f"    model finished its edit but did not exit; terminated "\n'
     '                        f"with its children after {int(time.time() - started)}s")'),
    # final wait fallback
    ('            except subprocess.TimeoutExpired:\n'
     '                proc.kill()\n'
     '                code = 0',
     '            except subprocess.TimeoutExpired:\n'
     '                kill_tree(proc.pid)\n'
     '                code = 0'),
]


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if "def kill_tree(" in text:
        print("already patched")
        return 0

    check(ANCHOR in text, "found the run_model anchor")
    if ANCHOR not in text:
        return 1
    text = text.replace(ANCHOR, KILL_TREE + ANCHOR, 1)

    for old, new in REPLACEMENTS:
        check(old in text, f"found termination site: {old.strip().splitlines()[-1][:52]}")
        if old not in text:
            return 1
        text = text.replace(old, new, 1)

    TARGET.write_text(text, encoding="utf-8")
    print("\npatched")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())