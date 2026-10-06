"""Detect and repair published chapters that lost or gained text.

``public/data/chapters`` is a projection of the canonical source script. A canon
pass damaged three scenes: ``c198`` had the whole 演化走向摘要 appended in place
of its body, and ``c065``/``c086`` shipped only the opening paragraph.

Repair is deliberately conservative. Two rules, both of which guarantee that no
already-published prose is thrown away:

``POLLUTED``
    The published body contains substantial sentences taken from the wave
    summary (the text of ``c999``) that do not exist in the source scene. Those
    sentences belong to no single scene, so the body was overwritten with
    foreign text. Repair replaces the body with the source scene.

``TRUNCATED``
    Reported only, never repaired. Every sentence in the published body also
    exists in the source scene, but the published body is shorter.

    This is *not* treated as damage. The published snapshot was projected from
    an older state of the source, which has since grown to 5605 scenes, so a
    published scene being shorter than today's draft is normal drift. Silently
    replacing shipped prose with a newer draft would rewrite the story, which
    is a human decision. ``--fix`` therefore only ever touches ``POLLUTED``.

The summary chapter itself is skipped.

Run:  py -3 repair_chapters.py          # report only
      py -3 repair_chapters.py --fix    # repair POLLUTED chapters only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = (ROOT / "research" / "persona_dna_library"
          / "20260920_canheguiying_reincarnation_v2"
          / "world_live_full_script.v1.md")
PUB = HERE / "public" / "data"
CHDIR = PUB / "chapters"
BOOK = PUB / "book.json"
SUMMARY_ID = "c999"

sys.path.insert(0, str(ROOT))
from tools.canon_scene_pass import _strip_meta_blocks  # noqa: E402
from tools.atomic_io import atomic_write_text

sys.stdout.reconfigure(encoding="utf-8")  # Bug #1 fix: prevent UnicodeEncodeError on GBK console

SCENE_RE = re.compile(r"^(?:【)?第(\d+)场(续)?(?:】)?｜(.+)$")
SENT_MIN = 12          # shortest string treated as a sentence for diffing
FOREIGN_MIN = 40       # a leaked summary must be at least this long to count
TRUNCATED_RATIO = 0.95  # published must be shorter than this share of source


def escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def md_to_html(body: str) -> str:
    """Same renderer as the reader build; kept in step with build_reader.py."""
    body = _strip_meta_blocks(body)
    out: list[str] = []
    block: list[str] = []

    def flush() -> None:
        nonlocal block
        if not block:
            return
        joined = "<br>".join(escape(x) for x in block)
        first = block[0]
        if first.startswith(">"):
            cleaned = "<br>".join(escape(x.lstrip("> ").lstrip(">")) for x in block)
            out.append("<blockquote>" + cleaned + "</blockquote>")
        elif first.startswith(("- ", "* ")):
            out.append("<ul>" + "".join("<li>" + escape(x[2:]) + "</li>" for x in block) + "</ul>")
        elif first.startswith(("本场", "时间：", "未解决", "已知", "【")):
            out.append("<div class='note'>" + joined + "</div>")
        else:
            out.append("<p>" + joined + "</p>")
        block = []

    for line in body.splitlines():
        s = line.rstrip()
        if not s:
            flush()
            continue
        if s.startswith("```"):
            continue
        block.append(s)
    flush()
    return "\n".join(out)


def plain(html: str) -> str:
    return re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", html))


def sentences(html: str) -> list[str]:
    text = plain(html)
    return [s.strip() for s in re.split(r"[\n。！？]", text) if len(s.strip()) >= SENT_MIN]


def source_scenes() -> dict[int, str]:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    starts: list[tuple[int, int]] = []
    for i, line in enumerate(lines):
        m = SCENE_RE.match(line.strip())
        if m:
            starts.append((i, int(m.group(1))))

    scenes: dict[int, str] = {}
    for k, (i, no) in enumerate(starts):
        nxt = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        body = lines[i + 1:nxt]
        while body and body[-1].startswith("## "):
            body = body[:-1]
        text = "\n".join(body).strip()
        if text:
            scenes.setdefault(no, text)   # first occurrence is the scene
    return scenes


def published_no(chapter_id: str) -> int | None:
    m = re.fullmatch(r"c(\d{3})b?", chapter_id)
    return int(m.group(1)) if m else None


def classify(cid: str, html: str, src_html: str, summary_text: str) -> tuple[str, str]:
    src_plain = plain(src_html)
    pub_sents = sentences(html)
    src_sents = set(sentences(src_html))

    # POLLUTED: foreign summary prose the source scene never had.
    foreign = [s for s in sentences(summary_text)
               if len(s) >= FOREIGN_MIN and s in plain(html) and s not in src_plain]
    if len(foreign) >= 2:
        head = foreign[0][:34]
        return "POLLUTED", f"{len(foreign)} summary sentences leaked (e.g. “{head}…”)"

    # TRUNCATED: published is a strict subset of the source and much shorter.
    if pub_sents and all(s in src_sents for s in pub_sents):
        ratio = len(html) / max(1, len(src_html))
        if ratio < TRUNCATED_RATIO:
            missing = len(src_sents) - len([s for s in pub_sents if s in src_sents])
            return "TRUNCATED", (f"published {len(html)} of {len(src_html)} chars, "
                                 f"~{missing} source sentences missing")
    return "ok", ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fix", action="store_true", help="rewrite damaged chapters")
    args = ap.parse_args()

    scenes = source_scenes()
    book = json.loads(BOOK.read_text(encoding="utf-8"))
    meta_by_id = {c["id"]: c for c in book.get("chapters", [])}
    summary_html = json.loads((CHDIR / f"{SUMMARY_ID}.json").read_text(encoding="utf-8"))["html"]

    findings: list[tuple[str, str, str, str]] = []
    for path in sorted(CHDIR.glob("c*.json")):
        cid = path.stem
        if cid == SUMMARY_ID:
            continue
        if (meta_by_id.get(cid) or {}).get("wave") == "summary":
            continue
        no = published_no(cid)
        if no is None or no not in scenes:
            continue
        src_html = md_to_html(scenes[no])
        html = json.loads(path.read_text(encoding="utf-8")).get("html", "")
        kind, note = classify(cid, html, src_html, summary_html)
        findings.append((kind, cid, note, src_html))

    damaged = [f for f in findings if f[0] == "POLLUTED"]
    drift = [f for f in findings if f[0] == "TRUNCATED"]
    for kind, cid, note, _ in findings:
        if kind == "POLLUTED":
            print(f"{kind:<10} {cid:<8} {note}")

    print(f"\nchecked {len(findings)} published chapters against {len(scenes)} source scenes")
    print(f"polluted (repairable): {len(damaged)}")
    print(f"source drift (report only, published prose left alone): {len(drift)}")
    if drift:
        print("  " + ", ".join(cid for _, cid, _, _ in drift))
    if damaged and not args.fix:
        print("re-run with --fix to repair the polluted chapters")

    if not args.fix or not damaged:
        return 0

    repaired: list[str] = []
    for _, cid, _, src_html in damaged:
        payload = json.loads((CHDIR / f"{cid}.json").read_text(encoding="utf-8"))
        payload["html"] = src_html
        atomic_write_text((CHDIR / f"{cid}.json"), 
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        meta = meta_by_id.get(cid)
        if meta is not None:
            no = published_no(cid)
            meta["preview"] = re.sub(r"\s+", " ", scenes[no]).strip()[:90]
        repaired.append(cid)

    atomic_write_text(BOOK, json.dumps(book, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"repaired {len(repaired)}: {', '.join(repaired)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())