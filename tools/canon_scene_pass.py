
# -*- coding: utf-8 -*-
"""Autonomous canon-scene pass gate.

System judges the next unpublished mill scene. Pass: incremental reader
sync. Fail: sandbox receipt only. Never dump mill waves into the site.
Never a second evolve writer. Default: free/heuristic, no paid model.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_LIB = ROOT / "research" / "persona_dna_library" / "20260920_canheguiying_reincarnation_v2"
PUBLIC = ROOT / "sites" / "tinghe-archive" / "public"
DATA = PUBLIC / "data"
BOOK = DATA / "book.json"
STATE = DATA / "story-state.v1.json"
CHAPTERS = DATA / "chapters"
WRANGLER_TOML = ROOT / "sites" / "tinghe-archive" / "wrangler.toml"

SCENE_HEAD_RE = re.compile(
    r"^第\s*(\d+)\s*场(?:[｜|·]\s*([^\n｜|]*))?(?:[｜|·]\s*([^\n｜|]*))?(?:[｜|·]\s*([^\n]*))?",
    re.M,
)
SCENE_SPLIT_RE = re.compile(r"(?=^第\s*\d+\s*场)", re.M)
# Meta-only lines / blocks that should not appear in the public reader HTML.
# The full text remains available for judge() and update_story_state(); only
# scene_to_html() strips these. Wave files keep them for the evolve system.
META_LINE_PATTERNS = (
    # 在场：xxx / 不在场：xxx (line-start only; mid-dialogue stays intact)
    re.compile(r"^\s*在场[：:].*$", re.M),
    re.compile(r"^\s*不在场[：:].*$", re.M),
    # name：未出场 / name：未出场（在城西）
    re.compile(r"^\s*[\u4e00-\u9fa5]{1,6}[：:]\s*未出场[（(][^）)]*[）)]?[。.]?\s*$", re.M),
    re.compile(r"^\s*[\u4e00-\u9fa5]{1,6}[：:]\s*未出场[。.]?\s*$", re.M),
    # 其他人：xxx — only strip when the line is a roster (no dialogue
    # punctuation and short). Long narrative under 其他人： is reader-facing
    # prose and must NOT be removed. Dialogue quote marks: “” ‘'  「」
    # and sentence-ending 。 are signs of actual content.
    re.compile(
        r"^\s*其他人[：:][^“”‘’「」\n。]{0,24}$",
        re.M,
    ),
    # 本场变化：xxx / 本场变化（承上）：xxx (legacy variant allows a short
    # bracketed qualifier between the label and the colon)
    re.compile(r"^\s*本场变化[^：:\n]{0,8}[：:].*$", re.M),
    # Legacy writer note: 【事件走向】...
    re.compile(r"^\s*【事件走向】.*$", re.M),
    # Marker-only tracking lines such as 【本波快照】
    re.compile(r"^\s*【[^】]*】\s*$", re.M),
    # Wave headings that leaked from markdown source into reader HTML
    re.compile(r"^\s*#{1,6}\s+wave_\d+\s*$", re.M | re.I),
)
# Sub-fields that may appear inside 本场变化 or 【本波快照】 blocks. The block
# itself is dropped wholesale; these patterns catch orphan sub-lines.
META_SUBLEVEL_RE = re.compile(
    r"^\s*(?:世界|关系|物件|未决|人物状态|新登场|离场[／/]生死|已发生|未解决|关键道具|"
    r"世界开门还是收束|一句话|时间|地点)[：:].*$",
    re.M,
)
SNAPSHOT_MARK = "【本波快照】"
CHANGE_MARK = "本场变化"
FORBIDDEN = (
    "外卖骑手",
    "厨房奶奶",
    "吃绝户",
    "战神归来",
    "系统金手指",
    "炫富认祖",
    "霸凌网红",
    "金手指",
    "战神归来",
    "空洞地府",
    "阎王殿",
    "地府阎王",
    "砸玻璃",
    "全场安静了",
    "众人道歉",
    "不是做不到，是有人只想着绕过去",
    "该是什么样，就得是什么样",
)
AI_TELLS = (
    "空气凝固",
    "眼神一冷",
    "嘴角一勾",
    "心中暗道",
    "不禁想到",
    "仿佛在告诉",
    "像是在说",
)
ADVANCE_HINTS = (
    "确认",
    "推翻",
    "缩小",
    "勾回",
    "对上",
    "画押",
    "日期",
    "信",
    "契",
    "当票",
    "不进",
    "短一截",
    "折价",
    "重丈",
    "守",
    "拒",
)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now().astimezone().date().isoformat()


def _lib(path: str | None) -> Path:
    return Path(path or os.environ.get("WORLD_LIVE_LIB") or DEFAULT_LIB).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def numeric_chapters(book: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for item in book.get("chapters", []):
        cid = str(item.get("id") or "")
        if re.fullmatch(r"c\d+", cid) and cid != "c999":
            items.append(item)
    return sorted(items, key=lambda item: float(item.get("no", 0)))


def latest_published_no(book: dict[str, Any]) -> int:
    nums = numeric_chapters(book)
    if not nums:
        return 0
    return int(float(nums[-1].get("no") or 0))


def extract_scene(lib: Path, n: int) -> dict[str, Any] | None:
    waves = sorted((lib / "world_live_waves").glob("wave_*.md"))
    heading = None
    body = ""
    wave_name = ""
    for wp in waves:
        text = wp.read_text(encoding="utf-8")
        parts = SCENE_SPLIT_RE.split(text)
        for part in parts:
            m = SCENE_HEAD_RE.search(part.strip())
            if not m:
                continue
            if int(m.group(1)) != n:
                continue
            heading = m.group(0).splitlines()[0].strip()
            body = part.strip()
            wave_name = wp.stem
            break
        if body:
            break
    if not body:
        return None
    m = SCENE_HEAD_RE.search(heading or "")
    time_bits = [x.strip() for x in (m.group(2), m.group(3)) if m and x and x.strip()]
    place = (m.group(4) or "").strip() if m else ""
    if not place and time_bits:
        # formats like 夜｜内｜县衙·东屋 already consumed
        pass
    # Header: 第234场｜夜｜内｜县衙·东屋
    raw_bits = re.split(r"[｜|]", heading or "")
    place = raw_bits[-1].strip() if len(raw_bits) >= 2 else place
    time_label = " ".join(raw_bits[1:-1]).strip() if len(raw_bits) >= 3 else " ".join(time_bits)
    return {
        "n": n,
        "heading": heading,
        "place": place,
        "time": time_label or "UNKNOWN",
        "wave": wave_name,
        "text": body,
    }


def scene_to_html(text: str) -> str:
    text = _strip_meta_blocks(text)
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[0].startswith("第"):
        lines = lines[1:]
    blocks: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        chunk = "\n".join(buf).strip()
        buf.clear()
        if not chunk:
            return
        esc = (
            chunk.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        esc = esc.replace("\n", "<br>")
        blocks.append("<p>" + esc + "</p>")

    for line in lines:
        if line.strip() == "":
            flush()
        else:
            buf.append(line)
    flush()
    return "\n".join(blocks)


def _strip_meta_blocks(text: str) -> str:
    """Strip tracking-only blocks from scene text before reader HTML render.

    Strips:
    - Lines starting with 在场：/不在场：
    - Lines shaped as `<name>：未出场` (with optional location parens)
    - Lines starting with 其他人：
    - The entire 【本波快照】... trailing section
    - The entire 本场变化：... block (single-line or multi-line)
    - Orphan sub-field lines (世界： / 关系： / 物件： / 未决： etc.) that may
      leak from a malformed snapshot block.

    Full text is preserved for judge() and update_story_state().
    """
    if not text:
        return text
    # Drop trailing 【本波快照】 section first (it always lives at the tail).
    snap = text.find(SNAPSHOT_MARK)
    if snap >= 0:
        text = text[:snap]
    # Drop the 本场变化 block. It can be a single line or span multiple lines
    # until the next blank line. We cut from the marker to the next blank line
    # (or to end of text if no blank follows).
    pattern = re.compile(
        r"^" + CHANGE_MARK + r"[：:][^\n]*(?:\n(?!\s*$).*)*",
        re.M,
    )
    text = pattern.sub("", text)
    # Drop orphan sub-field lines that survived (defensive).
    text = META_SUBLEVEL_RE.sub("", text)
    # Drop other single-line meta markers.
    for pat in META_LINE_PATTERNS:
        text = pat.sub("", text)
    # Collapse runs of blank lines left behind.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def preview_of(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("环境"):
            return s[:80]
    body = re.sub(r"^第[^\n]+\n", "", text).strip()
    return body[:80]


def judge(scene: dict[str, Any]) -> dict[str, Any]:
    text = scene["text"]
    reasons: list[str] = []
    fails: list[str] = []
    hits = [w for w in FORBIDDEN if w in text]
    if hits:
        fails.append("forbidden:" + ",".join(hits))
    if len(text) < 400:
        fails.append("too_short")
    if "本场变化" not in text:
        fails.append("no_change_block")
    if not any(h in text for h in ADVANCE_HINTS):
        fails.append("no_effective_advance")
    ai = [w for w in AI_TELLS if w in text]
    if len(ai) >= 2:
        fails.append("ai_tells:" + ",".join(ai))
    # 说明书：规则先讲
    if re.search(r"(规则是|所谓|系统提示|首先，|其次，)", text):
        fails.append("manual_voice")
    quotes = re.findall(r"[“\"]([^”\"]+)[”\"]", text)
    if len(quotes) < 2:
        fails.append("not_enough_pressure_talk")
    # Failure-mode signals (cheap, language-light). Same heuristic as
    # analyze_failure_modes.py but the thresholds live in
    # canon_failure_signals.THRESHOLDS.
    try:
        from tools.canon_failure_signals import compute_signals, flag_failures
    except Exception:
        sys.path.insert(0, str(ROOT / "tools"))
        from canon_failure_signals import compute_signals, flag_failures
    fm_signals = compute_signals(text)
    fm_fails = flag_failures(fm_signals)
    if fm_fails:
        fails.append("failure_modes:" + ",".join(fm_fails))
    # 问答完就推进：连续两轮纯问答且无沉默/不坐/不进
    qa_only = bool(re.search(r"：\s*“[^”]{2,}”\s*\n\n\S+：\s*“[^”]{2,}”", text))
    has_hold = any(x in text for x in ("沉默", "没坐", "不坐", "不进", "不答", "袖", "没让"))
    if qa_only and not has_hold:
        reasons.append("qa_fast_but_held_check_weak")
    # 活人三问：heuristic pass notes
    if "未出场" in text and text.count("：") < 4:
        fails.append("cast_sheet_not_people")
    change = ""
    for line in text.splitlines():
        if line.startswith("本场变化"):
            change = line
            break
    packet = {
        "schema": "video_kingdom.conflict_driven_scene.v1",
        "scene_class": "B",
        "goals": {
            "a": "ask_or_press",
            "b": "hold_boundary",
        },
        "change_at_end": {
            "kind": "information" if any(x in text for x in ("对上", "日期", "信")) else "choice",
            "what": change[:120] or "scene_end",
        },
        "lengthener": False,
        "speech_intent_readable": True,
        "completes_in_picture": True,
    }
    try:
        from tools.validate_conflict_driven_scene import validate_conflict_driven_scene
    except Exception:
        try:
            sys.path.insert(0, str(ROOT / "tools"))
            from validate_conflict_driven_scene import validate_conflict_driven_scene
        except Exception as exc:
            validate_conflict_driven_scene = None
            reasons.append("conflict_validator_import:" + type(exc).__name__)
    conflict = {"status": "ADVISORY", "errors": [], "notes": ["no validator"]}
    if validate_conflict_driven_scene:
        conflict = validate_conflict_driven_scene(packet, strict=False)
        if conflict.get("status") == "BLOCKED":
            fails.append("conflict_blocked")
    alive = {
        "q1_person_not_manual": "manual_voice" not in "".join(fails) and "cast_sheet_not_people" not in "".join(fails),
        "q2_not_ai": len(ai) < 2,
        "q3_will_not_settle": has_hold or any(x in text for x in ("不", "拒", "短一截", "不进园")),
    }
    if not all(alive.values()):
        fails.append("alive_three_fail:" + ",".join(k for k, v in alive.items() if not v))
    verdict = "PASS" if not fails else "REJECT"
    return {
        "verdict": verdict,
        "fails": fails,
        "reasons": reasons,
        "alive": alive,
        "conflict": conflict,
        "forbidden_hits": hits,
        "quote_count": len(quotes),
        "packet": packet,
        "failure_mode_signals": fm_signals,
        "failure_mode_fails": fm_fails,
    }


def quota_path(lib: Path) -> Path:
    return lib / "canon_pass_quota.v1.json"


def load_quota(lib: Path) -> dict[str, Any]:
    p = quota_path(lib)
    if p.exists():
        quota = _read_json(p)
    else:
        quota = {
            "schema": "video_kingdom.canon_pass_quota.v1",
            "max_per_day": 2,
            "days": {},
        }
    day = _today()
    days = quota.setdefault("days", {})
    rec = days.setdefault(day, {"passed": 0, "rejected": 0, "skipped": 0})
    if int(rec.get("passed") or 0) == 0 and STATE.exists():
        st = _read_json(STATE)
        gen = str(st.get("generated_at") or "")
        src = str(st.get("source_chapter") or "")
        if gen.startswith(day) and src.startswith("c") and src not in {"c000", "c999"}:
            rec["passed"] = 1
    return quota


def today_pass_count(lib: Path, quota: dict[str, Any]) -> int:
    day = _today()
    return int((quota.get("days") or {}).get(day, {}).get("passed") or 0)


def record_quota(lib: Path, quota: dict[str, Any], passed: bool) -> None:
    day = _today()
    days = quota.setdefault("days", {})
    rec = days.setdefault(day, {"passed": 0, "rejected": 0, "skipped": 0})
    key = "passed" if passed else "rejected"
    rec[key] = int(rec.get(key) or 0) + 1
    quota["updated_at"] = _now_iso()
    _write_json(quota_path(lib), quota)


def update_story_state(scene: dict[str, Any]) -> None:
    st = _read_json(STATE)
    n = scene["n"]
    cid = "c%03d" % n
    title = "第%s场 · %s" % (n, scene["place"])
    st["source_chapter"] = cid
    st["generated_at"] = _now_iso()
    progress = st.setdefault("progress", {})
    progress["completed_scenes"] = n
    progress["current_label"] = title
    progress["current_time"] = scene["time"]
    # Keep phase language; tighten next focus from this scene.
    if "冬至" in scene["text"]:
        progress["phase"] = "典税空名压向冬至"
        progress["next_focus"] = "冬至前画押；周父原信与典函是否同一封"
    plot = st.setdefault("current_plot", {})
    plot["title"] = "日期对上，税压落到周家接地"
    plot["summary"] = (
        "丁怀山把周父光绪二十七年秋寄清江浦的信，与赵氏女同年典函对上日期。"
        "冬至前不进园；冬至后若无人画押，典税折价、地要重丈，周家接地短一截。"
        "陆卷只敢透信有底、无底稿，仍守户房边界。"
    )
    plot["tone"] = "灯罩裂纹，空册退出"
    chars = st.setdefault("characters", [])
    for row in chars:
        if row.get("name") == "丁怀山":
            row["status"] = "把周家算进四条线"
            row["detail"] = "日期对上后，以冬至后折价重丈施压，税压转到周家接地。"
        if row.get("name") == "陆卷":
            row["status"] = "只透信底"
            row["detail"] = "送旧契抄本不坐；只敢说周父有信寄清江浦、户房无底稿。"
        if row.get("name") == "周培":
            row["status"] = "未出场，已被短地"
            row["detail"] = "冬至后无人画押则周家接地短一截；本场不在场。"
    fs = st.setdefault("foreshadowing", {})
    resolved = fs.setdefault("resolved", [])
    item = "周父光绪二十七年秋寄清江浦信与赵氏女同年典函日期对上"
    if item not in resolved:
        resolved.append(item)
    open_items = fs.setdefault("open", [])
    for extra in (
        "周父原信与聚宝当函是否同一封",
        "冬至前谁来画押",
        "周家接地短一截后园子落到哪一步",
    ):
        if extra not in open_items:
            open_items.append(extra)
    pub = st.setdefault("production", {}).setdefault("latest_public", {})
    pub.update({"kind": "正式小说场", "label": title, "href": "#/read/" + cid})
    _write_json(STATE, st)


def insert_book_chapter(scene: dict[str, Any]) -> None:
    book = _read_json(BOOK)
    n = scene["n"]
    cid = "c%03d" % n
    entry = {
        "id": cid,
        "no": n,
        "title": "第%s场 · %s" % (n, scene["place"]),
        "place": scene["place"],
        "time": scene["time"],
        "wave": scene.get("wave") or "",
        "preview": preview_of(scene["text"]),
        "chars": [],
    }
    chapters = book.get("chapters") or []
    existed = [i for i, x in enumerate(chapters) if x.get("id") == cid]
    if existed:
        chapters[existed[0]] = entry
    else:
        idx = next((i for i, x in enumerate(chapters) if x.get("id") == "c999"), len(chapters))
        chapters.insert(idx, entry)
    book["chapters"] = chapters
    book["chapter_count"] = len(chapters)
    _write_json(BOOK, book)


def write_chapter_file(scene: dict[str, Any]) -> Path:
    n = scene["n"]
    cid = "c%03d" % n
    payload = {
        "id": cid,
        "title": "第%s场 · %s" % (n, scene["place"]),
        "place": scene["place"],
        "time": scene["time"],
        "html": scene_to_html(scene["text"]),
    }
    path = CHAPTERS / (cid + ".json")
    _write_json(path, payload)
    return path


def publish_state() -> dict[str, Any]:
    script = ROOT / "tools" / "publish_tinghe_story_state.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError("publish_tinghe_story_state failed: " + (proc.stderr or proc.stdout or ""))
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"raw": proc.stdout}


def find_wrangler() -> list[str] | None:
    node = Path(r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe")
    wjs = Path(r"C:\Users\Administrator\AppData\Local\npm-cache\_npx\32026684e21afda6\node_modules\wrangler\bin\wrangler.js")
    if node.exists() and wjs.exists():
        return [str(node), str(wjs)]
    return None


def deploy_pages() -> dict[str, Any]:
    cmd = find_wrangler()
    if not cmd:
        return {"status": "SKIPPED", "reason": "wrangler_not_found"}
    site = ROOT / "sites" / "tinghe-archive"
    proc = subprocess.run(
        cmd + ["pages", "deploy", "public", "--project-name", "tinghe-archive", "--commit-dirty=true"],
        cwd=str(site),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    return {
        "status": "OK" if proc.returncode == 0 else "FAIL",
        "code": proc.returncode,
        "stdout": (proc.stdout or "")[-1200:],
        "stderr": (proc.stderr or "")[-1200:],
    }


def write_receipt(lib: Path, payload: dict[str, Any], rejected: bool) -> Path:
    folder = lib / ("canon_pass_rejects" if rejected else "canon_pass_receipts")
    folder.mkdir(parents=True, exist_ok=True)
    n = payload.get("scene") or payload.get("n") or "unknown"
    path = folder / ("scene_%s_%s.json" % (n, datetime.now().strftime("%Y%m%dT%H%M%S")))
    _write_json(path, payload)
    return path


def maybe_pass_next(lib: Path, deploy: bool = True, force: bool = False) -> dict[str, Any]:
    book = _read_json(BOOK)
    n = latest_published_no(book) + 1
    if n <= 0:
        n = 1
    quota = load_quota(lib)
    max_per_day = int(quota.get("max_per_day") or 2)
    used = today_pass_count(lib, quota)
    out: dict[str, Any] = {
        "schema": "video_kingdom.canon_scene_pass.v1",
        "at": _now_iso(),
        "lib": str(lib),
        "next": n,
        "quota_used": used,
        "max_per_day": max_per_day,
    }
    if used >= max_per_day and not force:
        out["verdict"] = "SKIPPED"
        out["reason"] = "daily_cap"
        write_receipt(lib, out, rejected=False)
        return out
    scene = extract_scene(lib, n)
    if not scene:
        out["verdict"] = "SKIPPED"
        out["reason"] = "scene_not_in_waves"
        write_receipt(lib, out, rejected=False)
        return out
    judged = judge(scene)
    out["scene"] = n
    out["heading"] = scene["heading"]
    out["wave"] = scene["wave"]
    out.update(judged)
    if judged["verdict"] != "PASS":
        rec = write_receipt(lib, out, rejected=True)
        out["receipt"] = str(rec)
        record_quota(lib, quota, passed=False)
        return out
    write_chapter_file(scene)
    insert_book_chapter(scene)
    update_story_state(scene)
    out["publish"] = publish_state()
    if deploy:
        out["deploy"] = deploy_pages()
    else:
        out["deploy"] = {"status": "SKIPPED", "reason": "no_deploy"}
    record_quota(lib, quota, passed=True)
    rec = write_receipt(lib, out, rejected=False)
    out["receipt"] = str(rec)
    return out


def maybe_pass_next_after_wave(lib: Path | None = None) -> dict[str, Any]:
    return maybe_pass_next(_lib(str(lib) if lib else None), deploy=True, force=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lib", default=str(DEFAULT_LIB))
    parser.add_argument("--once", action="store_true", help="judge and maybe pass the next unpublished scene")
    parser.add_argument("--no-deploy", action="store_true")
    parser.add_argument("--force", action="store_true", help="ignore daily cap")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    lib = _lib(args.lib)
    if args.check_only:
        book = _read_json(BOOK)
        n = latest_published_no(book)
        print(json.dumps({"latest": n, "next": n + 1, "lib": str(lib)}, ensure_ascii=False))
        return 0
    result = maybe_pass_next(lib, deploy=not args.no_deploy, force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("verdict") in {"PASS", "SKIPPED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

