#!/usr/bin/env python3
"""Build context_bundle.md for a single work.

Reads all published episodes from public/data/originals/<work_id>/epNN.json,
extracts text from HTML, and writes a markdown bundle to
originals_source/<work_id>/context_bundle.md with:
  - per-episode summary (entities, state changes, clues, time/place)
  - full text of the most recent 3 episodes
  - full text of all episodes if total <= 5
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from tools.atomic_io import atomic_write_text

PUBLIC_ORIGINALS = Path("public/data/originals")
SOURCE = Path("originals_source")

HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def strip_episode(context: str, ep_id: str) -> str:
    """Remove one episode's own section from a context bundle.

    The bundle is built from published data, so a freshly built draft shows up
    inside the "previous chapters" excerpt. Left in, the auditor treats the new
    episode as its own prior text and flags it as a duplicate or a retcon of
    itself. Sections are delimited by "### ep<NN>" headings.
    """
    pattern = re.compile(
        r"^### " + re.escape(ep_id) + r"\b.*?(?=^### |\Z)",
        re.DOTALL | re.MULTILINE,
    )
    stripped, hits = pattern.subn("", context)

    # The summary table also carries a row per episode; leaving it in keeps the
    # episode's opening lines visible as "prior context".
    row = re.compile(r"^\|\s*" + re.escape(ep_id) + r"\s*\|.*$\n?", re.MULTILINE)
    stripped, rows = row.subn("", stripped)

    if hits or rows:
        stripped = re.sub(r"\n{3,}", "\n\n", stripped).rstrip() + "\n"
    return stripped


def prior_context(context: str, ep_id: str, ep_no: int | None = None) -> tuple[str, list[int]]:
    """Return audit context containing only episodes strictly earlier than `ep_no`.

    Why this exists (found 2026-10-07): the bundle is built per *work* and keeps
    full text for the most recent N episodes. `strip_episode` removes only the
    audited episode, so auditing a non-latest episode left the newer ones behind
    as "previous chapters". The auditor then read ep06..ep08 as backstory for
    ep05 and produced verdicts like "the new chapter comes after ep09 yet
    regresses to ep05's progress" — comparing an episode against its own sequel.
    Roughly a quarter of the catalogue was failed on that basis, and seven
    episodes had already been quarantined because of it.

    So the rule for an audit is stricter than for a writer: prior context must be
    strictly earlier text. Everything with number >= ep_no is dropped — sections,
    summary-table rows, and the header lines that advertise episode ranges.

    Returns (text, dropped_numbers) so the caller can log what was removed; a
    drop list that is not empty is expected and healthy, not an error.
    """
    if ep_no is None:
        digits = "".join(ch for ch in ep_id if ch.isdigit())
        ep_no = int(digits) if digits else 0

    dropped: list[int] = []

    def _num(token: str) -> int | None:
        d = "".join(ch for ch in token if ch.isdigit())
        return int(d) if d else None

    # Drop whole "### epNN ..." sections at or after the audited episode.
    def _section(match: re.Match[str]) -> str:
        num = _num(match.group(1))
        if num is not None and num >= ep_no:
            dropped.append(num)
            return ""
        return match.group(0)

    text = re.sub(r"^### (ep\d+)\b.*?(?=^### |\Z)", _section, context,
                  flags=re.DOTALL | re.MULTILINE)

    # Drop the matching summary-table rows; they leak beat hints and titles.
    def _row(match: re.Match[str]) -> str:
        num = _num(match.group(1))
        if num is not None and num >= ep_no:
            return ""
        return match.group(0)

    text = re.sub(r"^\|\s*(ep\d+)\s*\|.*$\n?", _row, text, flags=re.MULTILINE)

    # Header lines name episode ranges ("最近 3 集完整正文（ep06–ep08）"). Leaving
    # them tells the auditor how many chapters exist in total, which is itself a
    # forward reference when auditing an early one.
    text = re.sub(r"^.*(?:最近|更早).*(?:完整正文|只提供标题).*$\n?", "", text,
                  flags=re.MULTILINE)
    text = re.sub(r"^已发布章节数[:：].*$\n?", "", text, flags=re.MULTILINE)

    framing = (
        "## 本次审核对象\n\n"
        f"- 待审新集：**第 {ep_no} 集**（{ep_id}）\n"
        f"- 本文其余全部内容都属于第 {ep_no} 集**之前**的剧情，是它的前情。\n"
        "- 若文中出现晚于第 {n} 集的集，那是打包错误，不作为连续性依据。\n"
        "- 不要要求本集包含它自己之后才会发生的事。\n\n"
    ).format(n=ep_no)
    text = re.sub(r"\n{3,}", "\n\n", text).lstrip("\n")
    return framing + text, sorted(set(dropped))


def strip_pending(context: str) -> str:
    """Remove the pending-facts section from an audit context.

    Pending facts come from unshipped episodes. An audit that sees them judges
    the new episode against claims derived from unshipped drafts — the same
    self-comparison bug strip_episode fixes for episode text. Writers keep
    reading pending (it stays in context_bundle.md); only audits strip it.
    The section is always last, so cut to end of file.
    """
    cut = context.find("## 待确认事实")
    if cut < 0:
        return context
    return context[:cut].rstrip() + "\n"


def strip_html(html: str) -> str:
    text = HTML_TAG_RE.sub(" ", html)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def extract_episode_text(html: str) -> str:
    """Convert episode HTML to readable plain text for context."""
    # Keep structural markers
    text = html
    text = text.replace("<h3>", "\n## 场景：").replace("</h3>", "\n")
    text = text.replace("<p><b>在场</b>：", "\n**在场**：")
    text = text.replace("<p><b>未出场</b>：", "\n**未出场**：")
    text = text.replace("<p><b>钩子</b>：", "\n**钩子**：")
    text = text.replace("<p><em>", "\n*")
    text = text.replace("</em></p>", "*\n")
    text = text.replace("<p>", "\n")
    text = text.replace("</p>", "\n")
    text = text.replace("<b>", "**")
    text = text.replace("</b>", "**")
    return strip_html(text)


def summarize_episode(ep_id: str, ep_no: int, ep_title: str, html: str) -> dict[str, Any]:
    """Extract structured summary from episode HTML."""
    text = strip_html(html)

    # Simple heuristics for entity/state extraction
    characters = set()
    for match in re.finditer(r"\*\*([^：\*]+)\*\*[:：]", text):
        name = match.group(1).strip()
        if 1 <= len(name) <= 12 and not any(kw in name for kw in ["场景", "钩子", "在场", "未出场"]):
            characters.add(name)

    # Extract beat from title and first paragraph
    beat_hint = ""
    first_para = text.split("\n")[0] if text else ""
    if first_para:
        beat_hint = first_para[:200]

    return {
        "episode": ep_id,
        "no": ep_no,
        "title": ep_title,
        "characters": sorted(characters),
        "beat_hint": beat_hint,
        "word_count": len(text),
    }


def build_context_bundle(work_id: str) -> Path:
    """Generate context_bundle.md for a work. Returns the written file path."""
    pub_dir = PUBLIC_ORIGINALS / work_id
    if not pub_dir.is_dir():
        return None

    eps = []
    for p in sorted(pub_dir.glob("ep*.json")):
        # Every published episode goes in. A previous version skipped ep04
        # whenever ep03 was absent — a hardcoded patch for one work that became a
        # trap once `quarantine.json` could hold a mid-series episode: with fanguan's
        # ep03 held back, its ep04 vanished from the bundle, so every later audit and
        # every repair was blind to a real chapter without saying so. A numbering gap
        # is information; silently dropping the chapter after it is not.
        data = json.loads(p.read_text(encoding="utf-8"))
        # Older payloads omitted `no`; the filename is authoritative then, so a
        # stale build can never collapse every episode onto number 0.
        no = data.get("no")
        if no is None:
            digits = "".join(ch for ch in p.stem if ch.isdigit())
            no = int(digits) if digits else 0
        eps.append({
            "id": data["id"],
            "no": int(no),
            "title": data["title"],
            "html": data["html"],
        })

    eps.sort(key=lambda x: x["no"])
    if not eps:
        return None

    # Build summaries
    summaries = []
    full_texts = []
    for ep in eps:
        clean = extract_episode_text(ep["html"])
        summaries.append(summarize_episode(ep["id"], ep["no"], ep["title"], ep["html"]))
        full_texts.append({
            "id": ep["id"],
            "no": ep["no"],
            "title": ep["title"],
            "text": clean,
        })

    # Decide what to include in full
    total_eps = len(eps)
    recent_n = 3 if total_eps > 5 else total_eps
    recent_start = max(0, total_eps - recent_n)

    # Write bundle
    bundle_path = SOURCE / work_id / "context_bundle.md"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"# {work_id} · 前文上下文包")
    lines.append(f"生成时间：{datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}")
    lines.append(f"已发布集数：{total_eps}")
    lines.append(f"完整保留最近 {recent_n} 集（ep{recent_start+1:02d}–ep{total_eps:02d}），其余仅摘要。")
    lines.append("")

    # Structured summary table
    lines.append("## 剧情状态摘要（所有集）")
    lines.append("")
    lines.append("| 集号 | 标题 | 出场人物 | 字数 | 首段提示 |")
    lines.append("|------|------|----------|------|----------|")
    for s in summaries:
        chars = "、".join(s["characters"][:6]) + ("..." if len(s["characters"]) > 6 else "")
        lines.append(f"| ep{s['no']:02d} | {s['title']} | {chars} | {s['word_count']} | {s['beat_hint']} |")
    lines.append("")

    # Full text of recent episodes
    lines.append(f"## 最近 {recent_n} 集完整正文（按集号顺序）")
    lines.append("")
    for ft in full_texts[recent_start:]:
        lines.append(f"### ep{ft['no']:02d} · {ft['title']}")
        lines.append("")
        lines.append(ft["text"])
        lines.append("")

    # If total <= 5, also include earlier full texts
    if total_eps <= 5:
        lines.append("## 早期集完整正文（因总集数 ≤5）")
        lines.append("")
        for ft in full_texts[:recent_start]:
            lines.append(f"### ep{ft['no']:02d} · {ft['title']}")
            lines.append("")
            lines.append(ft["text"])
            lines.append("")

    # Fact table: hand-maintained hard constraints (originals_source/<work>/facts.json).
    # It exists because the writer's memory of prior facts is weak — 20+ continuity
    # breaks in one batch (genders, identities, numbers, years). Whatever is listed
    # here outranks a fresh invention. A missing facts.json only warns; the bundle
    # must still build for works that do not have one yet.
    facts_path = SOURCE / work_id / "facts.json"
    facts = None
    if facts_path.is_file():
        try:
            facts = json.loads(facts_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARNING: {work_id}/facts.json unreadable ({exc}); bundle built without it")
            facts = None
        if facts:
            lines.append("## 事实表（写新集与审核的硬约束，优先级高于临场发挥）")
            lines.append("")

            # --- 压力轴（2026-10-11 新增）--------------------------------------------
            # Every other fact field says "do not break this" or "finish that".
            # None says "this must be harder than last time", so nothing stopped the
            # catalogue sliding from 爽文 into investigation once the premise grew a
            # conspiracy to uncover. Measured 2026-10-11: 升级/阶梯/对手/反派/地图/阶段
            # appear zero times in all five works' facts.json.
            #
            # Rendered ABOVE open_hooks on purpose. open_hooks is a list of questions
            # waiting to be answered, so an episode that honours it looks into
            # something; read after the pressure axis, the same hook becomes leverage
            # instead of an investigation.
            pressure = facts.get("pressure") or []
            if isinstance(pressure, dict):
                pressure = [pressure]
            if not pressure:
                lines.append("### ⚠ 压力轴未填写（pressure 段为空或缺失）")
                lines.append("")
                lines.append("本作品缺少「对手/赌注/上一轮赢下什么/代价是什么」的记录。")
                lines.append("按 DAILY_DIRECTIVE 8b：这一轴为空的期间，写新集容易退回"
                             "「继续查上一件事」。若要补，写成一段记录：")
                lines.append("")
                lines.append("```json")
                lines.append('"pressure": [{"arc": 2, "opponent": "谁在压她", '
                             '"stake": "拿什么做赌注", "deadline": "期限或时限", '
                             '"last_won": "上一轮她赢下了什么", '
                             '"cost": "这个赢的代价，下一轮要还", '
                             '"next_must_differ": "接下来 3 集里必须不同的那一项"}]')
                lines.append("```")
                lines.append("")
            else:
                lines.append("### 压力轴（爽文的引擎：压 → 当场翻回来 → 代价留到下一轮）")
                lines.append("")
                for rec in pressure:
                    # Inlined rather than calling `_flat`, which is defined below
                    # this block and is unbound at this point. Same unwrap it does:
                    # a hand-edited record wrapped as {"entry": {...}} appeared in
                    # the wild and crashed the daily publish when indexed directly.
                    if isinstance(rec, dict) and "entry" in rec \
                            and isinstance(rec.get("entry"), dict):
                        merged = dict(rec["entry"])
                        merged.update({k: v for k, v in rec.items() if k != "entry"})
                        norm = merged
                    else:
                        norm = rec
                    if not isinstance(norm, dict):
                        continue
                    bits = []
                    # An empty cost is load-bearing information, not a missing
                    # field. §8b bridges arcs with "what she won here is why she
                    # is under more pressure next arc", so silence would read as
                    # "no cost" — the reading that lets the arc repeat itself.
                    if not str(norm.get("cost") or "").strip():
                        bits.append("代价：未填（下一轮会偏向重复旧形状）")
                    for key, label in (
                        ("arc", "轮次"), ("opponent", "对手"), ("stake", "赌注"),
                        ("how_won", "怎么赢"),
                        ("deadline", "期限"), ("last_won", "上一轮赢下"),
                        ("cost", "代价（下一轮要还）"),
                        ("next_must_differ", "接下来必须不同的"),
                    ):
                        val = str(norm.get(key) or "").strip()
                        if val:
                            bits.append(f"{label}：{val}")
                    if bits:
                        lines.append("- " + "；".join(bits) + "。")
                lines.append("")

            def _flat(rec):
                """Normalize one fact record.

                Records are hand-edited, and a stray ``{"entry": {...}}`` wrapper
                appeared in the wild (liufang, 2026-10-07). Hard-indexing ``rec['name']``
                turned that typo into a crash that aborted the whole daily publish.
                Unwrap first, then let the caller decide what to do with a record
                that still lacks its required keys.
                """
                if not isinstance(rec, dict):
                    return None
                if "name" not in rec and isinstance(rec.get("entry"), dict):
                    merged = dict(rec["entry"])
                    merged.update({k: v for k, v in rec.items() if k != "entry"})
                    return merged
                return rec

            def _rows(records, required, render):
                """Render fact records, skipping malformed ones with a warning.

                A dropped fact is a real continuity risk, so every skip is reported
                on stdout and counted into the bundle header — but it never stops
                the bundle. Publishing already-audited episodes outranks one bad
                hand-edited row.
                """
                out, dropped = [], []
                for rec in records or []:
                    norm = _flat(rec)
                    missing = [k for k in required if not (norm or {}).get(k)]
                    if norm is None or missing:
                        dropped.append(f"{rec!r} missing={missing}")
                        continue
                    out.append(render(norm))
                return out, dropped

            all_dropped = []

            rows, dropped = _rows(
                facts.get("characters", []), ("name",),
                lambda c: (
                    f"- {c['name']}（{c['pronoun']}）：{c.get('role', '')}"
                    if c.get("pronoun")
                    else f"- {c['name']}（无确立代词，只许用名字/职务指代）：{c.get('role', '')}"
                ),
            )
            all_dropped += dropped
            lines.append("人物（代词是判卷依据，用错即 CHARACTER_INCONSISTENCY）：")
            lines.extend(rows)
            lines.append("")

            rows, dropped = _rows(
                facts.get("numbers", []), ("value", "meaning"),
                lambda n: f"- 数字 {n['value']} = {n['meaning']}（{n.get('source', '')}）",
            )
            all_dropped += dropped
            lines.extend(rows)
            lines.append("")

            rows, dropped = _rows(
                facts.get("timeline", []), ("when", "event"),
                lambda t: f"- 时间 {t['when']}：{t['event']}",
            )
            all_dropped += dropped
            lines.extend(rows)
            lines.append("")

            rows, dropped = _rows(
                facts.get("props", []), ("item", "holder"),
                lambda p: f"- 道具 {p['item']} 在 {p['holder']}（{p.get('state', '')}）",
            )
            all_dropped += dropped
            lines.extend(rows)
            lines.append("")

            # Established facts, promoted from the author's own pending entries.
            # This section did not exist before 2026-10-11 because promote_facts
            # could not classify anything: the contract never asked the author for
            # a `section` key, so every entry was skipped, 65 facts piled up, and
            # none of them ever reached the tables the writer actually reads.
            est_rows, est_dropped = [], []
            for rec in facts.get("facts", []):
                flat = _flat(rec) if not isinstance(rec, str) else rec
                if isinstance(flat, str):
                    text, source = flat.strip(), ""
                elif isinstance(flat, dict):
                    text, source = "", str(flat.get("source") or "")
                    for key in ("fact", "entry", "text", "note", "desc"):
                        val = flat.get(key)
                        if isinstance(val, str) and val.strip():
                            text = val.strip()
                            break
                else:
                    text, source = "", ""
                if not text:
                    est_dropped.append(repr(rec))
                    continue
                est_rows.append(f"- {text}" + (f"（{source}）" if source else ""))
            all_dropped += est_dropped
            if est_rows:
                lines.append("已确立事实（前文立下的机制与状态，写新集不得推翻）：")
                lines.extend(est_rows)
                lines.append("")

            # Hooks are hand-edited and arrive in three shapes: a bare string,
            # {"hook": ..., "source": ...}, and — after the same stray {"entry": {...}}
            # wrapper that broke the daily publish on 2026-10-07 — a nested one.
            # Formatting the record directly put Python dict literals into the bundle
            # the writer reads, ten of them across the five works:
            #   - 未回收钩子：{'hook': '四楼眉批主人是谁（ep08 …）'}
            #   - 未回收钩子：{'entry': {'hook': '回执背面第二行…'}}
            # `_flat` already normalizes the wrapper for the other fact sections, so
            # reuse it, then take the text and keep the source as a suffix.
            hook_rows, hook_dropped = [], []
            for h in facts.get("open_hooks", []):
                # A bare string must be checked before _flat: _flat returns None
                # for anything that is not a dict, and the first version of this
                # loop fed strings to it and rendered five "- None" bullets.
                rec = h if isinstance(h, str) else _flat(h)
                if isinstance(rec, dict):
                    text = rec.get("hook")
                    if not (isinstance(text, str) and text.strip()):
                        hook_dropped.append(repr(h))
                        continue
                    source = rec.get("source")
                    text = text.strip()
                    if source:
                        text = f"{text}（来自 {source}）"
                elif isinstance(rec, str):
                    text = rec.strip()
                    if not text:
                        hook_dropped.append(repr(h))
                        continue
                else:
                    hook_dropped.append(repr(h))
                    continue
                hook_rows.append(text)

            if hook_rows:
                lines.append("### 未回收钩子（压力轴上的筹码，不是本集任务）")
                lines.append("")
                lines.append("用它们逼对手让步或付代价，**不要**把它们当成"
                             "「这一集去查清楚」的待办清单。")
                lines.append("")
                for text in hook_rows:
                    lines.append(f"- {text}")
                lines.append("")
            if hook_dropped:
                all_dropped += hook_dropped
                print(f"WARNING: {work_id}/facts.json open_hooks with no text: "
                      f"{hook_dropped}")

            for rule in facts.get("never", []):
                lines.append(f"- 铁律：{rule}")
            lines.append("")

            if all_dropped:
                lines.append(
                    f"> 事实表有 {len(all_dropped)} 条记录格式不完整已被跳过，"
                    "这些硬约束本次未进入上下文，请人工补齐："
                )
                for entry in all_dropped:
                    lines.append(f"> - {entry}")
                lines.append("")
                print(f"WARNING: {work_id}/facts.json skipped "
                      f"{len(all_dropped)} malformed record(s): {all_dropped}")

    # Pending facts: appended by the writer from unshipped episodes, promoted
    # only after audit PASS + publish (see promote_facts.py). Writers may read
    # this section as reference; audits MUST NOT see it (run_audit strips it),
    # otherwise an episode would be judged against facts derived from itself
    # or from a draft that never shipped — exactly the 2026-10-05 contamination.
    # This section is always last so the audit strip can cut to end of file.
    pending = (facts or {}).get("pending", []) or []
    if pending:
        lines.append("## 待确认事实（未上线，仅供写作参考，不作审核依据）")
        lines.append("")

        def _pending(entry):
            """Return (label, text) for one pending record — never a dict repr.

            Pending entries are appended by the author model, and the contract has
            never asked it for a `section` key — it only required `source` and
            `awaiting`. So the payload lands under whichever key the model picked
            at the time (`fact`, `entry`, `hook`) and the old fallback printed the
            whole record. By 2026-10-11 that was 65 Python dict literals sitting in
            the bundle the writer reads, e.g. `- [?] {'entry': '回执背面第二行…'}`,
            which is also why promote_facts reported "would promote 0 entries" for
            every one of them.
            """
            if not isinstance(entry, dict):
                return None, str(entry).strip()
            section = entry.get("section")
            if section == "characters":
                return section, (f"{entry.get('name')}"
                                 f"（{entry.get('pronoun') or '无确立代词'}）："
                                 f"{entry.get('role', '')}")
            if section == "numbers":
                return section, f"数字 {entry.get('value')} = {entry.get('meaning', '')}"
            if section == "timeline":
                return section, f"时间 {entry.get('when')}：{entry.get('event')}"
            if section == "props":
                return section, f"道具 {entry.get('item')} 在 {entry.get('holder', '')}"
            if section == "open_hooks":
                return section, str(entry.get("hook") or "")
            for key in ("hook", "fact", "entry", "text", "note"):
                val = entry.get(key)
                if isinstance(val, str) and val.strip():
                    label = "钩子" if key == "hook" else (section or "事实")
                    return label, val.strip()
            return section, ""

        for entry in pending:
            label, text = _pending(entry)
            if not (text or "").strip():
                continue
            awaiting = entry.get("awaiting", "?") if isinstance(entry, dict) else "?"
            prefix = f"[{label}] " if label else ""
            lines.append(f"- {prefix}{text}（待确认：{awaiting}）")
        lines.append("")

    content = "\n".join(lines) + "\n"
    atomic_write_text(bundle_path, content, encoding="utf-8")
    return bundle_path


if __name__ == "__main__":
    import sys
    work_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not work_id:
        print("usage: build_context_bundle.py <work_id>")
        sys.exit(1)
    path = build_context_bundle(work_id)
    if path:
        print(f"OK: {path} ({path.stat().st_size} bytes)")
    else:
        print(f"no published episodes for {work_id}")
        sys.exit(1)