"""Safely remove leaked chapter metadata and restore a bad migration.

Normal mode cleans the current chapter HTML. Restore mode recalculates each
chapter from an external pre-cleanup zip (with c001 optionally sourced from
its earliest local backup), checks the current bytes against the old migration
result, and atomically replaces only conflict-free files.

The command defaults to a dry run. Use ``--apply`` to write files. Restore
mode requires both ``--restore`` and ``--source-zip``.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CHAPTERS = ROOT / "sites" / "tinghe-archive" / "public" / "data" / "chapters"
DEFAULT_BACKUP_DIR = ROOT / ".migration_backups" / "strip_chapter_meta"
C001_EARLIEST_BACKUP = CHAPTERS / "c001.json.bak_pre_strip"

BR_RE = re.compile(r"<br\s*/?>", re.I)
P_RE = re.compile(r"<p(\s[^>]*)?>(.*?)</p\s*>", re.I | re.S)
NOTE_DIV_RE = re.compile(
    r"<div\b(?=[^>]*\bclass\s*=\s*(['\"])note\1)[^>]*>(.*?)</div\s*>",
    re.I | re.S,
)
TAG_RE = re.compile(r"<[^>]+>")

# These are retained verbatim in spirit so restore-mode conflict checks can
# reproduce the conversion performed by the faulty migration.
LEGACY_META_LABEL_PATTERNS = (
    re.compile(r"^\s*在场[：:].*$"),
    re.compile(r"^\s*不在场[：:].*$"),
    re.compile(r"^\s*[一-龥]{1,6}[：:]\s*未出场.*$"),
    re.compile(r"^\s*其他人[：:].*$"),
    # 本场变化： / 本场变化（承上）： allow a short bracketed qualifier
    re.compile(r"^\s*本场变化[^：:\n]{0,8}[：:].*$"),
)
LEGACY_INLINE_NOTE_RE = re.compile(r"^\s*【(?:事件走向|本波快照)】.*$")
LEGACY_BARE_BRACKET_LINE_RE = re.compile(r"^\s*【[^】]*】\s*$")
LEGACY_META_SUBLEVEL_RE = re.compile(
    r"^\s*(?:世界|关系|物件|未决|人物状态|新登场|已发生|未解决|"
    r"关键道具|一句话|时间|地点)[：:].*$"
)
LEGACY_HEADING_PARA_RE = re.compile(r"^<p>\s*#{1,6}\s+.*?</p>$", re.S | re.M)
LEGACY_NOTE_DIV_RE = re.compile(r"<div\s+class=['\"]note['\"]>.*?</div>", re.S | re.I)
LEGACY_CHANGE_INLINE_RE = re.compile(
    r"(?:<br>\s*)?本场变化[：:].*?(?=<br>|<p>|</p>|$)"
)
LEGACY_SNAPSHOT_INLINE_RE = re.compile(
    r"(?:<br>\s*)?【本波快照】.*?(?=<br>|<p>|</p>|$)"
)

# New cleaner: labels are recognized only at the beginning of a token line.
STRICT_UNSEEN_RE = re.compile(
    r"^\s*[一-龥]{1,6}\s*[：:]\s*未出场"
    r"(?:\s*[（(][^）)]*[）)])?\s*$"
)
PRESENCE_RE = re.compile(r"^\s*(?:在场|不在场)\s*[：:].*$")
OTHER_PREFIX_RE = re.compile(
    r"^\s*(?:<[^>]+>\s*)*其他人\s*[：:]\s*", re.I
)
CHANGE_START_RE = re.compile(r"^\s*本场变化\b[^\uff1a:\n]{0,8}[：:]")
SNAPSHOT_START_RE = re.compile(r"^\s*【本波快照[^】]*】")
EVENT_START_RE = re.compile(r"^\s*【事件走向】")
WAVE_HEADING_RE = re.compile(r"^\s*#{1,6}\s+wave_\d+\s*$", re.I)
META_SUBLEVEL_RE = re.compile(
    r"^\s*(?:世界|关系|物件|未决|人物状态|新登场|已发生|未解决|"
    r"关键道具|一句话|时间|地点)\s*[：:].*$"
)


class MigrationError(RuntimeError):
    """A planned migration cannot be safely applied."""


def _visible_text(value: str) -> str:
    return html_lib.unescape(TAG_RE.sub("", value))


def _legacy_line_should_drop(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return any(pat.match(stripped) for pat in LEGACY_META_LABEL_PATTERNS) or bool(
        LEGACY_INLINE_NOTE_RE.match(stripped)
        or LEGACY_BARE_BRACKET_LINE_RE.match(stripped)
        or LEGACY_META_SUBLEVEL_RE.match(stripped)
    )


def _legacy_strip_meta_from_html(html: str) -> str:
    """Reproduce the old broad conversion for restore conflict checking."""
    if not html:
        return html
    out = html
    new = LEGACY_NOTE_DIV_RE.sub("", out)
    if new != out:
        out = re.sub(r"(<br>\s*){2,}", "<br>", new)
        out = re.sub(r"<br>\s*</p>", "</p>", out)
        out = re.sub(r"<p>\s*<br>", "<p>", out)
    out = LEGACY_HEADING_PARA_RE.sub("", out)
    new = LEGACY_CHANGE_INLINE_RE.sub("", out)
    if new != out:
        out = re.sub(r"(<br>\s*){2,}", "<br>", new)
        out = re.sub(r"<br>\s*</p>", "</p>", out)
    new = LEGACY_SNAPSHOT_INLINE_RE.sub("", out)
    if new != out:
        out = re.sub(r"(<br>\s*){2,}", "<br>", new)
        out = re.sub(r"<br>\s*</p>", "</p>", out)

    def clean_paragraph(match: re.Match[str]) -> str:
        body = match.group(1)
        lines = body.split("<br>")
        kept = [line for line in lines if not _legacy_line_should_drop(line)]
        new_body = "<br>".join(kept)
        new_body = re.sub(r"(<br>\s*){2,}", "<br>", new_body)
        new_body = re.sub(r"^<br>\s*", "", new_body)
        new_body = re.sub(r"<br>\s*$", "", new_body)
        if not new_body.strip():
            return ""
        return "<p>" + new_body + "</p>"

    out = re.sub(r"<p>(.*?)</p>", clean_paragraph, out, flags=re.S)
    out = re.sub(r"(<br>\s*){2,}", "<br>", out)
    out = re.sub(r"<p>\s*</p>", "", out)
    out = re.sub(r"<br>\s*</p>", "</p>", out)
    out = re.sub(r"<p>\s*<br>", "<p>", out)
    return out.strip()


def _line_action(line: str, in_meta_block: bool) -> tuple[str, bool, bool]:
    """Return (new line, keep, next metadata-block state)."""
    visible = _visible_text(line)
    stripped = visible.strip()
    if not stripped:
        return line, False, in_meta_block
    if PRESENCE_RE.match(visible):
        return line, False, in_meta_block
    if STRICT_UNSEEN_RE.match(visible):
        return line, False, in_meta_block
    other = OTHER_PREFIX_RE.match(line)
    if other:
        remainder = line[other.end() :]
        if not _visible_text(remainder).strip():
            return remainder, False, in_meta_block
        return remainder, True, in_meta_block
    if WAVE_HEADING_RE.match(visible):
        return line, False, False
    if CHANGE_START_RE.match(visible):
        return line, False, True
    if SNAPSHOT_START_RE.match(visible):
        return line, False, True
    if EVENT_START_RE.match(visible):
        return line, False, False
    if in_meta_block and META_SUBLEVEL_RE.match(visible):
        return line, False, True
    if in_meta_block:
        return line, True, False
    return line, True, False


def _clean_br_lines(body: str) -> str:
    parts = BR_RE.split(body)
    separators = BR_RE.findall(body)
    kept: list[tuple[int, str]] = []
    in_meta_block = False
    for index, line in enumerate(parts):
        cleaned, keep, in_meta_block = _line_action(line, in_meta_block)
        if keep and _visible_text(cleaned).strip():
            kept.append((index, cleaned))
    if not kept:
        return ""
    output = kept[0][1]
    for _, line in kept[1:]:
        output += "<br>" + line
    return output


def _is_known_note_block(match: re.Match[str]) -> bool:
    content = match.group(2)
    visible = _visible_text(content).strip()
    return bool(CHANGE_START_RE.match(visible) or SNAPSHOT_START_RE.match(visible))


def _strip_meta_from_html(html: str, *, preserve_summary: bool = False) -> str:
    """Remove only bounded metadata tokens while preserving story text."""
    if not html or preserve_summary:
        return html

    out = NOTE_DIV_RE.sub(lambda m: "" if _is_known_note_block(m) else m.group(0), html)

    def clean_paragraph(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        body = match.group(2)
        if WAVE_HEADING_RE.match(_visible_text(body)):
            return ""
        new_body = _clean_br_lines(body)
        if not new_body.strip():
            return ""
        return f"<p{attrs}>{new_body}</p>"

    out = P_RE.sub(clean_paragraph, out)
    out = re.sub(r"<p(?:\s[^>]*)?>\s*</p\s*>", "", out, flags=re.I)
    return out.strip()


def _payload_from_bytes(raw: bytes) -> dict[str, Any]:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise MigrationError("chapter JSON root must be an object")
    return payload


def _serialize_payload(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def _source_newline(raw: bytes) -> bytes:
    """Return the trailing newline style of the source bytes (LF or CRLF)."""
    if raw.endswith(b"\r\n"):
        return b"\r\n"
    return b"\n"


def _serialize_payload_like(payload: dict[str, Any], template: bytes) -> bytes:
    """Serialize payload using the trailing newline style of ``template``."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    style = _source_newline(template)
    if body.endswith(b"\n"):
        body = body[:-1]
    return body + style


def _safe_transform_bytes(raw: bytes, *, preserve_summary: bool = False) -> bytes:
    payload = _payload_from_bytes(raw)
    payload["html"] = _strip_meta_from_html(
        str(payload.get("html") or ""), preserve_summary=preserve_summary
    )
    return _serialize_payload_like(payload, raw)


def _legacy_transform_bytes(raw: bytes) -> bytes:
    payload = _payload_from_bytes(raw)
    payload["html"] = _legacy_strip_meta_from_html(str(payload.get("html") or ""))
    return _serialize_payload_like(payload, raw)


def _atomic_replace(path: Path, expected: bytes, replacement: bytes) -> None:
    if path.read_bytes() != expected:
        raise MigrationError(f"concurrent change detected: {path}")
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(replacement)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _write_backup_once(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise MigrationError(f"backup already exists, refusing to overwrite: {path}") from exc


def process_file(path: Path, dry_run: bool) -> tuple[bool, str]:
    """Clean one current file; retained for callers of the original utility."""
    raw = path.read_bytes()
    payload = _payload_from_bytes(raw)
    old_html = str(payload.get("html") or "")
    new_html = _strip_meta_from_html(old_html, preserve_summary=path.stem == "c999")
    if new_html == old_html:
        return False, old_html
    if not dry_run:
        payload["html"] = new_html
        _atomic_replace(path, raw, _serialize_payload(payload))
    return True, new_html


def _chapter_files(target_ids: set[str]) -> list[Path]:
    files = sorted(CHAPTERS.glob("c*.json"))
    if target_ids:
        files = [path for path in files if path.stem in target_ids]
    return files


def _source_bytes(
    path: Path, archive: zipfile.ZipFile, c001_source: Path
) -> bytes:
    if path.stem == "c001" and c001_source.exists():
        return c001_source.read_bytes()
    entry = archive.getinfo(f"{path.name}")
    return archive.read(entry)


def _planned_restore(
    path: Path, source: bytes
) -> tuple[bytes, bytes]:
    current = path.read_bytes()
    old_result = _legacy_transform_bytes(source)
    if current != source and current != old_result:
        raise MigrationError(f"concurrent or unknown current bytes: {path}")
    if path.stem == "c999":
        replacement = source
    else:
        replacement = _safe_transform_bytes(source, preserve_summary=False)
    return current, replacement


def _run(args: argparse.Namespace) -> int:
    if not CHAPTERS.exists():
        print(f"chapters dir not found: {CHAPTERS}", file=sys.stderr)
        return 2
    if args.apply and args.dry_run:
        print("--apply and --dry-run cannot be used together", file=sys.stderr)
        return 2
    if args.restore and not args.source_zip:
        print("--restore requires --source-zip", file=sys.stderr)
        return 2

    target_ids = {item.strip() for item in args.ids.split(",") if item.strip()}
    files = _chapter_files(target_ids)
    if args.limit:
        files = files[: args.limit]
    plans: list[tuple[Path, bytes, bytes]] = []
    archive: zipfile.ZipFile | None = None
    try:
        if args.restore:
            archive = zipfile.ZipFile(args.source_zip)
        for path in files:
            if args.restore:
                try:
                    source = _source_bytes(path, archive, args.c001_source)
                except KeyError as exc:
                    raise MigrationError(f"source archive lacks {path.name}") from exc
                current, replacement = _planned_restore(path, source)
            else:
                current = path.read_bytes()
                payload = _payload_from_bytes(current)
                replacement = _safe_transform_bytes(
                    current, preserve_summary=path.stem == "c999"
                )
            if replacement != current:
                plans.append((path, current, replacement))
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile, MigrationError) as exc:
        print(f"blocked: {exc}", file=sys.stderr)
        return 3
    finally:
        if archive is not None:
            archive.close()

    tag = "would change" if not args.apply else "changed"
    print(f"scanned={len(files)} {tag}={len(plans)}")
    for path, _, _ in plans:
        if args.verbose or not args.apply:
            print(("[DRY] " if not args.apply else "") + path.name)
    if not args.apply or not plans:
        return 0

    backup_dir = Path(args.backup_dir)
    try:
        # Pre-create no files until every current byte has passed the plan.
        for path, expected, _ in plans:
            if path.read_bytes() != expected:
                raise MigrationError(f"concurrent change detected: {path}")
        for path, expected, replacement in plans:
            backup_path = backup_dir / path.name
            _write_backup_once(backup_path, expected)
            _atomic_replace(path, expected, replacement)
    except (OSError, MigrationError) as exc:
        print(f"blocked during apply: {exc}", file=sys.stderr)
        return 3
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="preview only (default)")
    parser.add_argument("--apply", action="store_true", help="write approved changes")
    parser.add_argument("--restore", action="store_true", help="recalculate from --source-zip")
    parser.add_argument("--source-zip", type=Path, help="pre-cleanup chapter zip")
    parser.add_argument(
        "--c001-source", type=Path, default=C001_EARLIEST_BACKUP,
        help="earliest original c001 JSON (default: local .bak_pre_strip)",
    )
    parser.add_argument(
        "--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR,
        help="non-public, write-once backup directory",
    )
    parser.add_argument("--limit", type=int, default=0, help="limit scanned files")
    parser.add_argument("--ids", default="", help="comma-separated chapter ids")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
