"""Analyze recent published scenes for recurring writing-quality problems.

Walks sites/tinghe-archive/public/data/chapters/c*.json in order, computes
cheap signals per scene, aggregates the failure-mode counts and prints a
report. Read-only - never writes anything.

Signal heuristics (all cheap, all language-light):
- dialogue_density = dialogue lines / total lines
- sensory_lines = count of lines that name at least one sensory cue
  (sight: 看/望/盯/亮/暗/色/光, sound: 声/响/听/鸣/沉/静/哑, touch: 凉/
  暖/烫/冷/疼/僵/痒, smell/taste: 味/香/臭/腥/膻, body: 心跳/出汗/喘/抖/僵)
- line_avg_chars = total non-empty chars / non-empty line count
- redundancy = number of near-duplicate adjacent short sentences (same
  opening trigram or repeated leading character)
- env_first_paragraph_share = chars in the first <p> / total chars
- empty_paragraphs = number of <p></p>
- dialogue_monoculture = fraction of dialogue lines that start with the
  same leading character (e.g. 周培：周培：周培)
- phase_skip_pingpong = quick back-and-forth (>=6 alternating single-line
  turns in a window)
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from pathlib import Path

CHAPTERS = Path("sites/tinghe-archive/public/data/chapters")
WINDOW = 60
DIALOGUE_RE = re.compile(r"^\s*[^：:\s]{1,8}[：:]\s*")
SIGHT = "看望盯亮暗色光影闪烁雪白黑红灰雾光"
SOUND = "声响听鸣沉默哑嘶啸啼静雷风吹号钟鼓"
TOUCH = "凉暖烫冷疼僵痒黏滑糙湿汗颤抖喘热"
SMELL = "味香臭腥膻腥气味"
BODY = "心跳出汗喘气颤抖僵冷手心胸膛后背咽"
SENSORY = SIGHT + SOUND + TOUCH + SMELL + BODY
P_RE = re.compile(r"<p(\s[^>]*)?>(.*?)</p\s*>", re.S | re.I)
BR_RE = re.compile(r"<br\s*/?>", re.I)


def visible(line: str) -> str:
    return re.sub(r"<[^>]+>", "", line).strip()


def line_kind(line: str) -> str:
    v = visible(line)
    if not v:
        return "blank"
    if DIALOGUE_RE.match(v):
        return "dialogue"
    return "narration"


def sensory(line: str) -> bool:
    return any(ch in SENSORY for ch in visible(line))


def near_dup(lines: list[str]) -> int:
    sigs = [visible(l)[:6] for l in lines if visible(l)]
    counts = Counter(sigs)
    return sum(c - 1 for c in counts.values() if c > 1)


def alt_pings(lines: list[str], window: int = 8) -> int:
    """Count overlapping windows of size `window` with high alternation."""
    kinds = [line_kind(l) for l in lines]
    score = 0
    for i in range(len(kinds) - window):
        chunk = kinds[i : i + window]
        switches = sum(1 for a, b in zip(chunk, chunk[1:]) if a != b and a != "blank")
        if switches >= window - 2:
            score += 1
    return score


def report():
    files = sorted(CHAPTERS.glob("c*.json"))
    if not files:
        print("no chapter files found")
        return
    sample = files[-WINDOW:]

    dialogue_density = []
    sensory_rate = []
    line_lens = []
    dups = []
    pings = []
    env_share = []
    mono_rates = []
    empty_p = []
    dialogue_only_share = []
    short_dialogue_runs = []

    for path in sample:
        payload = json.loads(path.read_text(encoding="utf-8"))
        html = payload.get("html") or ""
        paragraphs = []
        for m in P_RE.finditer(html):
            body = m.group(2)
            if "<div" in body:
                continue
            paragraphs.append([visible(l) for l in BR_RE.split(body)])
        flat = [v for p in paragraphs for v in p if v]
        if not flat:
            continue

        kinds = [line_kind(l) for l in flat]
        d = sum(1 for k in kinds if k == "dialogue")
        n = sum(1 for k in kinds if k == "narration")
        b = sum(1 for k in kinds if k == "blank")
        total = max(1, d + n)

        dialogue_density.append(d / total)
        sensory_rate.append(sum(1 for l in flat if sensory(l)) / total)
        line_lens.extend(len(v) for v in flat)
        dups.append(near_dup(flat))
        pings.append(alt_pings(flat))

        if paragraphs:
            env_chars = sum(len(v) for v in paragraphs[0])
            total_chars = sum(len(v) for p in paragraphs for v in p)
            env_share.append(env_chars / max(1, total_chars))

        leading = Counter(v.split("：", 1)[0] for v in flat if "：" in v)
        top_speaker, top_count = (leading.most_common(1) or [(None, 0)])[0]
        d_total = max(1, sum(1 for k in kinds if k == "dialogue"))
        if top_speaker and top_count >= 4:
            mono_rates.append(top_count / d_total)
        else:
            mono_rates.append(0.0)

        empty_p.append(sum(1 for p in paragraphs if not any(v for v in p)))

        if d and not n:
            dialogue_only_share.append(1.0)
        else:
            dialogue_only_share.append(0.0)

        # Count consecutive single-character turns as a "ping-pong" run
        run = 0
        max_run = 0
        for l in flat:
            v = visible(l)
            if DIALOGUE_RE.match(v) and len(v.split("：", 1)[1].strip()) < 6:
                run += 1
                max_run = max(max_run, run)
            else:
                run = 0
        short_dialogue_runs.append(max_run)

    print(f"sample_size={len(sample)}")
    print(f"dialogue_density median={statistics.median(dialogue_density):.2f} mean={statistics.mean(dialogue_density):.2f}")
    print(f"sensory_rate median={statistics.median(sensory_rate):.2f} mean={statistics.mean(sensory_rate):.2f}")
    print(f"line_len_chars median={statistics.median(line_lens):.0f} mean={statistics.mean(line_lens):.0f}")
    print(f"near_dup_neighbors mean={statistics.mean(dups):.2f} max={max(dups)}")
    print(f"alt_pingpong_windows mean={statistics.mean(pings):.2f} max={max(pings)}")
    print(f"env_first_p_share median={statistics.median(env_share):.2f} mean={statistics.mean(env_share):.2f}")
    print(f"mono_speaker_share mean={statistics.mean(mono_rates):.2f} max={max(mono_rates):.2f}")
    print(f"empty_paragraphs total={sum(empty_p)} max={max(empty_p)}")
    print(f"dialogue_only_chapters={int(sum(dialogue_only_share))}")
    print(f"long_short_dialogue_runs mean={statistics.mean(short_dialogue_runs):.1f} max={max(short_dialogue_runs)}")
    print("---")
    # Flag worst-offenders per axis
    worst = sorted(zip(dialogue_density, sample), key=lambda x: x[0])[:5]
    print("lowest dialogue density:")
    for v, p in worst:
        print(f"  {p.stem}: {v:.2f}")
    worst2 = sorted(zip(sensory_rate, sample), key=lambda x: x[0])[:5]
    print("lowest sensory rate:")
    for v, p in worst2:
        print(f"  {p.stem}: {v:.2f}")
    worst3 = sorted(zip(mono_rates, sample), key=lambda x: -x[0])[:5]
    print("highest mono-speaker share:")
    for v, p in worst3:
        print(f"  {p.stem}: {v:.2f}")
    worst4 = sorted(zip(dups, sample), key=lambda x: -x[0])[:5]
    print("most near-duplicate neighbours:")
    for v, p in worst4:
        print(f"  {p.stem}: {v}")
    worst5 = sorted(zip(env_share, sample), key=lambda x: x[0])[:5]
    print("smallest environment share:")
    for v, p in worst5:
        print(f"  {p.stem}: {v:.2f}")


if __name__ == "__main__":
    report()