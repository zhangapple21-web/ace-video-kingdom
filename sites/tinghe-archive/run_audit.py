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
import json
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
    }
    try:
        clean["words"] = int(clean["words"])
        clean["visual_points"] = int(clean["visual_points"])
    except (TypeError, ValueError):
        clean["words"], clean["visual_points"] = 0, 0
    return fact, clean


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

    try:
        cmd = [
            str(OPENCODE), "run", "--auto",
            "--file", str(context_path),
            "--file", episode_file,
            "--file", str(prompt_path),
            "严格按 AUDIT_PROMPT.md 审核，仅输出一行 JSON。"
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout_sec
        )
    except subprocess.TimeoutExpired:
        try:
            Path(episode_file).unlink(missing_ok=True)
        except Exception:
            pass
        return 1, {"status": "FAIL", "issues": [{"type": "OTHER", "severity": "CRITICAL", "episode": ep_id, "description": f"Audit timeout after {timeout_sec}s", "evidence_before": "", "evidence_after": ""}]}, {}
    except Exception as exc:
        try:
            Path(episode_file).unlink(missing_ok=True)
        except Exception:
            pass
        return 1, {"status": "FAIL", "issues": [{"type": "OTHER", "severity": "CRITICAL", "episode": ep_id, "description": f"Subprocess error: {exc}", "evidence_before": "", "evidence_after": ""}]}, {}

    # Extract JSON from stdout (first line that looks like JSON)
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    if result.returncode != 0:
        try:
            Path(episode_file).unlink(missing_ok=True)
        except Exception:
            pass
        return 1, {"status": "FAIL", "issues": [{"type": "OTHER", "severity": "CRITICAL", "episode": ep_id, "description": f"opencode exited {result.returncode}: {stderr[:300]}", "evidence_before": "", "evidence_after": ""}]}, {}

    try:
        Path(episode_file).unlink(missing_ok=True)
    except Exception:
        pass

    # Find first line that starts with {
    json_line = None
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            json_line = line
            break

    if not json_line:
        return 1, {"status": "FAIL", "issues": [{"type": "OTHER", "severity": "CRITICAL", "episode": ep_id, "description": f"No JSON line in output: {stdout[:300]}", "evidence_before": "", "evidence_after": ""}]}, {}

    try:
        raw = json.loads(json_line)
    except json.JSONDecodeError as exc:
        return 1, {"status": "FAIL", "issues": [{"type": "OTHER", "severity": "CRITICAL", "episode": ep_id, "description": f"JSON parse error: {exc} in line: {json_line[:200]}", "evidence_before": "", "evidence_after": ""}]}, {}

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
                        style: dict[str, Any] | None = None) -> Path:
    """Record an audit verdict in audit_failures.json.

    Failures are kept and appended; a PASS supersedes any earlier record for the
    same episode instead of being appended beside it. Without that, a fixed
    episode stayed on the list forever and the next audit read the stale text as
    if it were still the published draft. The style verdict rides along purely
    as a record; it never decides anything here.
    """
    failures_path = ROOT / "audit_failures.json"
    record = {
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "work": work_id,
        "episode": ep_id,
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

    if audit.get("status") == "FAIL":
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
    if not episode_json_path.is_file():
        print(f"episode not found: {episode_json_path}", file=sys.stderr)
        return 2
    if not args.prompt.is_file():
        print(f"prompt not found: {args.prompt}", file=sys.stderr)
        return 2

    # Extract HTML from episode JSON
    try:
        episode_data = json.loads(episode_json_path.read_text(encoding="utf-8"))
        episode_html = episode_data.get("html", "")
        if not episode_html:
            print(f"episode HTML empty: {episode_json_path}", file=sys.stderr)
            return 2
    except Exception as exc:
        print(f"episode JSON parse error: {exc}", file=sys.stderr)
        return 2

    print(f"Auditing {args.work_id}/{args.ep_id} …")
    # The bundle is built from published data, so a draft episode appears in its
    # own "previous chapters" excerpt. Strip it, or the auditor compares the new
    # episode against itself and calls it a duplicate retcon.
    sys.path.insert(0, str(ROOT))
    from build_context_bundle import strip_episode, strip_pending  # noqa: E402

    context_text = strip_pending(
        strip_episode(context_path.read_text(encoding="utf-8"), args.ep_id))
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
        path = write_audit_failure(args.work_id, args.ep_id, audit, style)
        print(f"FAIL written to {path}")
        return 1

    # Record the PASS too, so the day's verdict for every episode is readable in
    # one place without re-running the auditor.
    path = write_audit_failure(args.work_id, args.ep_id, audit, style)
    print(f"PASS recorded in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())