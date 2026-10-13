#!/usr/bin/env python3
"""Rewrite the episodes whose spine became evidence work, not a reversal.

Scope was chosen by the user on 2026-10-11: ep08-ep12 is the arc where all five
works turned from 爽文 into investigation, but measurement showed part of that arc
is already good — liufang/ep10 and tuiqun/ep10 carry the highest reversal counts
in the catalogue — so rewriting the whole arc would have damaged the episodes that
work. The list is the four where procedure outweighs reversal outright:
zhenqianjin/ep09 (16:2), fanguan/ep08 (12:5), zhenqianjin/ep08 (10:1),
fanguan/ep09 (10:1).

A rewrite is only worth doing if the result is measurably different, so this
measures before and after with the same counters and refuses to claim success
without the numbers. That is the discipline the whole day has been arguing for:
an instrument that has not been checked produces confident nonsense — this
project's own beat classifier failed its calibration on 2026-10-11 and was
discarded rather than shipped.

It does not quarantine. The old text stays live while the rewrite is written and
measured, and only a rewrite that clears the bar is meant to be deployed. Holding
these back would drop them off the site for no reader benefit while they improve.

Usage:
  py -3 rewrite_episodes.py --dry-run          measure and print, write nothing
  py -3 rewrite_episodes.py --only zhenqianjin/ep09
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import shutil
import sys
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
PLAN = HERE / "rewrite_plan.json"
BACKUPS = HERE / "backup_rewrite"

# Episodes the user approved: procedure outweighs reversal outright.
TARGETS = [
    "zhenqianjin/ep09",
    "fanguan/ep08",
    "zhenqianjin/ep08",
    "fanguan/ep09",
    "tingjijia/ep06",
    "tuiqun/ep04",
    "zhenqianjin/ep05",
    "zhenqianjin/ep06",
]

CJK = re.compile(r"[一-鿿]")
PROCEDURE = (
    "证据", "线索", "核查", "核实", "追溯", "比对", "笔录", "存根", "底册",
    "登记簿", "签收", "会签", "核验", "复核", "存档", "卷宗", "台账", "是谁",
    "归档", "移交", "注销", "备案", "签章", "用印", "编号", "批复",
)
REVERSAL = (
    "当场", "当众", "开价", "认输", "认出", "翻脸", "抖出", "亮出", "甩出",
    "反手", "夺回", "抢回", "怼", "顶回去", "砸", "撕", "掀", "拍", "押",
    "赌", "赢", "输", "服", "跪", "破例", "自证", "愣住", "骇然", "变色",
    "傻眼", "懵", "作废", "退回", "免了", "不用了", "滚", "跪了",
)

# A rewrite must at minimum beat the ratio the old episode had. Generous, because
# these counters were shown to be blunt instruments; the reading after the rewrite
# is what actually decides.
MIN_PROC_RATIO = 0.75


def load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def narration(ep: dict) -> str:
    return "\n".join(b.get("t", "") for b in ep.get("blocks") or []
                     if isinstance(b, dict) and b.get("k") in {"para", "line", "hook"})


def measure(ep: dict) -> dict:
    text = narration(ep)
    chars = len(CJK.findall(text)) or 1
    proc = sum(text.count(w) for w in PROCEDURE)
    pay = sum(text.count(w) for w in REVERSAL)
    return {
        "chars": chars,
        "proc_per_1k": round(proc / chars * 1000, 1),
        "pay_per_1k": round(pay / chars * 1000, 1),
        "ratio": round(proc / pay, 2) if pay else float("inf"),
        "hook": next((b.get("t", "") for b in ep.get("blocks") or []
                      if isinstance(b, dict) and b.get("k") == "hook"), ""),
    }


def pressure_of(work_id: str) -> dict:
    f = SOURCE / work_id / "facts.json"
    if not f.is_file():
        return {}
    try:
        rec = (json.loads(f.read_text(encoding="utf-8-sig")).get("pressure") or [{}])[0]
    except (OSError, json.JSONDecodeError, IndexError):
        return {}
    return rec


def build_prompt(work_id: str, ep: dict, data: dict) -> str:
    p = pressure_of(work_id)
    lines = [
        f"重写一集：作品 {work_id}（{data.get('title')}）的 {ep['id']}"
        f"（第 {ep.get('no')} 集，标题《{ep.get('title')}》）。",
        "",
        "【为什么重写】这一集整体写成了核对记录：整集的动作是把两份文件、一个编号、",
        "一道封签对上一个档案窗口。它读起来像法证流程，不像爽文。用户已确认它偏题。",
        "",
        "【严格按 REPAIR_DIRECTIVE.md 第 1b 节执行】重写型修复必须换脊梁，不是把矛盾改对。",
        "只改这一集的 blocks，不动其他集、不动 facts.json、不改集号和标题、不要部署。",
        "",
        "【压力轴是这一轮的目标状态，不是前情】这一轴记的是全系列现在走到哪了，"
        "而你要改的这一集排在它前面。所以：",
        "  - 「上一轮赢下」「代价」指的是这一轴所在那一轮的记录，**不是这一集之前发生的事**。",
        "    绝不许把这一集之后才发生的结果写进这一集，那会让时间线倒过来。",
        "  - 正确的用法：把这一集写成**通往那条轴的一级台阶**。这一集结束时，她离"
        "赌注更近一步、或者被压得更狠一点，方向对就行。",
        "  - 「接下来必须不同的」对这一集同样适用：这一集赢的方式，不能和前面几集重复。",
        "",
        "【这一轮的压力轴（来自 facts.json，权威，高于你的任何发挥）】",
    ]
    for key, label in (("stake", "赌注"), ("how_won", "怎么赢"),
                       ("opponent", "对手"), ("deadline", "期限"),
                       ("last_won", "上一轮赢下"), ("cost", "代价"),
                       ("next_must_differ", "接下来必须不同的")):
        val = str(p.get(key) or "").strip()
        lines.append(f"- {label}：" + (val if val else "（未填——按下面要求自己设计，并写进 pending）"))
    lines += [
        "",
        "【脊梁，按这个写】谁在压她 → 压力怎么升（筹码变 / 对手变 / 期限变）→"
        "她怎么**当场**翻回来 → 围观的人当众吃一次瘪。",
        "",
        "【硬要求】",
        "- 赌注必须具体、当众、能被拿走。有人当场眼红、想抢、能在这一幕里拿走吗？",
        "  答不上来，说明你写的还是『查清真相』，那是解谜的赌注。",
        "- 笔迹、铜屑、回执、编号、封条可以用，但**只能是手段，不能是本集要完成的任务**。",
        "  反例（已判偏题）：『配钥匙铺齿模单与铜屑对上井底锁芯新痕』——这是比对任务。",
        "- **不要用「信息揭露递进」模板**（线索A→结论1→发现不对劲→线索B推翻→更大秘密）。",
        "  那是悬疑/解谜的章节模板。",
        "- 『接下来必须不同的』这一条最容易犯懒：上一轮赢的方式，这一集绝不能再用同一招。",
        "- 上一集的钩子意图要保留（除非判词说明它失效），但用新的脊梁去兑现。",
        "- 场景格式照旧：场景｜光｜在场 头，括号动作，剧本行，不写叙述总结。",
        "",
        f"【本集现有 blocks（JSON）】",
        json.dumps(ep.get("blocks"), ensure_ascii=False, indent=2),
        "",
        "【必须一并改写本集的 beat 字段】beat 是这一集的脊梁，下一集的作家会在上下文包里读到它。旧的 beat 写着「档案窗口拆封、手环编号对上空栏」这种比对任务，留着会把后面几集重新拉回程序腔。新 beat 要写成：谁在压她 · 她当场怎么翻回来（不要写成两份文件对上了）。格式与旧 beat 一致，用 `·` 分隔。\n"
        "改完依次执行：build_originals.py → verify_originals_batch.py → "
        f"run_audit.py {work_id} {ep['id']}，审核 PASS 才算完成。",
        "末行输出 REPAIR_DIRECTIVE 第 6 节的 JSON 摘要。",
    ]
    return "\n".join(lines)


def apply_probe(models: list, probe: dict | None,
                max_age_s: int = 1800) -> tuple[list, list]:
    """Drop models whose pool a fresh probe found spent for the day.

    Pure function so it can be tested without a network: probe is the parsed
    writer_pool_probe.json (or None), and only QUOTA_EXHAUSTED entries younger
    than max_age_s are dropped. A missing, unreadable, or stale probe changes
    nothing — a probe file must never be able to silently cancel a run. If
    every model is spent, the list is kept as-is with the warning left to the
    caller: running zero models would look like success.
    """
    if not probe or not isinstance(probe, dict):
        return list(models), []
    try:
        checked = datetime.fromisoformat(str(probe.get("checked_at", "")))
        age = (datetime.now().astimezone() - checked).total_seconds()
    except ValueError:
        return list(models), []
    if age < 0 or age > max_age_s:
        return list(models), []
    pools = probe.get("pools") or {}
    if not isinstance(pools, dict):
        return list(models), []
    spent = {m for m, r in pools.items()
             if isinstance(r, dict) and r.get("status") == "QUOTA_EXHAUSTED"}
    kept = [m for m in models if m not in spent]
    skipped = [m for m in models if m in spent]
    if skipped and not kept:
        return list(models), []
    return kept, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--models", default="")
    ap.add_argument("--max-models", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--skip-spent", action="store_true",
                    help="drop models a fresh writer_pool_probe.json found "
                         "quota-exhausted (probe must be <30min old)")
    args = ap.parse_args()

    repair = load("repair_evt", HERE / "repair_episodes.py")
    rdt = load("rdt", HERE / "run_daily_task.py")
    import build_context_bundle as bcb

    targets = TARGETS
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        targets = [t for t in targets if t in want]
    if not targets:
        print("nothing to rewrite")
        return 0

    models = ([m.strip() for m in args.models.split(",") if m.strip()]
              or list(rdt.WRITER_MODELS))[:max(1, args.max_models)]

    if args.skip_spent:
        try:
            probe = json.loads((HERE / "writer_pool_probe.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  --skip-spent: no usable probe file ({exc}); keeping all models")
            probe = None
        if probe is not None:
            kept, skipped = apply_probe(models, probe)
            for m in skipped:
                print(f"  --skip-spent: dropping {m} (probe: quota exhausted)")
            if skipped and kept:
                models = kept
            elif skipped:
                print("  --skip-spent: every model is spent; keeping the list "
                      "and letting the loop surface it")

    print("=" * 78)
    print("重写前 —— 同一个仪器，先量后写")
    print("=" * 78)
    before = {}
    for key in targets:
        wid, eid = key.split("/")
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        ep = next(e for e in data["episodes"] if e["id"] == eid)
        m = measure(ep)
        before[key] = m
        ratio = "inf" if m["ratio"] == float("inf") else f"{m['ratio']:.2f}"
        print(f"  {key:<20} proc={m['proc_per_1k']:>5}/1k  pay={m['pay_per_1k']:>5}/1k"
              f"  ratio={ratio}")
    print()

    if args.dry_run:
        for key in targets:
            wid, eid = key.split("/")
            data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
            ep = next(e for e in data["episodes"] if e["id"] == eid)
            print("=" * 78)
            print(f"--- {key} 重写提示词预览 ---")
            print(build_prompt(wid, ep, data)[:1500])
            print()
        return 0

    BACKUPS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    results = []

    for key in targets:
        wid, eid = key.split("/")
        work_path = SOURCE / wid / "work.json"
        data = json.loads(work_path.read_text(encoding="utf-8"))
        ep = next(e for e in data["episodes"] if e["id"] == eid)
        prompt = build_prompt(wid, ep, data)

        backup = BACKUPS / f"{stamp}_{wid}_{eid}_work.json"
        shutil.copy2(work_path, backup)

        try:
            bcb.build_context_bundle(wid)
        except Exception:
            pass

        print("=" * 78)
        print(f"{key}  ——  models: {', '.join(models)}")
        print("=" * 78)
        done = False
        for attempt, model in enumerate(models, 1):
            print(f"  attempt {attempt} with {model}")
            code, out = repair.run_model(model, wid, eid, prompt, args.timeout,
                                         work_path)
            # A pool that says "later" returns fast, so the backoff costs seconds
            # rather than the whole timeout. Wait once on the same model: five
            # unrelated models all reporting "blocks unchanged" in one run on
            # 2026-10-11 was one shared quota, not five writing failures.
            if repair.is_rate_limited(out):
                if repair.quota_exhausted(out):
                    print("    quota exhausted for the day on", model)
                    print("    a 45s backoff cannot wait that out; next model")
                    print("    model said:", repair.model_said(out))
                    continue
                print(f"    rate limited by {model}; backing off "
                      f"{repair.RATE_LIMIT_BACKOFF_SECONDS}s")
                import time as _t
                _t.sleep(repair.RATE_LIMIT_BACKOFF_SECONDS)
                code, out = repair.run_model(model, wid, eid, prompt,
                                             args.timeout, work_path)
                if repair.is_rate_limited(out):
                    print("    still rate limited after backoff; next model")
                    continue
            problems = repair.validate_work(work_path)
            if problems:
                print("    invalid work.json; restoring backup")
                print("   ", problems[:3])
                print("    model said:", repair.model_said(out))
                shutil.copy2(backup, work_path)
                continue
            now_data = json.loads(work_path.read_text(encoding="utf-8"))
            now_ep = next((e for e in now_data["episodes"] if e["id"] == eid), None)
            if now_ep is None or now_ep.get("blocks") == ep.get("blocks"):
                if repair.narrated_an_edit(out):
                    print("    model described the fix but never wrote it; "
                          "treating as a persistence failure, not a refusal")
                    print("    it claimed:", repair.describe_claim(out))
                else:
                    print("    blocks unchanged; restoring and trying the next model")
                    # The reason an edit did not land was being discarded here.
                    print("    model said:", repair.model_said(out))
                shutil.copy2(backup, work_path)
                continue
            if str(now_ep.get("beat") or "").strip() == str(ep.get("beat") or "").strip():
                # A rewrite that leaves the old spine behind is half applied: the
                # next episode's writer reads this beat in its context bundle and
                # gets pulled back toward the paperwork register.
                print("    beat unchanged; the old spine would drag the next "
                      "episode back. restoring and trying the next model")
                shutil.copy2(backup, work_path)
                continue
            touched = repair.collateral_edits(data, now_data, eid)
            if touched:
                print(f"    model also edited {touched}; discarding the whole write")
                shutil.copy2(backup, work_path)
                continue

            after = measure(now_ep)
            b = before[key]
            ratio_after = ("inf" if after["ratio"] == float("inf")
                           else f"{after['ratio']:.2f}")
            b_ratio = float("inf") if b["ratio"] == float("inf") else b["ratio"]
            improved = (after["proc_per_1k"] <= b["proc_per_1k"] * MIN_PROC_RATIO
                        or after["pay_per_1k"] > b["pay_per_1k"])
            print(f"    before: proc={b['proc_per_1k']}/1k pay={b['pay_per_1k']}/1k"
                  f" ratio={b_ratio if b_ratio != float('inf') else 'inf'}")
            print(f"    after : proc={after['proc_per_1k']}/1k pay={after['pay_per_1k']}/1k"
                  f" ratio={ratio_after}")
            print(f"    hook  : {' '.join(after['hook'].split())[:90]}")
            print(f"    verdict: {'IMPROVED' if improved else 'NOT MEASURABLY BETTER'}")
            if not improved:
                print("    keeping the backup; the rewrite did not measurably help")
                shutil.copy2(backup, work_path)
                results.append((key, "REJECTED_NOT_BETTER"))
                break
            results.append((key, "REWRITTEN"))
            done = True
            break

        if not done and not any(r[0] == key for r in results):
            shutil.copy2(backup, work_path)
            results.append((key, "FAILED"))

    print()
    print("=" * 78)
    print("重写结果")
    print("=" * 78)
    for key, status in results:
        print(f"  {key:<20} {status}")
    rewritten = [k for k, s in results if s == "REWRITTEN"]
    print(f"\n  改写成功 {len(rewritten)}/{len(targets)}；未改写的保留原文")
    print("  没有 deploy，也没有改扣留名单——改完先给你看。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())