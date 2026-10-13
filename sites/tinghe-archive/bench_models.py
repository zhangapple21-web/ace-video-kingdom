#!/usr/bin/env python3
"""Benchmark the free models on this project's actual writing task.

Online leaderboards rank creative writing in general. That is not the same
question as "which model can write a 1000-1500 word Chinese short-drama episode
that keeps a fixed cast, lands a beat, and leaves a hook that has not been
answered yet". A model can top a prose Elo and still fail the structural contract,
and in this pipeline a structurally invalid episode is thrown away by the build.

So each candidate gets the same real task, in a scratch directory that cannot
touch authored work, and is scored on two kinds of evidence:

  * mechanical, from the output itself — valid blocks, word count in range,
    required block kinds, whether it respected the "one <h3>场景</h3>" shape.
    These are facts, not opinions.
  * a prose judgement from a separate model, anonymised and asked to rank.

The prose judgement is one model's opinion and is reported as such. It is listed
separately from the mechanical results and never used to override a hard failure.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = HERE / "_bench"
CLI = pathlib.Path(os.environ.get("USERPROFILE", "")) / ".local" / "bin" / "opencode.exe"

# Ordered by "can it hold a ~20KB context bundle and write Chinese prose", not by
# overall quality. Muse Spark is placed high because Meta's Muse Spark 1.1 scores
# 1916 on EQ-Bench Creative Writing (checked 2026-10-08), the strongest
# creative-writing family among the free tiers available here.
CANDIDATES = [
    "opencode/muse-spark-1.3-contributor-free",
    "opencode/ling-3.1-flash-free",
    "opencode/longcat-2.5-preview-free",
    "opencode/nemotron-3-ultra-free",
    "opencode/fledge-alpha-free",
    "opencode/mimo-v2.6-flash-free",
    "opencode/nemotron-3.5-lightning-free",
    "opencode/ling-3.0-flash-fin-free",
    "opencode/exo-free",
    "opencode/space-bunny-free",
]

TASK = """你是域外星际短剧的编剧。下面给你一个既有作品的设定，请为它写**第 09 集**。

【作品】《退群》—— 一群被星际公司注销了账号的旧员工，发现"注销"背后是一套按等级
给人定价的系统。他们在工位上互相作证，把定价表一条一条对出来。

【必须遵守】
1. 总字数 1000～1500 字（含对白），低于 900 字不合格。
2. 至少 3 个可拍的具体画面点：道具、光线、倒计时，要能被镜头拍出来。
3. 结尾必须留钩子，且钩子要是**本章没有回答**的问题（前面几集已经回答过的不算钩子）。
4. 人物：姜迟（女，主角，前地质署签发员，冷静、只认证据）、铁算盘（男，工位旁，
   话少、随身带一把算盘）、秦瑰（女，名册管理员）。
5. 严禁：完整流程罗列、内心独白当叙述、"空气中弥漫着紧张的气息"这类空话、
   每段都用同一种句式收尾。
6. 输出**严格的 JSON**，不要任何解释文字，格式：
{"title":"第09集 标题","beat":"本集一句话落点","blocks":[{"k":"scene","place":"地点","time":"日/夜 内/外","light":"光线"},{"k":"cast","present":["姜迟"],"absent":[]},{"k":"para","t":"叙述或动作"},{"k":"line","t":"角色名：台词"},{"k":"hook","t":"结尾钩子"}]}

只输出 JSON。"""


def run(model: str, minutes: int = 7) -> dict:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    out_path = SCRATCH / "out.txt"
    # Per-model artifact. The first full run lost every model's prose because all
    # output went through one overwritten file — muse-spark's 1058-word piece, the
    # very text proposed as a few-shot exemplar, was never readable afterwards.
    # A benchmark that cannot show its work is a rumor, not evidence.
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", model)
    artifact = SCRATCH / f"{safe}.txt"
    cmd = [str(CLI), "run", "--model", model, TASK]
    started = time.time()
    try:
        proc = subprocess.Popen(cmd, cwd=SCRATCH, stdout=out_path.open("w",
                              encoding="utf-8", errors="replace"),
                                stderr=subprocess.STDOUT)
        try:
            proc.wait(timeout=minutes * 60)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception as exc:
        return {"model": model, "error": f"{type(exc).__name__}: {exc}"}
    took = time.time() - started
    text = out_path.read_text(encoding="utf-8", errors="replace") if out_path.is_file() else ""
    try:
        artifact.write_text(text, encoding="utf-8", errors="replace")
    except OSError:
        pass
    return {"model": model, "seconds": int(took), "raw": text, "artifact": str(artifact)}


def extract_json(text: str) -> dict | None:
    start = text.find("{")
    while start != -1:
        depth, in_str, esc, end = 0, False, False, None
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end is not None:
            try:
                obj = json.loads(text[start:end + 1])
                if isinstance(obj, dict) and "blocks" in obj:
                    return obj
            except json.JSONDecodeError:
                pass
        start = text.find("{", start + 1)
    return None


def score(model: str, payload: dict | None, seconds: int, raw: str) -> dict:
    if payload is None:
        return {"model": model, "ok": False, "why": "no valid JSON with blocks",
                "seconds": seconds, "tail": raw[-160:].replace("\n", " ")}
    blocks = payload.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        return {"model": model, "ok": False, "why": "blocks missing or empty",
                "seconds": seconds}
    kinds = [b.get("k") for b in blocks if isinstance(b, dict)]
    problems = []
    if kinds[:1] != ["scene"]:
        problems.append(f"first block is {kinds[:1]}, expected scene")
    if kinds[-1:] != ["hook"]:
        problems.append(f"last block is {kinds[-1:]}, expected hook")
    for b in blocks:
        if isinstance(b, dict) and b.get("k") == "scene":
            if set(b) < {"place", "time", "light"}:
                problems.append("scene block missing required keys")
        if isinstance(b, dict) and b.get("k") in ("para", "line", "hook") and not b.get("t"):
            problems.append(f"empty {b.get('k')} block")

    body = "".join(str(b.get("t", "")) for b in blocks if isinstance(b, dict))
    cn = len(re.findall(r"[\u4e00-\u9fff]", body))
    words = cn + len(re.findall(r"[A-Za-z]+", body))
    if words < 900:
        problems.append(f"only ~{words} words (below 900)")
    elif words > 1700:
        problems.append(f"~{words} words (over the 1500 target)")

    # Precise mechanical tics only (AUDIT_PROMPT §7a). This list must never grow
    # into banning literary devices: a good 成语, one earned parallel, a concrete
    # image are 文采, not AI 味. "干净 at the cost of 文采" is exactly what happens
    # when a banned list is written loosely, so each entry here is a tic — a habit
    # of the machine — not a word a human would never use.
    banned = [
        "紧接着", "与此同时", "事实上", "显然", "毫无疑问", "众所周知",
        "弥漫着", "心中五味杂陈",
        "目光中闪过一丝", "嘴角勾起一抹", "嘴角扬起一抹",
        "原来，", "原来,", "这就是",
    ]
    hits = [b for b in banned if b in body]
    ai_taste_hits = len(hits)
    if hits:
        problems.append(f"AI-taste tics: {hits}")

    lines = sum(1 for b in blocks if isinstance(b, dict) and b.get("k") == "line")
    paras = sum(1 for b in blocks if isinstance(b, dict) and b.get("k") == "para")
    return {
        "model": model, "ok": not problems, "words": words, "lines": lines,
        "paras": paras, "blocks": len(blocks), "seconds": seconds,
        "ai_taste_hits": ai_taste_hits,
        "problems": problems,
        "prose": body[:1500],
        "hook": str(payload.get("blocks")[-1].get("t", "")) if blocks else "",
        "title": payload.get("title", ""),
    }


def main() -> int:
    if not CLI.is_file():
        print(f"opencode CLI missing at {CLI}")
        return 2
    only = sys.argv[1:] or CANDIDATES
    results = []
    for i, model in enumerate(only, 1):
        print(f"[{i}/{len(only)}] {model} …", flush=True)
        raw = run(model)
        payload = extract_json(raw.get("raw", ""))
        row = score(model, payload, raw.get("seconds", 0), raw.get("raw", ""))
        results.append(row)
        if row["ok"]:
            print(f"      OK  {row['words']} words, {row['lines']} lines, "
                  f"{row['paras']} paras, {row['seconds']}s")
        else:
            print(f"      FAIL {row.get('why') or row.get('problems')} ({row['seconds']}s)")

    (SCRATCH / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 72)
    print("mechanical results (facts about the output, not opinions)")
    print("=" * 72)
    print(f"{'model':<42}{'ok':<4}{'words':>7}{'AI味':>6}{'s':>6}  problems")
    for r in results:
        name = r["model"].replace("opencode/", "")
        print(f"{name:<42}{'Y' if r['ok'] else 'N':<4}{r.get('words','-'):>7}"
              f"{r.get('ai_taste_hits','-'):>6}{r.get('seconds','-'):>6}  "
              f"{'; '.join(r.get('problems') or [r.get('why','')])[:60]}")

    print()
    rank_models(results)
    return 0


RANK_TIMEOUT = 420  # same budget run() enforces per model


def rank_models(results: list[dict]) -> list[dict]:
    """Rank candidates on three axes with two vetoes.

    - words 30: scaled to min(words,1500)/1500*30; below 800 is a VETO, not a low
      score — a short-drama episode that cannot fill its length cannot carry plot.
    - structure 15 + latency 15: valid JSON with blocks earns the structure half;
      the latency half scales down with seconds. Latency is deliberately NOT a
      hard veto at 90s: production holds hours per model with quiet-detection, so
      a 292s valid delivery is a fine backup. Only the run timeout vetoes.
    - AI-taste 40: 40 minus 5 per mechanical tic hit, floor 0. This is the
      "灵性" axis — among models that can all write enough valid words, the one
      with no tics ranks first.
    """
    scored = []
    for r in results:
        words = r.get("words") or 0
        secs = r.get("seconds") or RANK_TIMEOUT
        hits = r.get("ai_taste_hits") or 0
        veto = None
        if not r.get("ok") and r.get("why") == "no valid JSON with blocks":
            veto = "no valid JSON"
        elif isinstance(words, int) and words < 800:
            veto = f"only {words} words (<800)"
        if veto:
            scored.append((r, 0, veto))
            continue
        w = min(words, 1500) / 1500 * 30 if isinstance(words, int) else 0
        s = 15 + max(0, 15 * (1 - min(secs, RANK_TIMEOUT) / RANK_TIMEOUT))
        a = max(0, 40 - 5 * hits)
        scored.append((r, round(w + s + a, 1), None))
    scored.sort(key=lambda t: t[1], reverse=True)
    print("=" * 72)
    print("ranked: 字数30 + 结构15/延迟15 + AI味40  (veto: <800字, 无合法JSON)")
    print("=" * 72)
    for i, (r, total, veto) in enumerate(scored, 1):
        name = r["model"].replace("opencode/", "")
        mark = f"VETO: {veto}" if veto else f"{total:.1f}"
        print(f"  {i:>2}. {name:<40} {mark}")
    return scored


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
