#!/usr/bin/env python3
"""Daily task runner for Windows Task Scheduler.

Runs the full daily pipeline: write today's episodes -> context bundles ->
build/verify/audit/deploy.

The writing step (Gate 0.5) shells out to the opencode CLI with
``DAILY_DIRECTIVE.md``; it is the only thing in this repository that ever adds
an episode. Everything downstream merely projects ``originals_source`` into the
public snapshot and publishes it, so without Gate 0.5 this task can never grow
the catalogue.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tools.atomic_io import atomic_write_text

ROOT = Path(r"D:\视频创作\ace-video-kingdom\sites\tinghe-archive")
LOG = ROOT / "daily_run.log"
DAILY_LOG = ROOT / "daily_log.md"
SOURCE = ROOT / "originals_source"

# The writer is an LLM session writing five episodes; it needs far longer than
# the 300s used for the fast local gates.
WRITE_TIMEOUT = 3600
# A lock older than this is assumed to be left by a crashed run, not a live one.
LOCK_TTL_SECONDS = 6 * 3600


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    line = f"[{ts}] {msg}"
    # Scheduled runs have no console attached and inherit the OEM code page, so
    # echoing a child's Unicode output (emoji, CJK) raised UnicodeEncodeError
    # and aborted the task right after a successful deploy. Never let logging
    # be the thing that fails; the file is the authoritative record anyway.
    try:
        print(line)
    except (UnicodeEncodeError, OSError):
        pass
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd: list[str], label: str, timeout: int = 300) -> tuple[int, str]:
    log(f"=== {label} ===")
    # Child scripts print Chinese. Without errors="replace" a single undecodable
    # byte raises inside subprocess's reader thread, which then discards the
    # whole capture — the run fails with an empty log and no diagnosable cause.
    # Pin the child to UTF-8 and never lose its output.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=ROOT, timeout=timeout, env=env,
    )
    out = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        log(f"[FAIL] {label} (exit {result.returncode})")
        log(out[-2000:] if out.strip() else "(no output captured)")
    else:
        log(f"[OK] {label}")
        log(out[-500:])
    return result.returncode, out


def beat(stage: str) -> None:
    """Heartbeat for forensics: stage + timestamp, best effort.

    If this process is ever killed externally (2026-10-06 died with no trace
    after a verified deploy), the heartbeat shows exactly which stage went
    silent. Never raises.
    """
    try:
        atomic_write_text((ROOT / ".heartbeat"), 
            f"{datetime.now().isoformat(timespec='seconds')} {stage} pid={os.getpid()}\n",
            encoding="utf-8")
    except OSError:
        pass


def append_daily_log(summary: dict) -> None:
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    date_str = datetime.now().date().isoformat()
    line = f"## {date_str} {datetime.now().strftime('%H:%M:%S')}\n"
    line += f"- 作品: {summary.get('new_works', 0)} 新 / {summary.get('total_works', 0)} 总\n"
    line += f"- 集数: +{summary.get('new_episodes', 0)} / {summary.get('total_episodes', 0)} 总\n"
    line += f"- 状态: {summary.get('status', 'UNKNOWN')}\n"
    if summary.get("error"):
        line += f"- 错误: {summary['error']}\n"
    line += "\n"
    with (ROOT / "daily_log.md").open("a", encoding="utf-8") as f:
        f.write(line)


def snapshot_counts() -> tuple[int, int]:
    """Return (works, episodes) currently authored under originals_source."""
    works = episodes = 0
    for work_file in sorted(SOURCE.glob("*/work.json")):
        try:
            data = json.loads(work_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        eps = data.get("episodes") or []
        if eps:
            works += 1
            episodes += len(eps)
    return works, episodes


def write_next_episodes(before: tuple[int, int]) -> tuple[int, str]:
    """Gate 0.5: hand the writing job to the opencode CLI.

    Everything else in this pipeline only projects and publishes what already
    exists in originals_source; nothing here ever writes an episode. Without
    this step the scheduled task can never grow the catalogue, which is what
    happened on 2026-10-05: the run reported "0 new / 0 total" and exited 1
    because no gate can pass on an empty batch.

    Two guards keep this reliable unattended:

    * a lock file, so a second trigger inside the same window cannot launch a
      second writer against the same work.json files;
    * a staleness check, so a writer that exits 0 without having touched any
      work.json is retried once instead of silently producing nothing.
    """
    log("=== Gate 0.5: Write next episodes ===")

    # A lock left behind by a crashed run must not wedge every future day.
    # Anything older than the TTL is treated as stale: logged loudly, then
    # replaced. TTL is deliberately generous (6x the writer timeout).
    lock = ROOT / ".writing.lock"
    if lock.exists():
        stamp = lock.read_text(errors="replace").strip()
        stale = True
        try:
            started = datetime.fromisoformat(stamp.split("started=")[1].split()[0])
            age = (datetime.now() - started).total_seconds()
            stale = age > LOCK_TTL_SECONDS
        except (IndexError, ValueError):
            age = -1
        if not stale:
            message = f"writing lock held by another run ({stamp})"
            log(f"[SKIP] {message}")
            return 0, message
        log(f"[WARN] stale writing lock ({stamp}, age {age:.0f}s) — taking over")
    atomic_write_text(lock, f"pid={os.getpid()} started={datetime.now().isoformat(timespec='seconds')}\n",
                    encoding="utf-8")

    cli = Path(os.environ.get("USERPROFILE", "")) / ".local" / "bin" / "opencode.exe"
    if not cli.is_file():
        message = f"writing CLI missing: {cli}"
        log(f"[FAIL] {message}")
        lock.unlink(missing_ok=True)
        return 1, message

    prompt = ("严格执行附件作战指令，完成今天域外星际原创桌批次，输出末行 JSON 摘要。"
              "动笔前先加载创作者技能 @tinghe-author（创作总纲与去 AI 味军规），逐条执行。")
    if getattr(args, "works", None):
        only = sorted({w.strip() for w in args.works.split(",") if w.strip()})
        prompt += ("本次只写以下作品的新集，其余作品一律不动（含集号、标题、status）："
                   + "、".join(only) + "。")
    if getattr(args, "no_deploy", False):
        # The directive tells the writer to run daily_originals.py itself
        # (which deploys). In a trial run the wrapper owns the gates, so the
        # writer must stop after writing + structural self-check — otherwise a
        # "land only" test would ship through the back door.
        prompt += ("本次为试跑：完成写作与结构校验（build_originals.py、"
                   "verify_originals_batch.py）后即停，不要运行 daily_originals.py，"
                   "不要做任何部署；末行 JSON 摘要照常输出。")
    code = out = ""
    try:
        for attempt in (1, 2):
            code, out = run([str(cli), "run", "--auto",
                             "--file", str(ROOT / "DAILY_DIRECTIVE.md"),
                             "--file", str(ROOT / "DAILY_WRITING_NOTES.md"),
                             prompt],
                            f"opencode_write_next (attempt {attempt})", timeout=WRITE_TIMEOUT)
            after = snapshot_counts()
            added = after[1] - before[1]
            log(f"writing attempt {attempt}: episodes {before[1]} -> {after[1]} (+{added})")
            if added > 0:
                return code, out
            if attempt == 1:
                log("[WARN] writer produced no new episode; retrying once")
    finally:
        lock.unlink(missing_ok=True)
    return code, out


def main() -> int:
    global args
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true",
                        help="skip the writing step and only build/verify/audit/deploy")
    parser.add_argument("--works", default="",
                        help="comma-separated work ids to scope Gate 0.5 to "
                             "(e.g. --works fanguan); empty means all works")
    parser.add_argument("--no-deploy", action="store_true",
                        help="run every gate including build and audit, but stop "
                             "before deploying (for trial runs)")
    args = parser.parse_args()

    log("=== Daily task started ===")
    beat("started")

    works_before, eps_before = snapshot_counts()
    log(f"authored before writing: {works_before} works / {eps_before} episodes")

    # Snapshot the published episode set BEFORE the writer runs anything. The
    # writer self-checks with a real build (directive 4.1), which writes its
    # new episodes into public/ mid-run — so any snapshot taken later (even at
    # the pipeline's Gate 1) already contains them and Gate 3 finds nothing.
    # daily_originals.py consumes this file (and deletes it); without it, it
    # falls back to its own Gate 1 snapshot.
    pub_before = {}
    for work_dir in sorted((ROOT / "public" / "data" / "originals").iterdir()):
        if work_dir.is_dir():
            pub_before[work_dir.name] = sorted(p.stem for p in work_dir.glob("ep*.json"))
    atomic_write_text((ROOT / ".pub_before.json"), 
        json.dumps({"date": datetime.now().date().isoformat(), "works": pub_before},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"published before writing: {sum(len(v) for v in pub_before.values())} episode files")

    summary = {
        "new_works": 0,
        "new_episodes": 0,
        "total_works": 0,
        "total_episodes": 0,
        "status": "OK",
        "error": None,
    }

    try:
        # 1. Generate context bundles for all domain works
        log("=== Gate 0: Context bundles ===")
        for wid in ["fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin"]:
            code, _ = run([sys.executable, "build_context_bundle.py", wid], f"context:{wid}")
            if code != 0:
                raise RuntimeError(f"Context bundle failed for {wid}")

        # 1b. Actually write today's episodes. Skipped with --no-write for
        #     diagnosis, and a writer failure does not abort: publishing what
        #     already exists is still correct, so the run records it and goes on.
        if args.no_write:
            log("=== Gate 0.5: Write next episodes (skipped, --no-write) ===")
        else:
            code, write_out = write_next_episodes((works_before, eps_before))
            if code != 0:
                log("[WARN] writing step failed; continuing to publish existing work")
                summary["write_error"] = (f"writing step exited {code}; "
                                          f"{(write_out or '').strip()[-200:]}")

        beat("bundles-done")

        # 2. Run full pipeline (build/verify/audit/deploy)
        log("=== Gate 1-4: Full pipeline ===")
        beat("writing-done")
        works_after, eps_after = snapshot_counts()
        summary["new_episodes"] = max(0, eps_after - eps_before)
        summary["total_works"] = works_after
        summary["total_episodes"] = eps_after
        log(f"authored after writing: {works_after} works / {eps_after} episodes "
            f"(+{summary['new_episodes']})")

        # A run that writes nothing is not a success. Publishing yesterday's
        # episodes again is still correct, but it must be visible as a stall
        # rather than reported as a normal day — that is exactly how 2026-10-05
        # looked fine for three days while producing no new content.
        if summary["new_episodes"] == 0 and not args.no_write:
            log("[STALL] writer produced no new episode today")
            summary["write_error"] = summary.get(
                "write_error", "writer produced 0 new episodes")

        # Checkpoint: the write-phase record lands in daily_log NOW, not at the
        # end. If this process dies later (2026-10-06), the writing outcome is
        # still on record; the pipeline writes its own deploy-outcome entry.
        # Diagnostic runs (--no-write) stay out of the log.
        if not args.no_write:
            with (ROOT / "daily_log.md").open("a", encoding="utf-8") as f:
                f.write(f"## {datetime.now().date().isoformat()} {datetime.now().strftime('%H:%M:%S')}\n")
                f.write(f"- 阶段: 写作（门禁 0–0.5）\n")
                f.write(f"- 集数: +{summary.get('new_episodes', 0)} / {summary.get('total_episodes', 0)} 总\n")
                if summary.get("write_error"):
                    f.write(f"- 写作: {summary['write_error']}\n")
                f.write("\n")

        # Gate 3 now really audits (it used to compare the build against
        # itself and skip). Five episodes at up to 600s each plus the gates
        # needs well over the 300s default, so give the pipeline its own hour.
        pipe_cmd = [sys.executable, "daily_originals.py"]
        if args.no_deploy:
            pipe_cmd.append("--no-deploy")
            log("deploy suppressed by --no-deploy (trial run, nothing will ship)")
        code, out = run(pipe_cmd, "daily_originals.py", timeout=3600)
        if code == 0:
            # Post-deploy teardown (promote, daily_log, receipt) lives inside
            # daily_originals now, so a wrapper death cannot strand a verified
            # deploy without records (2026-10-06).
            summary["status"] = "GATES_OK" if args.no_deploy else "DEPLOYED"
            beat("pipeline-done")
        elif code == 1:
            summary["status"] = "BUILD_FAILED"
        elif code == 2:
            summary["status"] = "AUDIT_FAILED"
        elif code == 3:
            summary["status"] = "DEPLOY_FAILED"
        else:
            summary["status"] = f"UNKNOWN_EXIT_{code}"

        # Parse counts from output. The counts measured from disk above are
        # authoritative and already in the summary, so this only refines the
        # new-episode figure; nothing here may overwrite a known total with a
        # value it failed to parse. (Receipt/style lines are owned by the
        # pipeline's own daily_log entry now; the wrapper no longer records them.)
        for line in out.splitlines():
            if "New episodes to audit:" in line:
                try:
                    summary["new_episodes"] = int(line.split(":")[1].strip().split()[0])
                except Exception:
                    pass
            if "deploy_pending:  false" in line:
                summary["status"] = "DEPLOYED"

    except Exception as exc:
        # Early failure (before or around the pipeline): the pipeline never got
        # to write its own record, so the wrapper records the failure here.
        summary["status"] = "EXCEPTION"
        summary["error"] = str(exc)
        log(f"[EXCEPTION] {exc}")
        with (ROOT / "daily_log.md").open("a", encoding="utf-8") as f:
            f.write(f"## {datetime.now().date().isoformat()} {datetime.now().strftime('%H:%M:%S')}\n")
            f.write(f"- 阶段: 异常中断\n")
            f.write(f"- 状态: EXCEPTION\n")
            f.write(f"- 错误: {summary['error']}\n\n")
        return 1

    finally:
        # Marker only. Per-stage records already landed (write-phase checkpoint
        # above, pipeline outcome inside daily_originals), so even if this
        # process is killed right here, nothing of record is lost.
        log("=== Daily task finished ===")

    return 0 if summary["status"] in ("DEPLOYED", "GATES_OK") else 1


if __name__ == "__main__":
    sys.exit(main())