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
import time
from datetime import datetime, timezone
from pathlib import Path
from tools.atomic_io import atomic_write_text

ROOT = Path(r"D:\视频创作\ace-video-kingdom\sites\tinghe-archive")
LOG = ROOT / "daily_run.log"
DAILY_LOG = ROOT / "daily_log.md"
SOURCE = ROOT / "originals_source"

# The writer is an LLM session writing five episodes; it needs far longer than
# the 300s used for the fast local gates. Bounded per model rather than per run
# so that rotating the pool cannot multiply into an unbounded day: a throttled
# model fails in seconds, so the only model that can actually consume this budget
# is one that hangs. 6 models x 1800s x 2 passes = 6h worst case, which fits
# inside the task's 12h ExecutionTimeLimit with room for the publish gates.
# Before model rotation this was 3600s for a single pinned model, and on
# 2026-10-06 that one model ran 6h11m and got the run killed mid-publish.
WRITE_TIMEOUT = 1800
# A lock older than this is assumed to be left by a crashed run, not a live one.
LOCK_TTL_SECONDS = 6 * 3600

# Why the writing step declined to run, if it did. Module-level because the writer
# returns early from a helper; the reason then travels into the receipt, so a skipped
# day is visible in the record rather than only in the log.
WRITER_SKIP_REASONS: list[str] = []
# Once the episode count has moved we still let the CLI try to exit on its own,
# because it may be mid-way through its own structural self-check. Past this
# grace period it is terminated: the work is already on disk, and on 2026-10-07
# waiting for a clean exit is what held the lock for the rest of the day.
WRITER_EXIT_GRACE = 180


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
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=ROOT, timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired as expired:
        # Must be caught here. An uncaught timeout tears down the whole daily
        # run, and because publishing happens *after* the writer in this
        # process, episodes the writer already finished would never ship. That
        # is exactly what happened on 2026-10-06: the writer ran past its
        # 3600s budget, the exception escaped, and the 6h task limit killed the
        # run before Gate 1-4 — only the separate stale-watch task rescued the
        # publish. A slow step is a failed step, not a reason to drop finished
        # work on the floor.
        #
        # Note this is also not a *reliable* kill: a child that spawns
        # grandchildren inheriting stdout/stderr keeps the pipes open, so
        # subprocess.run can block past its own timeout. Treat this branch as
        # "we noticed and moved on", not as a guarantee the child is gone.
        message = (f"timeout after {timeout}s "
                   f"(stdout {(expired.stdout or b'')!r:.200} "
                   f"stderr {(expired.stderr or b'')!r:.200})")
        log(f"[TIMEOUT] {label}: {message}")
        return 124, message
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


# Ordered pool of free models the writer may use. Never pin one: on 2026-10-06 a
# single default model ran 6h11m and got the whole task killed, and every earlier
# rate-limit simply stalled the day. Ordering is by measured fitness for THIS job —
# writing Chinese short-drama episodes against ~20KB context bundles — not by vibes.
#
# Muse Spark 1.3 leads because it earned it twice: its family (Muse Spark 1.1)
# ranks highest among affordable models on EQ-Bench Creative Writing, and on
# 2026-10-08 it wrote a valid 1058-word episode with correct block structure in
# 40s against the project's own benchmark task (bench_models.py). The old order
# put it fourth behind an unmeasured "heavy/long-context first" guess.
#
# nemotron-3-ultra is OUT of the prose pool: the same benchmark measured 450
# words in 46s — half the floor — which is what a logic model does to long prose.
# It stays in the AUDIT pool, where logic is the job. longcat-2.5-preview sits
# last on one failed sample (420s, no valid JSON); a second failure quarantines
# it out of the main flow rather than letting it burn a timeout window each run.
#
# fledge-alpha-free was REMOVED on 2026-10-09: the provider delisted it, so
# `opencode models` no longer lists it and every run wastes a slot on
# "Model unavailable". Verify the pool whenever it is edited — probe_pool_health.py
# answers "is this slot still real?" in seconds instead of a failed run a day later.
#
# step-5-preview-free and ling-3.1-flash-free were REMOVED on 2026-10-16 by the
# same rule as fledge. probe_pool_health.py reports both [DEAD] with
# "[not listed]" and "Model unavailable"; neither appears anywhere in the 139
# models `opencode models` returns, and neither produces the regional signature
# described below. That distinguishes them from muse-spark-1.3 (kept): a
# delisting removes the entry, a region change only needs a re-probe, and the
# two look alike from a single sample.
#
# Cost of leaving them: each is tried once per episode at a 120s timeout, so two
# dead slots burn 240s of a run that already shares its budget with five audits.
# test_writer_pool.py pinned this: the pool must only name models the provider
# still offers.
#
# 2026-10-13 探测后重排。
#
# 关于 muse-spark-1.3 的更正：13:13 探测报
# "This model is not available in your country"，我据此把它当成被提供商按地区
# 下架、永久移出了池子。**这是错的** —— 用户测试下来，那是他临时切到香港地区
# 导致的，恢复原地区后立刻可用。地区/出口变化会伪装成"模型被下架"，而这两种
# 情况的处置相反：下架要移除，换个地区只要重探一次。
#
# 所以下面这一行保留，并在每次跑批前用 probe_pools.py 复测；探到不可用时，
# 用 --models 临时指定别的，不要从池里删。
#
# 顺序按"真跑过一整集"的实测排，不按探测排：2026-10-13 修 fanguan/ep11 时，
# step-5 与 ling 各跑满 480s 一个字没写出来，mimo 160s 改完并直接 audit PASS。
# （step-5 与 ling 已于 2026-10-16 因下架移除，见上；这次实测是它们当时仍在
#  池内的排序依据，保留作为"顺序按实测排"的出处。）
#
# Override without editing code:
#   set TINGHE_WRITER_MODELS=opencode/nemotron-3.5-lightning-free,opencode/amd-model
WRITER_MODELS = [
    "opencode/mimo-v2.6-flash-free",
    "opencode/nemotron-3.5-lightning-free",
    "opencode/longcat-2.5-preview-free",
]

# Signatures that mean "this model is temporarily unavailable", not "the writing
# failed". Matched case-insensitively against the captured output.
#
# "not available in your country" is NOT a rate limit — it is a permanent
# regional delisting — but it belongs in this list because the handling is
# identical: stop wasting attempts on this model and move to the next. Leaving
# it out is what let a dead model sit at position 1 and burn an attempt on
# every episode before anything noticed (2026-10-12/13).
RATE_LIMIT_PATTERNS = (
    "rate limit",
    "rate_limit",
    "too many requests",
    "429",
    "quota exceeded",
    "quota exhausted",
    "resource_exhausted",
    "overloaded",
    "try again later",
    "no available model",
    "not available in your country",
    "model not found",
    "usage limit exceeded",
    # Chinese terms are error phrases only, never the bare words: these patterns
    # run against model output that is mostly Chinese prose, and 额度/配额 on
    # their own appear in ordinary dialogue ("读者额度排行榜"). Bare words would
    # make the daily writer treat a story line as a dead pool and skip the run.
    "限流",
    "请求过快",
    "超出配额",
    "配额已用完",
    "额度已用尽",
    "请稍后重试",
)


def _pid_alive(pid: int) -> bool | None:
    """Is this pid still running? None when the platform will not say.

    On Windows a handle-based check is authoritative; os.kill(pid, 0) is not
    available, and psutil is not a dependency of this pipeline. A None answer
    must fall back to the age heuristic rather than be treated as "dead".
    """
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
            ).stdout or ""
        except Exception:
            return None
        if not out.strip():
            return None
        return f'"{pid}"' in out
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except Exception:
        return None


def writer_models() -> list[str]:
    """Model pool for the writer, honouring the TINGHE_WRITER_MODELS override."""
    override = os.environ.get("TINGHE_WRITER_MODELS", "").strip()
    if not override:
        return list(WRITER_MODELS)
    models = [m.strip() for m in override.split(",") if m.strip()]
    return models or list(WRITER_MODELS)


def looks_rate_limited(output: str) -> bool:
    """True when the failure looks like throttling rather than a writing problem."""
    low = (output or "").lower()
    return any(pattern in low for pattern in RATE_LIMIT_PATTERNS)


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


def discover_work_ids() -> list[str]:
    """Every work id that has a readable work.json with at least one episode.

    Read from disk instead of a hardcoded list so a newly created work is picked
    up on the next run without anyone editing this file.
    """
    ids: list[str] = []
    for work_file in sorted(SOURCE.glob("*/work.json")):
        try:
            data = json.loads(work_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("episodes"):
            ids.append(data.get("id") or work_file.parent.name)
    return ids


def _run_writer_model(cli: Path, model: str, prompt: str,
                      before: tuple[int, int]) -> tuple[int, str, bool]:
    """Run one writer model and return (code, output, throttled).

    Deliberately does NOT wait for the process to exit. On 2026-10-07 the CLI
    wrote its episode and then hung: the python wrapper sat at 0s CPU and the
    opencode child at 5s, still holding the lock 16 minutes later. The 2026-10-06
    run — 6h11m, killed by the task limit before it could publish — was the same
    hang at larger scale. "Wait for exit" is therefore the wrong completion
    signal; the only trustworthy one is that the episode count moved.

    So: launch detached, watch the tree for growth, and once the work is visibly
    done give the CLI a short grace period to exit on its own before terminating
    it. A model that never produces anything is cut off at WRITE_TIMEOUT and
    reported as a failure, which is what lets the pool rotate.
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    cmd = [str(cli), "run", "--auto",
           "--model", model,
           "--file", str(ROOT / "DAILY_DIRECTIVE.md"),
           "--file", str(ROOT / "DAILY_WRITING_NOTES.md"),
           prompt]
    log(f"=== opencode_write_next [{model}] ===")
    started = time.time()
    # Output goes to files, not pipes. With PIPE, terminating a writer whose
    # grandchildren still hold the handles makes communicate() block until its
    # own timeout — which is how a 10s budget turned into 30s. A file cannot be
    # "still open by a child": whatever was written is always readable.
    out_file = open(ROOT / f".writer_out_{os.getpid()}.log", "w+", encoding="utf-8")
    err_file = open(ROOT / f".writer_err_{os.getpid()}.log", "w+", encoding="utf-8")
    try:
        try:
            proc = subprocess.Popen(
                cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                stdout=out_file, stderr=err_file,
            )
        except Exception as exc:
            return 1, f"failed to launch writer: {exc}", False

        def collected() -> str:
            out_file.flush()
            err_file.flush()
            try:
                out_file.seek(0)
                err_file.seek(0)
                return (out_file.read() + err_file.read())[-4000:]
            except Exception:
                return ""

        grace_deadline: float | None = None
        try:
            while True:
                if proc.poll() is not None:
                    out = collected()
                    # Exiting cleanly is not the same as doing the job. If the
                    # tree did not grow, report a failure so the caller cannot
                    # read a silent no-op as success — that is what made
                    # 2026-10-07 look like a normal run for three days.
                    if snapshot_counts()[1] - before[1] <= 0:
                        return proc.returncode or 3, out, looks_rate_limited(out)
                    return proc.returncode, out, looks_rate_limited(out)
                # Work is visible in the tree, not in the exit code.
                current = snapshot_counts()[1]
                added = current - before[1]
                if added > 0 and grace_deadline is None:
                    grace_deadline = time.time() + WRITER_EXIT_GRACE
                    log(f"{model} produced {added} episode(s); "
                        f"allowing {WRITER_EXIT_GRACE}s for a clean exit")
                if grace_deadline is not None and time.time() > grace_deadline:
                    log(f"{model} finished its work but did not exit; terminating it")
                    _terminate(proc)
                    return 0, collected(), False
                if time.time() - started > WRITE_TIMEOUT:
                    out = collected()
                    log(f"[TIMEOUT] {model} exceeded {WRITE_TIMEOUT}s without producing")
                    _terminate(proc)
                    return 124, out, looks_rate_limited(out)
                time.sleep(5)
        finally:
            if proc.poll() is None:
                _terminate(proc)
    finally:
        out_file.close()
        err_file.close()
        # These are diagnostics, not records. Keep the most recent pair so a
        # failed run can still be inspected, and never let them pile up.
        try:
            for pattern in (".writer_out_*.log", ".writer_err_*.log"):
                stale = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime)
                for path in stale[:-2]:
                    path.unlink(missing_ok=True)
        except OSError:
            pass


def _terminate(proc) -> None:
    """Stop the writer and anything it spawned, then reap it.

    "Anything it spawned" used to be a claim rather than a fact: proc.terminate()
    and proc.kill() reach only the direct child, and `opencode run` forks a pair
    of python processes beneath the CLI that outlive it. Every terminated writer
    left two orphans, and test_writer_completion leaves two more behind each run
    by the same route.

    kill_tree walks the process tree on Windows; the per-process kill stays as
    the fallback for platforms without a tree walk.
    """
    from repair_episodes import kill_tree

    for killer in (lambda: kill_tree(proc.pid), proc.terminate, proc.kill):
        try:
            killer()
            proc.wait(timeout=15)
            return
        except Exception:
            continue


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
    # Liveness is checked by pid, not only by age: on 2026-10-07 a completed run
    # left the lock behind while its interpreter was still shutting down, and an
    # age-only check made the 14:00 catch-up task believe a writer was active and
    # skip itself — the exact day it existed to rescue. A dead pid is proof the
    # lock is stale regardless of how young it is; the TTL stays as a backstop for
    # pids we cannot inspect (different session, permissions).
    lock = ROOT / ".writing.lock"
    if lock.exists():
        stamp = lock.read_text(errors="replace").strip()
        age = -1
        owner_alive = None
        try:
            started = datetime.fromisoformat(stamp.split("started=")[1].split()[0])
            age = (datetime.now() - started).total_seconds()
        except (IndexError, ValueError):
            pass
        try:
            owner = int(stamp.split("pid=")[1].split()[0])
            owner_alive = _pid_alive(owner)
        except (IndexError, ValueError):
            owner = None
        if owner_alive is False:
            log(f"[WARN] writing lock owner pid={owner} is gone ({stamp}) — taking over")
        elif age > LOCK_TTL_SECONDS:
            log(f"[WARN] stale writing lock ({stamp}, age {age:.0f}s) — taking over")
        else:
            message = f"writing lock held by another run ({stamp})"
            log(f"[SKIP] {message}")
            # Carried into the receipt. A skip is precisely how a day ships nothing
            # while every gate passes, so the reason belongs in the record and not
            # only in the log — on 2026-10-08 this line was the whole explanation.
            WRITER_SKIP_REASONS.append(message)
            return 0, message
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
    models = writer_models()
    log(f"writer model pool ({len(models)}): {', '.join(models)}")
    try:
        for attempt in (1, 2):
            for model in models:
                code, out, throttled = _run_writer_model(cli, model, prompt, before)
                after = snapshot_counts()
                added = after[1] - before[1]
                log(f"writing with {model}: episodes {before[1]} -> {after[1]} (+{added})")
                if added > 0:
                    log(f"wrote {added} episode(s) via {model}")
                    return code, out
                # Throttled means this model is out of budget right now, not that
                # the writing failed. Move to the next one instead of burning the
                # whole day re-running the same throttled model.
                if throttled:
                    log(f"[RATE-LIMITED] {model} throttled; switching to next model")
                    continue
                log(f"[WARN] {model} produced no episode and was not rate limited")
                break
            if attempt == 1:
                log("[WARN] whole model pool produced nothing; one more pass")
    finally:
        lock.unlink(missing_ok=True)
    return code, out


def write_run_receipt(summary: dict) -> None:
    """Append a per-run receipt keyed by date, so "did today succeed?" has an answer.

    The staleness watchdog used to infer success from the live episode total
    going up. On 2026-10-07 that reported `[OK] grew 79 -> 80` at 09:00 while the
    08:00 run had crashed in Gate 0 and produced nothing — the +1 was the
    previous day's leftover trickling in. Inferring a day's outcome from a
    running total cannot tell today's work from yesterday's residue.

    A receipt states what this run did. It is written from `finally`, so an early
    exception still records a failure, and a later successful catch-up
    supersedes an earlier failure for the same date because the last entry wins.
    That turns "is today done?" into a lookup instead of an inference.
    """
    try:
        eps_after = snapshot_counts()[1]
    except Exception:
        eps_after = summary.get("total_episodes")
    now = datetime.now(timezone.utc).astimezone()
    status = summary.get("status", "UNKNOWN")
    # A deployed snapshot is not the same as a delivered update. On 2026-10-08 the
    # 08:00 run skipped writing (a lock left behind by a crashed repair) and the
    # receipt still said `DEPLOYED, ok: true` while the log said "writer produced no
    # new episode today". That is the 2026-10-03..05 failure mode wearing a green
    # receipt: the reader is told the day succeeded while nothing new shipped.
    #
    # So `ok` is about the deliverable, not the exit status. A full run that wrote
    # nothing is recorded as a stall even though every gate passed.
    mode = ("no-write" if getattr(args, "no_write", False)
            else "catchup" if getattr(args, "only_if_stale", False)
            else "full")
    produced = summary.get("writer_episodes_added")
    if produced is None:
        produced = eps_after - (summary.get("eps_authored_before") or eps_after)
    stalled = mode == "full" and produced <= 0
    receipt = {
        "date": now.date().isoformat(),
        "finished_at": now.isoformat(timespec="seconds"),
        "status": status,
        "ok": status in ("DEPLOYED", "GATES_OK") and not stalled,
        "stalled": stalled,
        "delivered_episodes": produced,
        "mode": mode,
        "eps_authored_before": summary.get("eps_authored_before"),
        "eps_authored_after": eps_after,
        "new_episodes": summary.get("new_episodes"),
        "writer_skip_reason": summary.get("writer_skip_reason")
                              or ("; ".join(WRITER_SKIP_REASONS) or None),
        "error": summary.get("error"),
    }
    path = ROOT / "daily_receipts.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    log(f"[receipt] {receipt['date']} {receipt['mode']} -> {status} "
        f"({'ok' if receipt['ok'] else 'FAILED'})")


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
    parser.add_argument("--only-if-stale", action="store_true",
                        help="exit early unless today genuinely has no new content; "
                             "used by the afternoon catch-up task so a healthy "
                             "morning is never written twice")
    args = parser.parse_args()

    log("=== Daily task started ===")
    beat("started")

    works_before, eps_before = snapshot_counts()
    log(f"authored before writing: {works_before} works / {eps_before} episodes")

    # Catch-up guard. The afternoon task exists to recover a morning that
    # produced nothing; without this check it would also write on top of a
    # morning that already succeeded, doubling the daily output on healthy days.
    # Ask the status file, not a guess — it is derived from episode counts.
    if args.only_if_stale:
        code, out = run([sys.executable, "desk_status.py", "--check-only"],
                        "desk_status_probe", timeout=120)
        try:
            state = json.loads(out).get("state") if code == 0 else None
        except Exception:
            state = None
        # PENDING_PUBLISH means episodes are authored but the reader cannot open
        # them. That is precisely when the catch-up is needed, and it used to be
        # listed as a reason to skip — so a blocked deploy was never retried and
        # the day ended with written-but-invisible content. Only a day already
        # published today is genuinely done.
        if state == "UPDATED_TODAY":
            log(f"[SKIP] catch-up not needed: status={state}")
            return 0
        if state == "PENDING_PUBLISH":
            # Publish what is written; do not write again.
            args.no_write = True
            log("[CATCH-UP] content is written but not live — publishing without writing")
        else:
            log(f"[CATCH-UP] proceeding: status={state or 'UNKNOWN'}")

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
        "eps_authored_before": eps_before,
        "works_authored_before": works_before,
        "status": "OK",
        "error": None,
    }

    try:
        # 1. Generate context bundles for every authored work.
        #    Discovered from originals_source/*/work.json, never a hardcoded list:
        #    a new work must not be silently skipped because nobody edited this file.
        #    A malformed bundle is recorded and skipped, NOT fatal — the bundles
        #    feed the writer and the audit, they do not decide whether already
        #    authored, already audited episodes may ship. liufang/facts.json had one
        #    stray {"entry": {...}} wrapper on 2026-10-07 and that single typo
        #    aborted the whole day's publish (nothing shipped that morning).
        log("=== Gate 0: Context bundles ===")
        bundle_errors = []
        for wid in discover_work_ids():
            code, _ = run([sys.executable, "build_context_bundle.py", wid], f"context:{wid}")
            if code != 0:
                bundle_errors.append(wid)
                log(f"[WARN] context bundle failed for {wid}; continuing to publish")
        if bundle_errors:
            summary["bundle_errors"] = bundle_errors

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

        # 1c. Refresh the reader-facing `status` string BEFORE the build, because
        # the build copies it into desk.json. It used to run only inside land_it.py,
        # a manual script — so on the automated path the label drifted: on
        # 2026-10-10 fanguan showed "EP01–05 可读" while ep10 and ep11 were live.
        # A reader who trusts the label clicks and finds nothing. Derived state has
        # to be derived on the path that publishes, not only when a human runs a
        # helper by hand.
        code, status_out = run([sys.executable, "sync_status.py"],
                               "sync_status", timeout=180)
        if code != 0:
            # Non-fatal: a stale label is a lie in the other direction, but blocking
            # the whole day's publish over it would be worse than shipping content
            # with an imperfect label. It is recorded so the next run can be judged.
            log("[WARN] sync_status failed; status strings may be stale")
            summary["status_sync_failed"] = (status_out or "").strip()[-200:]

        beat("status-done")

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
        summary["writer_episodes_added"] = summary["new_episodes"]
        if summary["new_episodes"] == 0 and not args.no_write:
            log("[STALL] writer produced no new episode today")
            summary["write_error"] = summary.get(
                "write_error", "writer produced 0 new episodes")
            summary["stalled"] = True

        # Refresh the reader-visible status BEFORE the pipeline, not after. It used to
        # run in the finally block, which is after Gate 4 — so every deployment
        # shipped the *previous* run's status and the live page lagged a full
        # cycle behind reality. Written here, it is built from the tree the
        # pipeline is about to publish and ships in the same deploy.
        try:
            run([sys.executable, "desk_status.py"], "desk_status", timeout=120)
        except Exception as exc:
            log(f"[WARN] desk_status refresh failed: {exc}")

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
        write_run_receipt(summary)
        # Marker only. Per-stage records already landed (write-phase checkpoint
        # above, pipeline outcome inside daily_originals), so even if this
        # process is killed right here, nothing of record is lost. The status
        # file was refreshed before the deploy, so nothing needs doing here.
        log("=== Daily task finished ===")

    return 0 if summary["status"] in ("DEPLOYED", "GATES_OK") else 1


if __name__ == "__main__":
    sys.exit(main())