"""Cheap failure-mode signals for canon scenes.

Used by both:
- tools/analyze_failure_modes.py (read-only report over published HTML)
- tools/canon_scene_pass.py judge() (rejects the next scene when its
  signals exceed the same thresholds)

Signals are deliberately language-light (single characters / simple regex)
so a quick text scan is enough. Operating on the markdown ``scene["text"]``
is supported; on the published HTML, paragraph breaks become ``<p>`` and
``<br>`` so we use the same line-splitting helper.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

# Dialogue cue: a short name + Chinese full-width colon, then content that
# actually contains a quote pair (the hallmark of spoken text in this canon).
# Exclude narrator/roster labels: 环境：, 在场：, 不在场：, 本场变化：,
# 其他人：, and short single-name roster entries (顾良：已离园 / name：未出场).
QUOTE_RE = re.compile(r"[“”‘’「」]")
NAME_LABEL_RE = re.compile(
    r"^\s*(?:环境|在场|不在场|本场变化|其他人)[:：]"
)
ROSTER_LINE_RE = re.compile(
    r"^\s*[^：:\s]{1,8}[:：]"
    r"\s*(?:未出场|不在场|已离园|在场|不在|离场|退场|已出场|未到场)"
    r"\s*$"
)
# Either: short name + colon + quote (the classic dialogue line), OR
# short name + colon + content + a quote somewhere in the line. We don't
# gate on quote position because this canon often drops the quote when
# the speaker cue alone is clear (e.g. "周培：看着灯盏，沉默不语。").
DIALOGUE_RE = re.compile(
    r"^\s*(?!环境[:：]|在场[:：]|不在场[:：]|本场变化[:：]|其他人[:：])"
    r"[^：:\s]{1,8}[:：]"
)
# Sensory lexicon — single Chinese characters; cheap and high recall.
SIGHT = "看望盯亮暗色光影闪烁雪白黑红灰雾"
SOUND = "声响听鸣沉默哑嘶啸啼静雷号钟鼓风声"
TOUCH = "凉暖烫冷疼僵痒黏滑糙湿汗颤抖喘热"
SMELL = "味香臭腥膻气"
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


# Within a long narrative line, look for embedded dialogue cues:
# "吴妈说：", "阿寿问：", "周培低声答：" etc. The pattern is
# 1-6 Chinese chars (the speaker) followed by 说/问/答/回/笑/喊/叫/低声/抬头
# then a Chinese full-width colon.
INLINE_DIALOGUE_RE = re.compile(
    r"([\u4e00-\u9fa5]{1,6})"
    r"(?:说|问|答|回|笑|喊|叫|低声|抬头|沉声)"
    r"[：:]"
)

# Stop-words that often sit between a 1-2 char speaker prefix and the verb
# (e.g. "周培低声说" — the "低声" is a verb qualifier, not part of the name).
SPEAKER_PREFIX_RE = re.compile(
    r"([\u4e00-\u9fa5]{1,6})"
    r"(?:又)?"
    r"(?:低声|沉声|抬头)?"
    r"(?:说|问|答|回|笑|喊|叫)"
    r"[：:]"
)


def count_inline_dialogue(line: str) -> int:
    """How many distinct speaker turns are inside a narration line."""
    return len(INLINE_DIALOGUE_RE.findall(visible(line)))


def sensory(line: str) -> bool:
    return any(ch in SENSORY for ch in visible(line))


def near_dup(lines: list[str]) -> int:
    sigs = [visible(l)[:6] for l in lines if visible(l)]
    counts = Counter(sigs)
    return sum(c - 1 for c in counts.values() if c > 1)


def alt_pings(lines: list[str], window: int = 8) -> int:
    kinds = [line_kind(l) for l in lines]
    score = 0
    for i in range(len(kinds) - window):
        chunk = kinds[i : i + window]
        switches = sum(1 for a, b in zip(chunk, chunk[1:]) if a != b and a != "blank")
        if switches >= window - 2:
            score += 1
    return score


def iter_lines(text_or_html: str) -> list[str]:
    """Return logical lines from markdown or published HTML.

    Markdown: split by ``\\n``; paragraphs separated by blank lines.
    HTML:    split each <p>...</p> by <br>.
    """
    if "<p" in text_or_html and "</p" in text_or_html:
        out: list[str] = []
        for m in P_RE.finditer(text_or_html):
            body = m.group(2)
            if "<div" in body:
                continue
            out.extend(BR_RE.split(body))
        return out
    return text_or_html.split("\n")


def compute_signals(text_or_html: str) -> dict[str, float]:
    """Return all signals at once. Caller picks thresholds."""
    flat = [v for v in (visible(l) for l in iter_lines(text_or_html)) if v]
    if not flat:
        return {
            "dialogue_density": 0.0,
            "sensory_rate": 0.0,
            "near_dup": 0,
            "alt_pingpong": 0,
            "mono_speaker_share": 0.0,
            "empty_paragraphs": 1,
            "dialogue_only": 1,
            "short_dialogue_runs": 0,
            "lines": 0,
        }

    kinds = [line_kind(l) for l in flat]
    d = sum(1 for k in kinds if k == "dialogue")
    n = sum(1 for k in kinds if k == "narration")
    # Count inline dialogue cues inside narration lines (speaker said/quoted
    # lines that got concatenated into one <br>-less paragraph). The
    # narration line itself still counts as 1 turn.
    inline_d = sum(count_inline_dialogue(l) for l in flat if not DIALOGUE_RE.match(visible(l)))
    d_eff = d + inline_d
    n_eff = n
    total = max(1, d_eff + n_eff)

    leading_inline = Counter(
        m.group(1) for l in flat for m in INLINE_DIALOGUE_RE.finditer(visible(l))
    )
    leading_prefix = Counter(
        m.group(1) for l in flat for m in SPEAKER_PREFIX_RE.finditer(visible(l))
    )
    leading_top = Counter(v.split("：", 1)[0] for v in flat if DIALOGUE_RE.match(v))
    # Merge prefix-only counts (e.g. "周培低声说" and "周培说" both attribute to 周培)
    # by adding prefix counts into the same speaker name.
    merged = Counter()
    for spk, n in (leading_inline | leading_top).items():
        merged[spk] += n
    for spk, n in leading_prefix.items():
        merged[spk] += n
    top_speaker, top_count = (
        merged.most_common(1)[0] if merged else (None, 0)
    )
    d_total = max(1, d_eff)
    mono = (top_count / d_total) if top_speaker and top_count >= 4 else 0.0

    paragraphs_html = re.findall(r"<p[^>]*>(.*?)</p\s*>", text_or_html, re.S | re.I)
    empty_p = 0
    if paragraphs_html:
        for body in paragraphs_html:
            lines = [visible(l) for l in BR_RE.split(body)]
            if not any(v for v in lines):
                empty_p += 1
    elif "<p" not in text_or_html:
        # Markdown: paragraphs are blank-line separated.
        empty_p = sum(1 for blk in text_or_html.split("\n\n") if not blk.strip())

    run = 0
    max_run = 0
    for l in flat:
        v = visible(l)
        if DIALOGUE_RE.match(v) and len(v.split("：", 1)[1].strip()) < 6:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0

    return {
        "dialogue_density": d_eff / total,
        "sensory_rate": sum(1 for l in flat if sensory(l)) / max(1, d_eff + n_eff),
        "near_dup": near_dup(flat),
        "alt_pingpong": alt_pings(flat),
        "mono_speaker_share": mono,
        "empty_paragraphs": empty_p,
        "dialogue_only": 1 if (d_eff and not n_eff) else 0,
        "short_dialogue_runs": max_run,
        "lines": len(flat),
        "dialogue_turns": d_eff,
        "narration_turns": n_eff,
    }


# Thresholds used by judge(). Chosen from the analyze_failure_modes.py
# recent-60 distribution (median 0.50 dialogue, 0.95 sensory; max
# 3 near-dup, 4 alt-pingpong, 0.57 mono-share) — tuned to flag the worst
# offenders without rejecting healthy scenes.
THRESHOLDS = {
    "dialogue_density_min": 0.20,
    "sensory_rate_min": 0.50,
    "near_dup_max": 4,
    "alt_pingpong_max": 5,
    "mono_speaker_share_max": 0.55,
    "empty_paragraphs_max": 0,
    "dialogue_only_max": 0,
    "short_dialogue_runs_max": 3,
}


def flag_failures(signals: dict[str, float]) -> list[str]:
    fails: list[str] = []
    if signals["dialogue_density"] < THRESHOLDS["dialogue_density_min"]:
        fails.append("low_dialogue_density")
    if signals["sensory_rate"] < THRESHOLDS["sensory_rate_min"]:
        fails.append("low_sensory_rate")
    if signals["near_dup"] > THRESHOLDS["near_dup_max"]:
        fails.append("near_dup:" + str(signals["near_dup"]))
    if signals["alt_pingpong"] > THRESHOLDS["alt_pingpong_max"]:
        fails.append("alt_pingpong:" + str(signals["alt_pingpong"]))
    if signals["mono_speaker_share"] > THRESHOLDS["mono_speaker_share_max"]:
        fails.append("mono_speaker:" + f"{signals['mono_speaker_share']:.2f}")
    if signals["empty_paragraphs"] > THRESHOLDS["empty_paragraphs_max"]:
        fails.append("empty_paragraphs:" + str(signals["empty_paragraphs"]))
    if signals["dialogue_only"] > THRESHOLDS["dialogue_only_max"]:
        fails.append("dialogue_only_chapter")
    if signals["short_dialogue_runs"] > THRESHOLDS["short_dialogue_runs_max"]:
        fails.append("short_dialogue_run:" + str(signals["short_dialogue_runs"]))
    return fails