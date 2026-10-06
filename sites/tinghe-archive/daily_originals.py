"""Daily originals batch: validate, build context, build, verify, audit, deploy.

This is the repeatable half of "publish five originals a day". Authoring is a
human decision and stays in ``originals_source/<work_id>/work.json``; this
script turns whatever is authored there into the public snapshot, proves the
result, and deploys to Cloudflare Pages.

Three gates are deliberate and fail closed:
1. Context bundle generation (pre-write, ensures continuity)
2. Structural validation + verification (build_originals + verify_originals_batch)
3. Narrative continuity audit (run_audit per new episode)
4. Deployment (only if all above PASS)

A green run (exit 0) means "live on https://studio.zhangningjing.com/dramai/".
Exit 1 = structural/build failure. Exit 2 = audit interception. Exit 3 = deploy failure.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # wrangler output carries ✨ etc.; GBK console would crash print()
from datetime import date, datetime
from pathlib import Path
from typing import Any
from tools.atomic_io import atomic_write_text

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build_originals.py"
VERIFY = HERE / "verify_originals_batch.py"
BUILD_CTX = HERE / "build_context_bundle.py"
AUDIT = HERE / "run_audit.py"
SITE_META = HERE / "build_site_meta.py"
INTEGRITY = HERE / "check_site_integrity.py"
CHAPTER_PAGES = HERE / "build_chapter_pages.py"
PUBLIC = HERE / "public"
SOURCE = HERE / "originals_source"


def run(command: list[str], label: str) -> tuple[int, str]:
    # Child scripts print Chinese; on Windows they can come back in the console
    # code page rather than UTF-8. Decoding strictly raised UnicodeDecodeError
    # inside the reader thread and silently lost the whole output, so pin the
    # child to UTF-8 and never fail on an undecodable byte.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    # 900s, not the refactor's 300s: Gate 3 calls run_audit.py, which runs the
    # model with a 600s internal timeout; an outer 300s would kill healthy
    # audits and turn them into spurious FAILs.
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=env,
                            timeout=900)
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        print(f"[FAIL] {label}")
        print(output.rstrip()[-2500:])
    return result.returncode, output


def authored_works() -> dict[str, dict[str, Any]]:
    """Return {work_id: work_data} for works that have episodes to publish."""
    works: dict[str, dict[str, Any]] = {}
    for work_file in sorted(SOURCE.glob("*/work.json")):
        data = json.loads(work_file.read_text(encoding="utf-8"))
        wid = data.get("id", work_file.parent.name)
        eps = data.get("episodes", [])
        if eps:
            works[wid] = data
    return works


def published_episode_ids() -> dict[str, set[str]]:
    """Return {work_id: {ep ids}} currently published under public/data."""
    out: dict[str, set[str]] = {}
    root = PUBLIC / "data" / "originals"
    if root.is_dir():
        for work_dir in sorted(root.iterdir()):
            if work_dir.is_dir():
                out[work_dir.name] = {p.stem for p in work_dir.glob("ep*.json")}
    return out


SNAP_ROOT = HERE / ".public_snapshots"
SNAP_KEEP = 5


def snapshot_public() -> Path:
    """Copy public/ aside before the build writes, for one-click rollback.

    Rollback restores content, not code: the snapshot holds exactly what the
    next deploy would overwrite. Old snapshots are pruned to SNAP_KEEP.
    """
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = SNAP_ROOT / stamp
    shutil.copytree(PUBLIC, dest)
    olds = sorted(p for p in SNAP_ROOT.iterdir() if p.is_dir())
    for stale in olds[:-SNAP_KEEP]:
        shutil.rmtree(stale, ignore_errors=True)
    print(f"public snapshot: {dest.name} ({len(olds)} kept)")
    return dest


LIVE_BASE = "https://studio.zhangningjing.com/dramai/"
LIVE_RETRIES = 6
LIVE_RETRY_WAIT = 30


def verify_live(deploy_output: str, expect_works: dict[str, int],
                new_episodes: list[tuple[str, str]]) -> tuple[bool, str, str]:
    """Confirm the production domain serves what was just deployed.

    Returns (ok, note, receipt_url). The receipt is parsed from wrangler's
    output; ok requires every authored work's live episode count to match AND
    every new episode file to answer 200. Retries cover propagation lag.
    """
    import re
    import time
    import urllib.request

    receipt = ""
    m = re.search(r"https://[0-9a-f]+\.tinghe-archive\.pages\.dev", deploy_output)
    if m:
        receipt = m.group(0)
        atomic_write_text((HERE / ".last_deploy.json"), json.dumps({
            "url": receipt,
            "time": datetime.now().isoformat(timespec="seconds"),
            "works": expect_works,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def get(path: str) -> tuple[int, bytes]:
        req = urllib.request.Request(LIVE_BASE + path,
                                     headers={"User-Agent": "tinghe-deploy-verify/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, resp.read()
        except Exception as exc:  # HTTPError carries a status; anything else is 0
            status = getattr(exc, "code", 0) or 0
            return status, b""

    note = ""
    for attempt in range(1, LIVE_RETRIES + 1):
        status, body = get("data/originals/desk.json")
        live_works: dict[str, int] = {}
        if status == 200:
            try:
                live_works = {w["id"]: len(w.get("episodes", []))
                              for w in json.loads(body.decode("utf-8"))["works"]}
            except Exception:
                pass
        drifted = [f"{wid}: live {live_works.get(wid, '∅')} vs want {n}"
                   for wid, n in expect_works.items()
                   if live_works.get(wid) != n]
        missing = [f"{wid}/{ep}" for wid, ep in new_episodes
                   if get(f"data/originals/{wid}/{ep}.json")[0] != 200]
        if not drifted and not missing:
            total = sum(expect_works.values())
            return True, f"https://studio.zhangningjing.com/dramai/ ({total} authored eps)", receipt
        note = (f"attempt {attempt}/{LIVE_RETRIES}: drifted {drifted or 'none'}, "
                f"missing {missing or 'none'}")
        print(f"  [verify] {note}")
        if attempt < LIVE_RETRIES:
            time.sleep(LIVE_RETRY_WAIT)
    return False, note, receipt


def generate_context_bundles(work_ids: list[str]) -> bool:
    """Generate context_bundle.md for each work. Returns True if all succeed."""
    ok = True
    for wid in work_ids:
        code, _ = run([sys.executable, str(BUILD_CTX), wid], f"build_context_bundle({wid})")
        if code != 0:
            ok = False
    return ok


def style_line(work_id: str, ep_id: str, style: dict[str, Any]) -> str:
    """One compact STYLE line per episode for logs and daily_log pickup."""
    return (f"[STYLE] {work_id}/{ep_id} "
            f"words={style.get('words', '?')} "
            f"visual={style.get('visual_points', '?')} "
            f"pressure={'Y' if style.get('pressure_complete') else 'n'} "
            f"dumps={'Y' if style.get('dialogue_dumps') else 'n'} "
            f"hook={'Y' if style.get('hook_open') else 'n'} "
            f"humor={'Y' if style.get('humor_ok') else 'n'} "
            f"violation={'Y' if style.get('violation') else 'n'}")


def record_outcome(status: str, works: dict[str, Any], total_eps: int,
                   new_episodes: list[tuple[str, str]],
                   audit_summaries: list[dict[str, Any]],
                   receipt_url: str = "") -> None:
    """Append the pipeline-outcome entry to daily_log.md.

    This lives in the deploy subprocess, not the wrapper, so the record
    survives a wrapper death — exactly what happened on 2026-10-06, when the
    wrapper died after a verified deploy and left no daily_log entry behind.
    """
    new_works = len({wid for wid, _ in new_episodes})
    lines = [
        f"## {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 作品: {new_works} 新 / {len(works)} 总",
        f"- 集数: +{len(new_episodes)} / {total_eps} 总",
        f"- 状态: {status}",
    ]
    if receipt_url:
        lines.append(f"- 收据: {receipt_url}")
    passed = sum(1 for s in audit_summaries if s.get("passed"))
    if audit_summaries:
        lines.append(f"- 审核: {passed}/{len(audit_summaries)} PASS")
    for s in audit_summaries:
        if not s.get("passed"):
            issues = (s.get("audit") or {}).get("issues", [])
            first = issues[0] if issues else {}
            lines.append(f"- 拦单: {s['work']}/{s['episode']} "
                         f"{first.get('severity', '?')} {first.get('type', '?')}")
    for s in audit_summaries:
        lines.append("- 文笔: " + style_line(s["work"], s["episode"], s.get("style", {})))
    lines.append("")
    with (HERE / "daily_log.md").open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_audits(new_episodes: list[tuple[str, str]]) -> tuple[bool, list[dict[str, Any]]]:
    """Run audit for each new episode. Returns (all_pass, audit_summaries).

    A FAIL is retried once against byte-identical input before it blocks. The
    auditor is a stochastic judge: the same episode has passed one run and
    failed the next with mutually contradictory complaints (2026-10-05
    fanguan/ep07 passed clean, then failed on a two-word edit with issues that
    contradicted the passing round). Chasing every single-run complaint with
    content edits never converges; a FAIL that does not reproduce is noise. Two
    consecutive FAILs are treated as signal and block the deploy.
    """
    def parse_verdict(output: str, tag: str) -> dict[str, Any]:
        """Extract an AUDIT_JSON / STYLE_JSON verdict line from a capture.

        Falls back to {} when the child crashed before judging (timeout,
        traceback): callers treat a missing verdict as a block, never a pass.
        """
        for line in reversed(output.splitlines()):
            if line.startswith(tag):
                try:
                    verdict = json.loads(line[len(tag):])
                except Exception:
                    return {}
                return verdict if isinstance(verdict, dict) else {}
        return {}

    all_pass = True
    summaries = []
    for work_id, ep_id in new_episodes:
        code, out = run([sys.executable, str(AUDIT), work_id, ep_id], f"run_audit({work_id}/{ep_id})")
        audit = parse_verdict(out, "AUDIT_JSON:")
        style = parse_verdict(out, "STYLE_JSON:")
        print("  " + style_line(work_id, ep_id, style))
        passed = code == 0
        first_audit = first_style = None
        if not passed:
            first_audit, first_style = audit, style
            print(f"  [AUDIT FAIL] {work_id}/{ep_id}: retrying once on identical input…")
            code, out = run([sys.executable, str(AUDIT), work_id, ep_id],
                            f"run_audit({work_id}/{ep_id}) retry")
            audit = parse_verdict(out, "AUDIT_JSON:")
            style = parse_verdict(out, "STYLE_JSON:")
            print("  " + style_line(work_id, ep_id, style))
            passed = code == 0
            print(f"  [AUDIT {'PASS' if passed else 'FAIL'}] {work_id}/{ep_id} on retry: "
                  f"{'noise, shipping' if passed else 'reproduced, blocking'}")
            if passed:
                # A FAIL that does not reproduce is filed as noise, not
                # deleted: both rounds stay in audit_failures.json, and this
                # one-line pointer lets a human抽查 whether the retry policy
                # is letting real problems through.
                with (HERE / "audit_noise_log.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "date": date.today().isoformat(),
                        "work": work_id,
                        "episode": ep_id,
                        "fail_issues": (first_audit or {}).get("issues", []),
                        "pass_issues": audit.get("issues", []),
                        "fail_style": first_style,
                        "pass_style": style,
                    }, ensure_ascii=False) + "\n")
                print(f"  [AUDIT NOISE] {work_id}/{ep_id} filed to audit_noise_log.jsonl")
        all_pass = all_pass and passed
        summaries.append({"work": work_id, "episode": ep_id, "passed": passed,
                          "audit": audit, "style": style})
        if not passed:
            print(f"  [AUDIT FAIL] {work_id}/{ep_id}: {audit.get('issues', [])}")
    return all_pass, summaries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true",
                        help="validate and report drift without writing the snapshot")
    parser.add_argument("--no-deploy", action="store_true",
                        help="run every gate including build, but stop before deploying")
    args = parser.parse_args()

    works = authored_works()
    if not works:
        print("[FAIL] no works authored under", SOURCE)
        return 1
    # Filled by Gate 3; initialized here so every record_outcome call below
    # sees defined values even when an early gate fails first.
    new_episodes: list[tuple[str, str]] = []
    audit_summaries: list[dict[str, Any]] = []

    work_ids = list(works.keys())
    total_eps = sum(len(w.get("episodes", [])) for w in works.values())
    print(f"batch date: {date.today().isoformat()}")
    print(f"authored: {len(work_ids)} works / {total_eps} episodes")

    # Gate 0: Context bundles
    print("\n=== Gate 0: Context bundles ===")
    if not generate_context_bundles(work_ids):
        print("[FAIL] Context bundle generation failed")
        record_outcome("SETUP_FAILED", works, total_eps, new_episodes, audit_summaries)
        return 1

    # Gate 1: Build (with --check-only first if requested)
    print("\n=== Gate 1: Build ===")
    if not args.check_only:
        # Rollback point: what the deploy below is about to overwrite.
        snapshot_public()
    # Snapshot the published episode set BEFORE the build writes. Gate 3 finds
    # new episodes by comparing the authored source against what was already
    # published; snapshotting after the build would always compare the build
    # against itself, find nothing, and silently skip every audit. That is how
    # the narrative gate went years without ever firing.
    #
    # Prefer the wrapper's pre-write snapshot when present: the writer
    # self-checks with a real build mid-run, so even this Gate 1 snapshot can
    # already contain the new episodes. The file is consumed exactly once.
    pub_before = published_episode_ids()
    pre_write = HERE / ".pub_before.json"
    if pre_write.is_file():
        try:
            state = json.loads(pre_write.read_text(encoding="utf-8"))
            pub_before = {k: set(v) for k, v in state.get("works", {}).items()}
            print(f"using pre-write snapshot from wrapper ({state.get('date')})")
        except (OSError, json.JSONDecodeError, AttributeError) as exc:
            print(f"[WARN] ignoring unreadable .pub_before.json ({exc}); using Gate 1 snapshot")
        try:
            pre_write.unlink()
        except OSError:
            pass
    command = [sys.executable, str(BUILD)] + (["--check-only"] if args.check_only else [])
    code, output = run(command, "build_originals")
    if code != 0:
        record_outcome("BUILD_FAILED", works, total_eps, new_episodes, audit_summaries)
        return 1
    for line in output.splitlines():
        if any(key in line for key in ("status", "desk", "action", "work", '"episodes"')):
            print(line.rstrip())

    if args.check_only:
        print("\npublic_dir_ready: false (check-only, nothing written)")
        print("deploy_pending:  true")
        return 0

    # Gate 2: Verify
    print("\n=== Gate 2: Verify ===")
    code, output = run([sys.executable, str(VERIFY)], "verify_originals_batch")
    if code != 0:
        record_outcome("BUILD_FAILED", works, total_eps, new_episodes, audit_summaries)
        return 1
    for line in output.splitlines():
        print(line.rstrip())

    # Gate 2b: Public projection hygiene. Both are local, fast and fail closed
    # on real problems, so a broken snapshot or a mojibake edit cannot ship.
    print("\n=== Gate 2b: Site projection ===")
    gates = (("build_chapter_pages", CHAPTER_PAGES, True),
             ("build_site_meta", SITE_META, True),
             ("check_site_integrity", INTEGRITY, False))
    for label, script, check_only in gates:
        cmd = [sys.executable, str(script)] + (["--check-only"] if check_only else [])
        code, output = run(cmd, label)
        if code != 0:
            print(f"[FAIL] {label}")
            print(output.rstrip()[-1500:])
            record_outcome("BUILD_FAILED", works, total_eps, new_episodes, audit_summaries)
            return 1
        for line in output.splitlines()[-3:]:
            print(line.rstrip())

    # Gate 3: Narrative continuity audit
    print("\n=== Gate 3: Narrative continuity audit ===")
    # Re-read the source: `works` was loaded at startup, before Gate 0.5 wrote
    # today's episodes, so it cannot see them. Comparing the stale dict against
    # anything finds nothing — this is the second reason the gate never fired
    # (the first was comparing post-build public against itself). Tonight's
    # trial proved it: ep08 landed on disk, yet the gate reported no new
    # episodes, because the in-memory catalogue predated the writing.
    works = authored_works()
    work_ids = list(works.keys())
    total_eps = sum(len(w.get("episodes", [])) for w in works.values())
    print(f"source now: {len(work_ids)} works / {total_eps} episodes")
    # New episodes are those the authored source has beyond what was published
    # BEFORE this run's build (see the Gate 1 snapshot). Comparing against the
    # current public tree would find nothing, because the build just wrote it.
    new_episodes = []
    for work_id, work_data in works.items():
        before = pub_before.get(work_id, set())
        for ep in work_data.get("episodes", []):
            if ep["id"] not in before:
                new_episodes.append((work_id, ep["id"]))

    if new_episodes:
        print(f"New episodes to audit: {len(new_episodes)}")
        audit_ok, audit_summaries = run_audits(new_episodes)
        if not audit_ok:
            print("[FAIL] Narrative audit intercepted deployment")
            record_outcome("AUDIT_FAILED", works, total_eps, new_episodes, audit_summaries)
            return 2
    else:
        print("No new episodes (all already published)")

    print(f"\npublic_dir_ready: true ({PUBLIC})")

    # Gate 4: Deploy
    if args.no_deploy:
        print("\n=== Gate 4: Deploy (skipped, --no-deploy) ===")
        print("deploy_pending:  true  <- gates passed; nothing was pushed")
        return 0

    print("\n=== Gate 4: Deploy ===")
    # --branch main is load-bearing, not cosmetic. Wrangler picks the target
    # environment from the repo's current branch; on any other branch the exact
    # same command deploys to Preview, reports success, and the live site never
    # changes. That is what happened to the 2026-10-05 catch-up batch on the
    # first attempt (repo sat on fix/second-round-audit). Pin production here
    # so a branch drift can never silently swallow a deploy again.
    deploy_cmd = [
        "cmd.exe", "/c",
        f"set PATH=%PATH%;C:\\Program Files\\nodejs&&cd /d D:\\视频创作\\ace-video-kingdom\\sites\\tinghe-archive&&"
        f"npx --yes wrangler pages deploy public --project-name tinghe-archive "
        f"--branch main --commit-dirty=true",
    ]
    print("deploying to Cloudflare Pages…")
    code, output = run(deploy_cmd, "wrangler pages deploy")
    tail = output.rstrip().splitlines()[-3:]
    for line in tail:
        print(line)
    if code != 0:
        print(f"\ndeploy_pending:  true  <- wrangler exited {code}; snapshot is locally ready but NOT live.")
        record_outcome("DEPLOY_FAILED", works, total_eps, new_episodes, audit_summaries)
        return 3

    # Gate 4b: prove it is live. Wrangler reporting success is not enough — a
    # deploy can land on Preview (wrong branch) while printing success, as
    # happened on 2026-10-05. Fetch the production domain and compare per-work
    # episode counts plus every new episode file. Retry briefly for lag.
    # (Per-work, not grand total: the live desk also carries legacy works the
    # local authored count does not include. Comparing totals would fail every
    # run by construction.)
    expect_works = {wid: len(w.get("episodes", [])) for wid, w in works.items()}
    live_ok, live_note, receipt_url = verify_live(output, expect_works, new_episodes)
    if receipt_url:
        print(f"receipt: {receipt_url}")
    if not live_ok:
        print(f"[FAIL] live verification: {live_note}")
        print("deploy_pending:  true  <- pushed but NOT confirmed live; "
              "rollback with py -3 rollback_public.py --list")
        record_outcome("DEPLOY_FAILED", works, total_eps, new_episodes,
                       audit_summaries, receipt_url)
        return 3

    print(f"\ndeploy_pending:  false  <- live deploy complete ({live_note})")
    # Post-deploy teardown lives HERE, not in the wrapper, so a wrapper death
    # (2026-10-06) cannot strand a verified deploy without records or staged
    # facts. Non-blocking: the deploy already succeeded.
    code2, _ = run([sys.executable, str(HERE / "promote_facts.py"), "--apply"],
                   "promote_facts")
    if code2 != 0:
        print("[WARN] facts promotion failed; pending facts stay pending")
    record_outcome("DEPLOYED", works, total_eps, new_episodes, audit_summaries,
                   receipt_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())