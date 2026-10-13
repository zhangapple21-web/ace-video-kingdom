#!/usr/bin/env python3
"""Repair quarantined episodes, one model at a time, with verification after each.

Fifteen episodes are held back because a continuity audit failed them. Holding an
episode back is a pause, not an exile: an episode that cannot be audited can never
be repaired and re-admitted. So this walks the held list, hands each episode to a
writer model together with the exact audit findings, and re-audits the result.

Design decisions that matter here:

* **The writer is given strictly-earlier context only**, via `prior_context`. The
  original defect was that an audit saw its own sequels as backstory; a repair
  that could see them would "fix" the episode by rewriting earlier continuity, and
  the directive forbids exactly that.
* **Backups before every edit.** work.json is the only copy of the authored text.
  A model that rewrites it wrongly must not be able to destroy it.
* **The schema is re-validated after each write.** A repair that returns valid
  JSON with the wrong block shape is a failed repair, not a successful one.
* **PASS is required to lift the hold.** Nothing here publishes; the caller
  re-audits and decides.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
LOCK = HERE / ".writing.lock"
# The lock text must match what run_daily_task.py parses. It expects a pid so it can
# prove the holder is dead rather than guessing from age — the repair runner wrote a
# bare timestamp, the daily task could not read a pid from it, fell back to the TTL,
# and skipped the 08:00 writing run for six hours on 2026-10-08. Two lock writers,
# two formats, one silently dead day.
# The repair runner must also RELEASE the lock; a crashed run otherwise locks out
# the morning until the TTL expires.
LOCK_STALE_SECONDS = 12 * 3600


def acquire_lock() -> bool:
    """Take the writer lock, or skip when the pipeline is already using it."""
    if LOCK.is_file():
        stamp = LOCK.read_text(encoding="utf-8", errors="replace").strip()
        owner_alive = None
        try:
            owner = int(stamp.split("pid=")[1].split()[0])
            owner_alive = owner == os.getpid() or _pid_alive(owner)
        except (IndexError, ValueError):
            owner = None
        try:
            age = time.time() - LOCK.stat().st_mtime
        except OSError:
            age = 0.0
        if owner_alive is False:
            log(f"lock owner pid={owner} is gone; taking over")
        elif owner_alive is None and age < LOCK_STALE_SECONDS:
            log(f"writer lock held ({age / 60:.0f} min old, no pid to check); skipping")
            return False
        elif owner_alive:
            log("another run holds the writer lock; skipping repairs")
            return False
    try:
        LOCK.write_text(
            f"started={datetime.now().astimezone().isoformat(timespec='seconds')} "
            f"pid={os.getpid()}",
            encoding="utf-8")
    except OSError as exc:
        log(f"could not take the writer lock: {exc}")
        return False
    return True


def release_lock() -> None:
    """Release the lock only if this process is the recorded owner.

    Unconditionally deleting would let a run that lost the race delete the winner's
    lock — the same silent corruption as ignoring it.
    """
    if not LOCK.is_file():
        return
    try:
        stamp = LOCK.read_text(encoding="utf-8", errors="replace")
        owner = int(stamp.split("pid=")[1].split()[0])
    except (IndexError, ValueError, OSError):
        owner = None
    if owner is None or owner == os.getpid():
        LOCK.unlink(missing_ok=True)


def safe_unlink(path: pathlib.Path, attempts: int = 6, wait: float = 0.5) -> bool:
    """Delete a file, tolerating a Windows handle that has not been released yet.

    Windows keeps the handle alive for a short while after a process is
    terminated, so deleting that process's output straight away raises
    PermissionError [WinError 32]. On 2026-10-09 that exception escaped a finally
    block at 02:30 and killed the entire nightly repair — a cleanup step took down
    the job it was cleaning up after. Cleanup must never be able to fail the work.
    """
    for _ in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return True
        except OSError:
            time.sleep(wait)
    return False


def _pid_alive(pid: int) -> bool | None:
    """True/False if the pid can be judged, None if it cannot."""
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30).stdout
        if str(pid) in out:
            return True
        if out.strip():
            return False
        return None
    except Exception:
        return None
sys.path.insert(0, str(HERE))

BLOCK_KINDS = {"scene", "cast", "para", "line", "hook"}
REQUIRED_BLOCK_KEYS = {
    "scene": ("place", "time", "light"),
    "cast": ("present",),
    "para": ("t",),
    "line": ("t",),
    "hook": ("t",),
}


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def read_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_verdicts() -> dict[tuple[str, str], dict]:
    ledger = HERE / "audit_failures.json"
    if not ledger.is_file():
        return {}
    out: dict[tuple[str, str], dict] = {}
    for row in json.loads(ledger.read_text(encoding="utf-8")):
        out[(row.get("work"), row.get("episode"))] = row.get("audit") or {}
    return out


def held_episodes() -> list[tuple[str, str]]:
    q = HERE / "quarantine.json"
    if not q.is_file():
        return []
    data = json.loads(q.read_text(encoding="utf-8-sig"))
    return [(i["work"], i["episode"]) for i in ((data.get("held") if isinstance(data, dict) else data) or [])]


def validate_work(path: pathlib.Path) -> list[str]:
    """Return structural problems; empty means the file is sound."""
    problems: list[str] = []
    try:
        data = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"work.json unreadable: {exc}"]
    for ep in data.get("episodes", []):
        blocks = ep.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            problems.append(f"{ep.get('id')}: no blocks")
            continue
        for i, b in enumerate(blocks):
            kind = b.get("k")
            if kind not in BLOCK_KINDS:
                problems.append(f"{ep.get('id')} block {i}: unknown kind {kind!r}")
                continue
            for key in REQUIRED_BLOCK_KEYS[kind]:
                if key not in b:
                    problems.append(f"{ep.get('id')} block {i} ({kind}): missing {key!r}")
        kinds = [b.get("k") for b in blocks]
        if kinds and kinds[0] != "scene":
            problems.append(f"{ep.get('id')}: first block is {kinds[0]!r}, expected 'scene'")
        if kinds and kinds[-1] != "hook":
            problems.append(f"{ep.get('id')}: last block is {kinds[-1]!r}, expected 'hook'")
    return problems


def collateral_edits(before: dict, after: dict, target_ep: str) -> list[str]:
    """Return episodes other than `target_ep` whose blocks differ.

    Anything that is not episode content (status string, facts) is ignored: a model
    recomputing `status` is harmless, but a model rewriting another chapter's text
    silently invalidates that chapter's audit verdict.
    """
    def by_id(data: dict) -> dict[str, dict]:
        return {e["id"]: e for e in data.get("episodes", [])}

    a, b = by_id(before), by_id(after)
    touched = []
    for eid in sorted(set(a) | set(b)):
        if eid == target_ep:
            continue
        if eid not in a or eid not in b:
            touched.append(eid)
        elif a[eid].get("blocks") != b[eid].get("blocks"):
            touched.append(eid)
    return touched


def render_for_prompt(data: dict, ep_id: str) -> tuple[dict, dict]:
    work = {"id": data["id"], "title": data.get("title", ""),
            "chars": data.get("chars", []), "logline": data.get("logline", "")}
    ep = next((e for e in data["episodes"] if e["id"] == ep_id), None)
    return work, ep


def build_prior_context(work_id: str, ep_no: int, ep_id: str) -> str:
    import build_context_bundle as bcb
    try:
        path = bcb.build_context_bundle(work_id)
    except Exception as exc:
        return f"(context bundle unavailable: {exc})"
    if path is None:
        return "(context bundle unavailable: no published episodes)"
    text, dropped = bcb.prior_context(path.read_text(encoding="utf-8"), ep_id, ep_no)
    return f"{text}\n\n<!-- 打包时按编号丢弃的后续集: {dropped} -->\n"


def hold_reason(work_id: str, ep_id: str) -> str | None:
    """Why this episode is being held, in the words of whoever held it.

    Held is not the same as failed. Most episodes on the list are held because a
    single PASS has not yet been corroborated; four more are held because the
    connective gate measured a repeated verbal habit, and those carry a *passing*
    audit verdict. A prompt built only from audit issues would hand the writer
    "the auditor found nothing" and ask it to fix something — so it would either
    do nothing, wasting the attempt, or invent an edit, which is worse.

    So the reason is read from the hold list rather than guessed from the verdict.
    """
    q = HERE / "quarantine.json"
    if not q.is_file():
        return None
    try:
        data = json.loads(q.read_text(encoding="utf-8-sig"))
        for item in (data.get("held") if isinstance(data, dict) else data) or []:
            if item.get("work") == work_id and item.get("episode") == ep_id:
                return str(item.get("reason") or item.get("verdict") or "").strip() or None
    except (OSError, json.JSONDecodeError):
        return None
    return None


def issues_block(audit: dict, reason: str | None = None) -> str:
    issues = audit.get("issues") or []
    if not issues:
        if reason:
            return ("【注意】审核判词是 PASS，本集没有被指出剧情缺陷。"
                    "下面这段只是解释它为什么还在扣留名单上——"
                    "**按它说的那一条改，不要凭空发挥，也不要动剧情**：\n\n"
                    + reason)
        return "(审核没有给出 issues，但判词不是 PASS —— 重新审核一遍再修。)"
    lines = []
    # Decide the mode here and say so out loud. Measured 2026-10-13: with four to
    # five cross-episode issues (a verdict reversed between episodes, a reveal
    # done two different ways, a prop with no source) three models each read the
    # whole issue list, understood it, and left the episode alone. They were not
    # being stubborn — REPAIR_DIRECTIVE §1b reserves "rewrite the spine" for the
    # case where the whole episode was written wrong, which is not what these
    # episodes look like, so every model took the narrow reading and tried to
    # patch lines that cannot be patched one at a time.
    if len(issues) >= 3:
        lines.append(
            f"【这一集是重写型修复，不是小修】一共 {len(issues)} 条判词，横跨时间线、"
            "人物、道具或立场，且互相咬合——**逐条打补丁改不动，改一处会撞上另一处**。"
            "按 REPAIR_DIRECTIVE §1b：读上下文包里的压力轴，按 DAILY_DIRECTIVE §8b "
            "重写这一集的脊梁（谁在压 → 压力怎么升 → 她怎么当场翻回来 → 余震与新钩子），"
            "让上面每一条判词都不再成立。保留已经成立的细节（人物关系、已确立事实、"
            "道具归属），换掉导致矛盾的场面与节拍。\n")
    else:
        lines.append(
            "【这一集按判词小修】只需让下面每一条判词不再成立，"
            "不要重写整集气质，不要动已经成立的剧情与人物。\n")
    for i, issue in enumerate(issues, 1):
        lines.append(f"### 缺陷 {i}：{issue.get('type')} / {issue.get('severity')}")
        lines.append(f"- 判定说明：{issue.get('description', '')}")
        if issue.get("evidence_before"):
            lines.append(f"- 前文证据（必须与之一致）：{issue['evidence_before']}")
        if issue.get("evidence_after"):
            lines.append(f"- 本集冲突处（要改这里）：{issue['evidence_after']}")
        lines.append("")
    return "\n".join(lines)


# `opencode run` writes its work and then does not exit — measured on 2026-10-07:
# the model finished editing work.json at 16:44 and was still running at 17:01.
# Waiting for the process is therefore not a way to find out whether the work
# happened; it is a way to lose most of an hour per attempt. Detect completion from
# the artefact instead: once work.json stops changing, the model is done.
QUIET_SECONDS = 150
POLL_SECONDS = 10
# A model that has not touched the artefact at all after this long is not going to.
# Measured 2026-10-07: one attempt sat 16 minutes without a byte written, and the
# only reason it ended was the 30-minute overall timeout — half an hour per dead
# model, times six models, times sixteen episodes.
NO_PROGRESS_SECONDS = 480

# A pool that says "later" is not a writing failure and not the model's fault,
# but from the outside it looks exactly like "the model chose not to edit",
# because run_model returns stdout either way and the caller threw it away.
# On 2026-10-11 five unrelated AMD models all reported "blocks unchanged" in a
# single run and nothing in the log could say why. Surface the message, and
# wait out a limited pool once instead of walking straight through the list.
RATE_LIMIT_BACKOFF_SECONDS = 45
# What a quota error actually looks like, in the CLI's own words, ranged over
# three providers on 2026-10-11:
#   opencode/  "Rate limit exceeded. Please try again later."
#   amd/       "Daily usage limit exceeded: maximum $1 per period for this
#               OneClick user."
# The second one was invisible for one whole run — five unrelated AMD models all
# reported "blocks unchanged" and the log said nothing about why, because the
# pattern only knew "rate limit" and this says "usage limit".
# Words that only count as pool trouble when the surrounding text says so.
# Bare "额度" / "quota" must NOT match: this pattern is tested against model
# output that is mostly Chinese prose, and a story line like
# "个人额度已用完" or "读者额度排行榜" would otherwise be read as an API error
# and silently stop the run. Each alternative below requires an error verb or
# a status phrase alongside it.
RATE_LIMIT_RE = re.compile(
    r"\b(429|403)\b"
    r"|rate ?limit"
    r"|(daily |per day )?usage limit (exceeded|reached)"
    r"|per period for this"
    r"|too many requests"
    r"|quota (exceeded|exhausted|reached)"
    r"|overloaded|capacity"
    r"|billing|payment required|insufficient"
    # Permanent regional delisting, not throttling — but the handling is the
    # same (stop spending attempts here), and it is what killed the writer pool's
    # first model on 2026-10-13.
    r"|not available in your country"
    r"|model not found|no available model"
    r"|限流|请求过快|超出配额|配额已用完|额度已用尽|请稍后重试",
    re.I,
)


def is_rate_limited(text: str) -> bool:
    return bool(RATE_LIMIT_RE.search(text or ""))


# A daily or billing quota is not something a 45-second backoff can wait out.
# AMD's error is "$1 per period for this OneClick user" — spent for the day, so
# retrying within the hour is just noise. Only these are worth backing off;
# anything else goes straight to the next model.
QUOTA_EXHAUSTED_RE = re.compile(
    r"(daily|per period|per day).*(limit|exceeded|reached)|"
    r"(limit|exceeded|reached).*(daily|per period|per day)|"
    r"quota (exceeded|exhausted|reached)|"
    r"billing|payment required|insufficient (balance|credit|quota)|"
    # Same trap as RATE_LIMIT_RE: bare 配额/额度 is ordinary story vocabulary.
    # Require an error phrase instead.
    r"配额已用完|额度已用尽|超出配额|每日额度",
    re.I,
)


def quota_exhausted(text: str) -> bool:
    """True when the pool is out of budget for the day, not just for now."""
    return bool(QUOTA_EXHAUSTED_RE.search(text or ""))


def model_said(out: str, limit: int = 700) -> str:
    """The model's own words, trimmed to fit one log line.

    This is the only diagnostic there is when an edit does not land, and it
    was being discarded before now. "(no output)" is a distinct case worth
    saying out loud: it means the CLI exited without printing anything, which
    is a different fault from a model that returned prose and no edit.
    """
    out = (out or "").strip()
    if not out:
        return "(no output)"
    if len(out) > limit:
        out = "..." + out[-limit:]
    return " | ".join(l.strip() for l in out.splitlines() if l.strip())


def kill_tree(pid: int) -> None:
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


def run_model(model: str, work_id: str, ep_id: str, prompt: str, timeout: int,
              watched: pathlib.Path) -> tuple[int, str]:
    """Run one repair model, returning when its output settles rather than when it exits."""
    cli = pathlib.Path(os.environ.get("USERPROFILE", "")) / ".local" / "bin" / "opencode.exe"
    if not cli.is_file():
        return 1, f"opencode CLI missing at {cli}"
    cmd = [str(cli), "run", "--model", model,
           "--file", str(HERE / "REPAIR_DIRECTIVE.md"),
           "--file", str(HERE / "originals_source" / work_id / "context_bundle.md"),
           prompt]
    out_path = HERE / f".repair_out_{os.getpid()}_{work_id}_{ep_id}.log"
    try:
        with out_path.open("w", encoding="utf-8", errors="replace") as sink:
            proc = subprocess.Popen(cmd, cwd=HERE, stdout=sink, stderr=subprocess.STDOUT)
            started = time.time()
            baseline = watched.read_bytes() if watched.is_file() else None
            last_change = time.time()
            last_seen = baseline
            while True:
                if proc.poll() is not None:
                    break
                if time.time() - started > timeout:
                    kill_tree(proc.pid)
                    log(f"    model exceeded {timeout}s; killed with its children")
                    return 124, "timed out"
                time.sleep(POLL_SECONDS)
                try:
                    current = watched.read_bytes()
                except OSError:
                    continue
                if current != last_seen:
                    last_seen = current
                    last_change = time.time()
                elif current == baseline and time.time() - started >= NO_PROGRESS_SECONDS:
                    kill_tree(proc.pid)
                    log(f"    model wrote nothing in {NO_PROGRESS_SECONDS}s; killed with its children")
                    return 3, "no progress"
                elif current != baseline and time.time() - last_change >= QUIET_SECONDS:
                    # The artefact changed and has been quiet long enough: the
                    # model finished its edit. It simply never exits.
                    kill_tree(proc.pid)
                    try:
                        proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    log(f"    model finished its edit but did not exit; terminated "
                        f"with its children after {int(time.time() - started)}s")
                    break
            try:
                code = proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                kill_tree(proc.pid)
                code = 0
        text = out_path.read_text(encoding="utf-8", errors="replace")
        return code, text[-4000:]
    finally:
        safe_unlink(out_path)


def hold_codes(work_id: str, ep_id: str) -> list[str]:
    """The codes on the hold list for this episode, lowercased."""
    q = HERE / "quarantine.json"
    if not q.is_file():
        return []
    try:
        data = json.loads(q.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []
    for item in (data.get("held") if isinstance(data, dict) else data) or []:
        if item.get("work") == work_id and item.get("episode") == ep_id:
            return [str(c).upper() for c in (item.get("codes") or [])]
    return []


def needs_corroboration(work_id: str, ep_id: str) -> bool:
    """True when this episode is held only for want of a second PASS.

    Nothing is wrong with the text in this case. The auditor passed it once and
    one sample of a judgement that has been measured flipping is not enough to
    let it ship, so it is held pending a second look at the same bytes.

    These must not be handed to a writer. Told that an episode is held and needs
    fixing, with nothing actually wrong, a writer has only two moves: do nothing
    (wasting the attempt) or invent an edit to a chapter that passed.
    """
    return "PASS_STREAK" in hold_codes(work_id, ep_id)


def confirm_only(work_id: str, ep_id: str, rounds: int = 2) -> str:
    """Re-audit an unchanged episode until its PASS settles, or it fails for real.

    Returns PASS when the second consecutive PASS lands on identical text, and
    STILL_FAILING otherwise. A FAIL here is useful rather than a dead end: it
    carries issues, so the next repair round has something concrete to work from.
    """
    import verdict as verdict_mod

    for i in range(1, rounds + 1):
        log(f"  {work_id}/{ep_id}: no defect recorded; audit {i}/{rounds} on unchanged text")
        try:
            proc = subprocess.run(
                [sys.executable, "-u", str(HERE / "run_audit.py"), work_id, ep_id],
                cwd=HERE, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=900)
        except subprocess.TimeoutExpired:
            log(f"    audit {i} timed out")
            continue
        status = verdict_mod.status_of(work_id, ep_id)
        log(f"    audit {i}: exit={proc.returncode} verdict={status}")
        if status != "PASS":
            if status != "NO_VERDICT":
                issues = verdict_mod.issues_of(work_id, ep_id)
                log(f"    came back FAIL with {len(issues)} issue(s); "
                    f"now it has something to repair")
            return "STILL_FAILING"
        if verdict_mod.settled_pass(work_id, ep_id):
            log("    settled PASS on unchanged text; hold can be lifted")
            return "PASS"
    log("    still not settled; stays held")
    return "STILL_FAILING"


def repair_one(work_id: str, ep_id: str, models: list[str], timeout: int) -> str:
    work_path = HERE / "originals_source" / work_id / "work.json"
    data = read_json(work_path)
    _, ep = render_for_prompt(data, ep_id)
    if ep is None:
        log(f"  {work_id}/{ep_id}: not in source")
        return "MISSING"

    audit = latest_verdicts().get((work_id, ep_id), {})
    context = build_prior_context(work_id, int(ep.get("no", 0)), ep_id)

    # Backup before any model touches the only copy of the authored text.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = HERE / "originals_source" / work_id / f"work.json.bak-{stamp}"
    shutil.copy2(work_path, backup)
    before_data = read_json(backup)

    prompt = (
        f"修复缺陷：作品 {work_id}（{data.get('title')}）的 {ep_id}（第 {ep.get('no')} 集，"
        f"标题《{ep.get('title')}》）。\n\n"
        f"严格按 REPAIR_DIRECTIVE.md 执行：只改这一集的 blocks，不动其他集、不动 facts.json、"
        f"不改集号和标题、不要部署。\n\n"
        f"【本集现有 blocks（JSON）】\n"
        f"{json.dumps(ep.get('blocks'), ensure_ascii=False, indent=2)}\n\n"
        f"【审核判词指出的缺陷】\n{issues_block(audit, hold_reason(work_id, ep_id))}\n\n"
        f"【硬约束 facts.json 摘要见 context_bundle.md；前情只含早于本集的集】\n"
        f"{context[:14000]}\n\n"
        f"改完依次执行：build_originals.py → verify_originals_batch.py → "
        f"run_audit.py {work_id} {ep_id}，审核 PASS 才算完成。末行输出 REPAIR_DIRECTIVE "
        f"第 6 节的 JSON 摘要。"
    )

    # The context bundle on disk must be current, because the prompt cites it.
    try:
        import build_context_bundle as bcb
        bcb.build_context_bundle(work_id)
    except Exception:
        pass

    for attempt, model in enumerate(models, 1):
        log(f"  {work_id}/{ep_id}: attempt {attempt} with {model}")
        code, out = run_model(model, work_id, ep_id, prompt, timeout, work_path)

        # A limited pool returns fast, so this costs seconds, not the whole
        # timeout. Wait once on the same model: the next one usually shares the
        # same clock, and burning the whole list is how a single shared quota
        # gets recorded as "five models failed".
        if is_rate_limited(out):
            if quota_exhausted(out):
                log(f"    quota exhausted for the day on {model}: a backoff "
                    f"cannot wait that out, so straight to the next model")
                log(f"    {model_said(out, 200)}")
                continue
            log(f"    rate limited by {model} ({RATE_LIMIT_BACKOFF_SECONDS}s backoff): "
                f"{model_said(out, 200)}")
            time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
            code, out = run_model(model, work_id, ep_id, prompt, timeout, work_path)
            if is_rate_limited(out):
                log(f"    still rate limited after backoff; next model")
                continue

        problems = validate_work(work_path)
        if problems:
            log(f"    model wrote an invalid work.json; restoring backup")
            log(f"    {problems[:3]}")
            log(f"    model said: {model_said(out)}")
            shutil.copy2(backup, work_path)
            continue
        try:
            now_data = read_json(work_path)
            now_ep = next((e for e in now_data["episodes"] if e["id"] == ep_id), None)
        except Exception as exc:
            log(f"    unreadable after write ({exc}); restoring")
            shutil.copy2(backup, work_path)
            continue
        if now_ep is None or now_ep.get("blocks") == ep.get("blocks"):
            # The reason an edit did not land used to be thrown away here —
            # five models in a row produced "blocks unchanged" with no way to
            # tell a refusal from an error from a silent CLI.
            log("    blocks unchanged; trying the next model")
            log(f"    model said: {model_said(out)}")
            continue

        # The directive says "only this episode". Nothing checked that, and a
        # model that rewrites a neighbouring chapter changes an unrelated audit
        # verdict with no trace in the log. Reject the write if anything outside the
        # target episode moved — a failed repair is recoverable, silent edits to
        # chapters nobody asked about are not.
        touched = collateral_edits(before_data, now_data, ep_id)
        if touched:
            log(f"    model also edited {touched}; discarding the whole write")
            shutil.copy2(backup, work_path)
            continue

        # Connective gate, checked before the audit so a repair that reintroduces
        # the tic is rejected on a fact rather than on a model's opinion about it.
        # Repair is exactly where this tic comes from: connecting a patched clause
        # with 虽然…可… is the default move, and on 2026-10-10 that left four
        # episodes at 6-11 occurrences while the rest of the catalogue sat at zero.
        try:
            import connective_gate
            after_data = read_json(work_path)
            now_blocks = next((e.get("blocks") for e in after_data["episodes"]
                               if e["id"] == ep_id), None)
            measured = connective_gate.measure_blocks(now_blocks or [])
            if measured["fails"]:
                log(f"    connective gate: {measured['hinge_total']} hinge(s), "
                    f"dominant {measured['dominant_hinge']} — discarding")
                shutil.copy2(backup, work_path)
                continue
        except Exception as exc:
            # Never let the extra check take the repair down; the audit still runs.
            log(f"    connective gate could not run ({type(exc).__name__}); continuing")

        # Re-audit the repaired episode. A repair is only a success if the auditor
        # says so; the model's own claim in its summary line is not evidence.
        verdict = subprocess.run(
            [sys.executable, str(HERE / "run_audit.py"), work_id, ep_id],
            cwd=HERE, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
        )
        audit_out = verdict.stdout or ""
        current = latest_verdicts().get((work_id, ep_id), {})
        if current.get("status") == "PASS":
            # One PASS is not enough. The same text of tingjijia/ep05 was audited
            # PASS at 16:25 and FAIL at 16:35, so a single passing sample is not
            # evidence that the repair held. Confirm on unchanged content.
            log(f"    -> audit PASS ({model}); confirming on unchanged text")
            confirm = subprocess.run(
                [sys.executable, str(HERE / "run_audit.py"), work_id, ep_id],
                cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout,
            )
            current = latest_verdicts().get((work_id, ep_id), {})
            if current.get("status") == "PASS":
                log(f"    -> settled PASS on unchanged text; hold can be lifted")
                backup.unlink(missing_ok=True)
                return "PASS"
            log("    -> confirmation disagreed; treating as still failing")
        codes = [i.get("type") for i in (current.get("issues") or [])]
        log(f"    -> still {current.get('status')} {codes}; keeping changes, retrying")
        # Keep the improved version as the new baseline for the next attempt.
        ep = now_ep
        shutil.copy2(work_path, backup)

    log(f"  {work_id}/{ep_id}: exhausted {len(models)} model(s); last state kept")
    return "STILL_FAILING"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="", help="comma-separated work/ep to limit to")
    parser.add_argument("--models", default="", help="comma-separated model override")
    parser.add_argument("--max-models", type=int, default=2,
                        help="how many models to try per episode (bounds total runtime)")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--no-lock", action="store_true",
                        help="skip the writer lock (for a manual run when nothing else runs)")
    args = parser.parse_args()

    from run_daily_task import WRITER_MODELS
    pool = [m.strip() for m in args.models.split(",") if m.strip()] or list(WRITER_MODELS)
    # Bounded on purpose. Six models per episode across sixteen episodes is a
    # multi-hour run in which a late fix is indistinguishable from an early one;
    # better to leave an episode held, visibly, than to spend hours on it.
    models = pool[:max(1, args.max_models)]

    # Resolve the work list BEFORE taking the lock. The 02:30 task died on a
    # NameError here — `targets` was referenced by main() but had been moved into
    # _run_repairs(), so every nightly run raised instead of repairing, and the
    # scheduled task discarded the traceback. Resolving first also means the lock
    # is only held when there is real work to do.
    targets = held_episodes()
    if args.only:
        wanted = {tuple(x.strip().split("/")) for x in args.only.split(",") if "/" in x}
        targets = [t for t in targets if t in wanted]
    if not targets:
        log("nothing is held back; nothing to repair")
        return 0

    # Split by what the hold is actually for. An episode held for want of a
    # second audit has nothing to repair; sending it to a writer spends the
    # attempt and risks an edit to a chapter that passed.
    to_confirm = [t for t in targets if needs_corroboration(*t)]
    to_repair = [t for t in targets if t not in to_confirm]
    if to_confirm:
        log(f"{len(to_confirm)} held episode(s) await corroboration, not repair: "
            f"{', '.join(f'{w}/{e}' for w, e in to_confirm)}")

    if not args.no_lock and not acquire_lock():
        return 0

    try:
        return _run_repairs(args, models, targets, to_confirm, to_repair)
    finally:
        # Always release. A repair that crashed mid-run previously left the lock
        # behind and the next morning's writing run skipped itself — a dead day
        # caused by a lock, with the log saying only "another run is using it".
        if not args.no_lock:
            release_lock()
        log("writer lock released")


def _run_repairs(args, models: list[str], targets: list[tuple[str, str]],
                 to_confirm: list[tuple[str, str]],
                 to_repair: list[tuple[str, str]]) -> int:
    # Say what will actually happen. A batch can be all corroboration, in which
    # case no writer model runs and announcing a writer pool is a lie the reader
    # of the log has to notice and correct.
    if to_confirm:
        log(f"auditing {len(to_confirm)} held episode(s) for corroboration "
            f"(no writer): {', '.join(f'{w}/{e}' for w, e in to_confirm)}")
    if to_repair:
        log(f"repairing {len(to_repair)} held episode(s) with model pool: "
            f"{', '.join(models)}")
    if not to_confirm and not to_repair:
        log("nothing to do")
    results: dict[str, list[str]] = {"PASS": [], "STILL_FAILING": [], "MISSING": []}
    for work, ep in to_confirm:
        results.setdefault(confirm_only(work, ep), []).append(f"{work}/{ep}")

    for work, ep in to_repair:
        results.setdefault(repair_one(work, ep, models, args.timeout), []).append(f"{work}/{ep}")

    print()
    print("=" * 66)
    for status in ("PASS", "STILL_FAILING", "MISSING"):
        if results.get(status):
            print(f"{status} ({len(results[status])}):")
            for item in results[status]:
                print(f"  {item}")
    print("\nnothing was published or un-quarantined by this script")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
