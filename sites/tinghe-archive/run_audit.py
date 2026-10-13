#!/usr/bin/env python3
"""Run narrative continuity audit for a newly generated episode.

Usage:
  py -3 run_audit.py <work_id> <ep_id> [--context PATH] [--episode PATH] [--prompt PATH]

Exits:
  0 = PASS (status PASS, issues only MINOR or empty)
  1 = FAIL (status FAIL, or parse error, or timeout, or model error)
  2 = USAGE ERROR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from tools.atomic_io import atomic_write_text

# A scheduled run has no console and may inherit the OEM code page;
# writing Chinese or an ellipsis to stdout would then raise.
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
OPENCODE = Path(r"C:\Users\Administrator\.local\bin\opencode.exe")

# Ordered by "can it hold ~20 KB of context and judge continuity", not by overall
# quality. Overridable so the auditor can be pointed elsewhere without editing code.
AUDIT_MODELS = [
    m for m in (os.environ.get("TINGHE_AUDIT_MODELS") or "").split(",") if m.strip()
] or [
    "opencode/nemotron-3-ultra-free",
    "opencode/fledge-alpha-free",
    "opencode/longcat-2.5-preview-free",
    "opencode/muse-spark-1.3-contributor-free",
    "opencode/mimo-v2.6-flash-free",
    "opencode/nemotron-3.5-lightning-free",
]


def audit_models() -> list[str]:
    return list(AUDIT_MODELS)


STYLE_FIELDS = ("words", "visual_points", "pressure_complete", "dialogue_dumps",
                "hook_open", "humor_ok", "violation", "notes")


def split_verdict(raw: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a model verdict into (fact audit, style audit).

    New schema: {"fact": {...}, "style": {...}}. Old bare schema (status +
    issues at top level) is still accepted, with an empty style, so a model
    that ignores the new contract degrades to fact-only instead of failing.
    Style fields are coerced to their types; unknown keys are dropped.
    """
    if isinstance(raw, dict) and isinstance(raw.get("fact"), dict):
        fact = raw["fact"]
        rest = raw.get("style")
        style = rest if isinstance(rest, dict) else {}
    elif isinstance(raw, dict) and "status" in raw and "issues" in raw:
        fact, style = raw, {}
    else:
        return {}, {}
    clean = {
        "words": style.get("words", 0) or 0,
        "visual_points": style.get("visual_points", 0) or 0,
        "pressure_complete": bool(style.get("pressure_complete", True)),
        "dialogue_dumps": bool(style.get("dialogue_dumps", False)),
        "hook_open": bool(style.get("hook_open", True)),
        "humor_ok": bool(style.get("humor_ok", True)),
        "violation": bool(style.get("violation", False)),
        "notes": str(style.get("notes", ""))[:200],
        # AI 味与文采（AUDIT_PROMPT §7a，只记录不拦单）。缺省 True 是深思熟虑的：
        # 老模型输出的 style 里没有这些键，缺省 False 会把历史数据全标成"有 AI 味"。
        "ai_taste_ok": bool(style.get("ai_taste_ok", True)),
        "ai_taste_notes": str(style.get("ai_taste_notes", ""))[:200],
        "prose_alive": bool(style.get("prose_alive", True)),
    }
    try:
        clean["words"] = int(clean["words"])
        clean["visual_points"] = int(clean["visual_points"])
    except (TypeError, ValueError):
        clean["words"], clean["visual_points"] = 0, 0
    return fact, clean


def extract_json_object(text: str) -> str | None:
    """Return the outermost balanced `{...}` in `text`, or None.

    Brace counting is string-aware so a `}` inside a quoted description does not
    end the object early — which is exactly what happens when an issue description
    contains Chinese quotes or a stray brace.
    """
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
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
                    return text[start:i + 1]
        # Unbalanced from here; try the next opening brace.
        start = text.find("{", start + 1)
    return None


def salvage_verdict(text: str) -> dict | None:
    """Find any embedded object that looks like a verdict and return it.

    Accepts both schemas seen in practice: a bare `{"status":..., "issues":[...]}`
    and the wrapped `{"fact": {...}, "style": {...}}`. Used only when the outermost
    object failed to parse — this recovers the auditor's answer instead of
    discarding it because of surrounding text.
    """
    best = None
    idx = 0
    while True:
        start = text.find("{", idx)
        if start == -1:
            break
        idx = start + 1
        depth = 0
        in_str = False
        escape = False
        end = None
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
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
        if end is None:
            continue
        try:
            obj = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if "status" in obj and "issues" in obj:
            return obj
        for key in ("fact", "audit", "verdict", "result"):
            inner = obj.get(key)
            if isinstance(inner, dict) and "status" in inner and "issues" in inner:
                return inner
        if best is None:
            best = obj
    return best


def run_audit(
    work_id: str,
    ep_id: str,
    context_path: Path,
    episode_html: str,
    prompt_path: Path,
    timeout_sec: int = 180,
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    """Run opencode audit, return (exit_code, fact_json, style_json)."""
    if not OPENCODE.is_file():
        return 1, {"status": "FAIL", "issues": [{"type": "OTHER", "severity": "CRITICAL", "episode": ep_id, "description": f"opencode not found at {OPENCODE}", "evidence_before": "", "evidence_after": ""}]}, {}

    # Write episode HTML to temp file for --file
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as tf:
        tf.write(episode_html)
        episode_file = tf.name

    def _infra_fail(reason: str) -> tuple[int, dict, dict]:
        try:
            Path(episode_file).unlink(missing_ok=True)
        except Exception:
            pass
        return 1, {"status": "FAIL", "issues": [{"type": "OTHER", "severity": "CRITICAL",
                                                 "episode": ep_id, "description": reason,
                                                 "evidence_before": "", "evidence_after": ""}]}, {}

    # Rotate models instead of letting `--auto` pick one. On 2026-10-07 auto chose a
    # model whose upstream was returning 500s, and because an infrastructure error
    # counts as FAIL by design, one dead endpoint blocked every deployment for as
    # long as it stayed down. Infrastructure failure is not a verdict about the
    # episode, so it should cost one model, not the whole pipeline.
    models = audit_models()
    last_infra = ""
    for index, model in enumerate(models, 1):
        cmd = [
            str(OPENCODE), "run", "--model", model,
            "--file", str(context_path),
            "--file", episode_file,
            "--file", str(prompt_path),
            "严格按 AUDIT_PROMPT.md 审核，仅输出一行 JSON。"
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout_sec
            )
        except subprocess.TimeoutExpired:
            last_infra = f"Audit timeout after {timeout_sec}s on {model}"
            print(f"  audit: {last_infra}; trying the next model")
            continue
        except Exception as exc:
            last_infra = f"Subprocess error on {model}: {exc}"
            print(f"  audit: {last_infra}; trying the next model")
            continue

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        if result.returncode != 0:
            last_infra = f"opencode exited {result.returncode} on {model}: {stderr[:300]}"
            print(f"  audit: {last_infra[:160]}; trying the next model")
            continue

        try:
            Path(episode_file).unlink(missing_ok=True)
        except Exception:
            pass
        break
    else:
        # Every model failed for infrastructure reasons. Fail closed — that is the
        # correct outcome, and now it means "no auditor available", not "this
        # episode is broken".
        return _infra_fail(last_infra or "no audit model produced a verdict")

    # Extract the verdict object from whatever the model printed.
    #
    # This used to accept only a single line that both started with "{" and ended
    # with "}", which meant a perfectly good verdict written as pretty-printed
    # multi-line JSON was thrown away and recorded as FAIL. Measured 2026-10-07:
    # 12 of 19 failures were this, and three of them contained `"status": "PASS"` —
    # the auditor had passed the episode and the parser threw the answer away.
    # Extract the outermost balanced JSON object from the whole output instead,
    # tolerating line breaks, leading prose and trailing chatter.
    json_line = extract_json_object(stdout)

    if not json_line:
        return 1, {"status": "FAIL", "issues": [{"type": "OTHER", "severity": "CRITICAL", "episode": ep_id, "description": f"No JSON object in output: {stdout[:300]}", "evidence_before": "", "evidence_after": ""}]}, {}

    try:
        raw = json.loads(json_line)
    except json.JSONDecodeError as exc:
        # One retry on the same output, salvaging the last complete inner object.
        # Models often wrap the verdict in extra keys or prefix it with commentary
        # that leaves the outer braces unbalanced but the verdict intact.
        salvaged = salvage_verdict(stdout)
        if salvaged is not None:
            raw = salvaged
            json_line = json.dumps(raw, ensure_ascii=False)
        else:
            return 1, {"status": "FAIL", "issues": [{"type": "OTHER", "severity": "CRITICAL", "episode": ep_id, "description": f"JSON parse error: {exc} in: {json_line[:200]}", "evidence_before": "", "evidence_after": ""}]}, {}

    # Split the style verdict from the fact verdict. The old single-object
    # schema (bare status/issues) is still accepted, with an empty style.
    audit, style = split_verdict(raw)

    # Validate shape
    if not isinstance(audit, dict) or "status" not in audit or "issues" not in audit:
        return 1, {"status": "FAIL", "issues": [{"type": "OTHER", "severity": "CRITICAL", "episode": ep_id, "description": f"Invalid audit shape: missing status/issues", "evidence_before": "", "evidence_after": ""}]}, style

    if audit["status"] not in ("PASS", "FAIL"):
        audit["status"] = "FAIL"
        audit["issues"].insert(0, {"type": "OTHER", "severity": "CRITICAL", "episode": ep_id, "description": f"Invalid status value: {audit.get('status')}", "evidence_before": "", "evidence_after": ""})

    # Validate each issue
    for issue in audit.get("issues", []):
        if not isinstance(issue, dict):
            return 1, {"status": "FAIL", "issues": [{"type": "OTHER", "severity": "CRITICAL", "episode": ep_id, "description": f"Issue not object: {issue}", "evidence_before": "", "evidence_after": ""}]}, style
        for field in ("type", "severity", "episode", "description", "evidence_before", "evidence_after"):
            if field not in issue:
                return 1, {"status": "FAIL", "issues": [{"type": "OTHER", "severity": "CRITICAL", "episode": ep_id, "description": f"Issue missing field: {field}", "evidence_before": "", "evidence_after": ""}]}, style
        if issue["severity"] not in ("CRITICAL", "MAJOR", "MINOR"):
            issue["severity"] = "CRITICAL"

    # Determine final exit code
    status = audit["status"]
    issues = audit.get("issues", [])
    if status == "FAIL":
        return 1, audit, style
    # PASS but may have MINOR issues
    critical_or_major = any(i["severity"] in ("CRITICAL", "MAJOR") for i in issues)
    if critical_or_major:
        audit["status"] = "FAIL"
        return 1, audit, style
    return 0, audit, style


def write_audit_failure(work_id: str, ep_id: str, audit: dict[str, Any],
                        style: dict[str, Any] | None = None,
                        episode_html: str = '') -> Path:
    """Record an audit verdict in audit_failures.json.

    Failures are kept and appended; a PASS supersedes any earlier record for the
    same episode instead of being appended beside it. Without that, a fixed
    episode stayed on the list forever and the next audit read the stale text as
    if it were still the published draft. The style verdict rides along purely
    as a record; it never decides anything here.
    """
    failures_path = ROOT / "audit_failures.json"
    # The verdict is produced by a model, so it is not a proof. On 2026-10-07 the
    # same text of tingjijia/ep05 was audited PASS at 16:25 and FAIL at 16:35.
    # Recording which text was judged lets a hold-back be lifted only after
    # several consecutive PASSes *of the same content*; without that, one lucky
    # verdict is indistinguishable from a settled one.
    content_sha = hashlib.sha256(episode_html.encode("utf-8")).hexdigest()[:16]
    record = {
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "work": work_id,
        "episode": ep_id,
        "content_sha": content_sha,
        "audit": audit,
        "style": style or {},
    }
    existing = []
    if failures_path.is_file():
        try:
            existing = json.loads(failures_path.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    same = [r for r in existing
            if r.get("work") == work_id and r.get("episode") == ep_id]
    kept = [r for r in existing
            if not (r.get("work") == work_id and r.get("episode") == ep_id)]

    # How many PASSes in a row have this exact text earned, counting this one.
    streak = 1
    if audit.get("status") == "PASS":
        for row in reversed(same):
            if row.get("audit", {}).get("status") != "PASS":
                break
            if row.get("content_sha") != content_sha:
                break
            streak += 1
    record["pass_streak"] = streak
    if audit.get("status") == "FAIL":
        record["pass_streak"] = 0
        kept.append(record)
    else:
        # A PASS is the current truth for this episode: record it, and mark any
        # earlier failure resolved rather than dropping the history.
        for row in same:
            row["resolved"] = record["timestamp"]
        kept.extend(same)
        record["resolved"] = False
        kept.append(record)

    atomic_write_text(failures_path, json.dumps(kept, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    return failures_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work_id")
    parser.add_argument("ep_id")
    parser.add_argument("--context", type=Path, default=None)
    parser.add_argument("--episode", type=Path, default=None)
    parser.add_argument("--prompt", type=Path, default=ROOT / "AUDIT_PROMPT.md")
    # A full-context audit of a 40-block episode runs a long model session; the
    # old 180s default timed out on healthy content, and a timeout is scored as
    # a CRITICAL failure, so a passing episode looked rejected.
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    context_path = args.context or (ROOT / "originals_source" / args.work_id / "context_bundle.md")
    episode_json_path = args.episode or (ROOT / "public" / "data" / "originals" / args.work_id / f"{args.ep_id}.json")

    if not context_path.is_file():
        print(f"context not found: {context_path}", file=sys.stderr)
        return 2
    if not args.prompt.is_file():
        print(f"prompt not found: {args.prompt}", file=sys.stderr)
        return 2

    episode_html = ""
    episode_data: dict = {}
    if episode_json_path.is_file():
        try:
            episode_data = json.loads(episode_json_path.read_text(encoding="utf-8"))
            episode_html = episode_data.get("html", "")
        except Exception as exc:
            print(f"episode JSON parse error: {exc}", file=sys.stderr)
            return 2
    else:
        # Fall back to the authored source. A quarantined episode is deliberately
        # absent from public/, which made it unauditable — and an episode that
        # cannot be audited can never be repaired and re-admitted, so holding one
        # back would be a permanent exile rather than a pause. Render the same way
        # the builder does so the audited text matches what a reader would get.
        print("not in public/ (held back?); auditing the authored source instead")
        try:
            sys.path.insert(0, str(ROOT))
            from build_originals import load_sources, render_blocks
            work = next((w for w in load_sources() if w["id"] == args.work_id), None)
            if work is None:
                print(f"work not found in originals_source: {args.work_id}", file=sys.stderr)
                return 2
            episode = next((e for e in work.get("episodes", []) if e["id"] == args.ep_id), None)
            if episode is None:
                print(f"episode not found in source: {args.work_id}/{args.ep_id}", file=sys.stderr)
                return 2
            episode_data = {"id": episode["id"], "no": episode["no"],
                            "title": episode["title"]}
            episode_html = render_blocks(episode["blocks"], work, episode)
        except Exception as exc:
            print(f"could not render authored episode: {exc}", file=sys.stderr)
            return 2

    if not episode_html:
        print(f"episode HTML empty: {episode_json_path}", file=sys.stderr)
        return 2

    print(f"Auditing {args.work_id}/{args.ep_id} …")
    # Prior context must be STRICTLY earlier episodes. The bundle is built per
    # work and keeps full text for the most recent N chapters, so simply removing
    # the audited episode left its own sequels behind as "backstory" — that is how
    # an audit of ep05 ended up arguing that ep05 "comes after ep09 yet regresses
    # to ep05's progress", and how a quarter of the catalogue was failed and seven
    # episodes quarantined. prior_context() drops everything numbered >= the
    # audited episode and labels what remains as backstory.
    sys.path.insert(0, str(ROOT))
    from build_context_bundle import prior_context, strip_pending  # noqa: E402

    # The episode's number comes from the payload, not the id, so a work whose
    # ids do not encode the number still gets the right cut.
    ep_no = episode_data.get("no")
    if ep_no is None:
        digits = "".join(ch for ch in args.ep_id if ch.isdigit())
        ep_no = int(digits) if digits else 0

    raw_context = context_path.read_text(encoding="utf-8")
    context_text, dropped = prior_context(raw_context, args.ep_id, int(ep_no))
    if dropped:
        print(f"  prior context: dropped later episodes {dropped} "
              f"(kept only text before ep{int(ep_no):02d})")
    else:
        print(f"  prior context: nothing later than ep{int(ep_no):02d} was present")
    context_text = strip_pending(context_text)
    tmp_context = context_path.with_name(context_path.stem + ".audit.md")
    atomic_write_text(tmp_context, context_text, encoding="utf-8")
    try:
        code, audit, style = run_audit(args.work_id, args.ep_id, tmp_context,
                                       episode_html, args.prompt, args.timeout)
    finally:
        tmp_context.unlink(missing_ok=True)

    # Style verdict never blocks — except the single hard exception below.
    # Everything else in style is recorded, not judged.
    if style.get("violation"):
        audit["status"] = "FAIL"
        audit.setdefault("issues", []).append({
            "type": "OTHER",
            "severity": "CRITICAL",
            "episode": args.ep_id,
            "description": "【文笔·内涵越界】出现直白性描写或露骨暗示，按硬规则拦单。",
            "evidence_before": "",
            "evidence_after": style.get("notes", "")[:120],
        })
        code = 1

    print(f"Audit status: {audit.get('status')}, issues: {len(audit.get('issues', []))}")
    # Machine-readable verdicts for the pipeline (daily_originals.run_audits).
    # The human lines above are for logs; these two lines are the contract.
    print("AUDIT_JSON: " + json.dumps(audit, ensure_ascii=False))
    print("STYLE_JSON: " + json.dumps(style, ensure_ascii=False))

    if code != 0:
        path = write_audit_failure(args.work_id, args.ep_id, audit, style, episode_html)
        print(f"FAIL written to {path}")
        return 1

    # Record the PASS too, so the day's verdict for every episode is readable in
    # one place without re-running the auditor.
    path = write_audit_failure(args.work_id, args.ep_id, audit, style, episode_html)
    print(f"PASS recorded in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())