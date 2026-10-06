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
        if p.name == "ep04.json" and not (pub_dir / "ep03.json").exists():
            continue
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
            rows = []
            for c in facts.get("characters", []):
                if c.get("pronoun"):
                    rows.append(f"- {c['name']}（{c['pronoun']}）：{c.get('role', '')}")
                else:
                    rows.append(f"- {c['name']}（无确立代词，只许用名字/职务指代）：{c.get('role', '')}")
            lines.append("人物（代词是判卷依据，用错即 CHARACTER_INCONSISTENCY）：")
            lines.extend(rows)
            lines.append("")
            for n in facts.get("numbers", []):
                lines.append(f"- 数字 {n['value']} = {n['meaning']}（{n.get('source', '')}）")
            lines.append("")
            for t in facts.get("timeline", []):
                lines.append(f"- 时间 {t['when']}：{t['event']}")
            lines.append("")
            for p in facts.get("props", []):
                lines.append(f"- 道具 {p['item']} 在 {p['holder']}（{p.get('state', '')}）")
            lines.append("")
            for h in facts.get("open_hooks", []):
                lines.append(f"- 未回收钩子：{h}")
            lines.append("")
            for rule in facts.get("never", []):
                lines.append(f"- 铁律：{rule}")
            lines.append("")

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
        for entry in pending:
            section = entry.get("section", "?")
            if section == "characters":
                desc = f"{entry.get('name')}（{entry.get('pronoun') or '无确立代词'}）：{entry.get('role', '')}"
            elif section == "numbers":
                desc = f"数字 {entry.get('value')} = {entry.get('meaning', '')}"
            elif section == "timeline":
                desc = f"时间 {entry.get('when')}：{entry.get('event')}"
            elif section == "props":
                desc = f"道具 {entry.get('item')} 在 {entry.get('holder', '')}"
            elif section == "open_hooks":
                desc = f"未回收钩子：{entry.get('hook')}"
            else:
                desc = str({k: v for k, v in entry.items() if k not in ("section", "awaiting", "why_pending")})
            lines.append(f"- [{section}] {desc}（待确认：{entry.get('awaiting', '?')}）")
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