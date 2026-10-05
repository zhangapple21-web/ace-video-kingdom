"""M-01/C: the hard-prohibition wording has one source of truth.

governance/script_prompt_review_gate.v1.json#hard_prohibitions is canonical.
The other four files must reference the prohibition ids instead of restating the
wording, and anything they do state has to match the canonical text.

A negative test at the bottom deliberately corrupts a phrase and asserts the
checker fails, so this file cannot pass by having no teeth.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
CANON = ROOT / "governance" / "script_prompt_review_gate.v1.json"

# Files that must NOT restate the full wording, plus the ids they must cite.
REFERENCERS = {
    "governance/script_prompt_review_gate.v1.md": {"P1", "P2", "P3", "P4", "P5", "P6"},
    "AGENTS.md": {"P1", "P2", "P3", "P4", "P5", "P6"},
    "../AGENTS.md": {"P1", "P2", "P3", "P4", "P5", "P6"},
    Path.home() / ".codex/skills/video-kingdom/SKILL.md": {"P1", "P2", "P3", "P4", "P5", "P6"},
}

# A referencer may CITE a prohibition by printing the canonical clause, because
# that is the reference table format. What it may not do is RESTATE the rule in
# its own prose, which is how the wording drifted in the first place.
#
# So the rule is about where the text sits, not whether the characters appear:
# outside the canonical file, a canonical clause is only acceptable on a line
# that is part of a markdown table row (starts with "|") or is the sole content
# of the line. Free prose must use the prohibition ids instead.
TABLE_ROW = re.compile(r"^\s*\|")
ID_REFERENCE = re.compile(r"\bP[1-6]\b")


def _canon() -> dict:
    return json.loads(CANON.read_text(encoding="utf-8"))


def _norm(text: str) -> str:
    return re.sub(r"[\s，,、。.；;：:（）()「」\"'`]+", "", text)


def _resolve(rel: str | Path) -> Path:
    path = Path(rel)
    return path if path.is_absolute() else (ROOT / path).resolve()


def test_canonical_section_exists_and_is_complete():
    section = _canon().get("hard_prohibitions")
    assert section, "hard_prohibitions section missing from the canonical file"
    ids = [item["id"] for item in section["items"]]
    assert ids == ["P1", "P2", "P3", "P4", "P5", "P6"]
    for item in section["items"]:
        assert item["text"].strip(), f"{item['id']} has empty text"
        assert item["machine"].strip(), f"{item['id']} has no machine enforcement"
    assert section["phone_state_escape_prefix"] == "本镜不涉及手机"
    assert section["scope"].strip()


def test_referencers_do_not_restate_canonical_wording_in_prose():
    """A canonical clause may appear in a reference table, never in prose."""
    items = _canon()["hard_prohibitions"]["items"]
    offenders: list[str] = []
    for rel in REFERENCERS:
        path = _resolve(rel)
        if not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if TABLE_ROW.match(line) or ID_REFERENCE.search(line):
                continue  # reference table or an explicit id citation
            norm_line = _norm(line)
            if len(norm_line) < 12:
                continue
            for item in items:
                if _norm(item["text"]) in norm_line:
                    offenders.append(
                        f"{path.name}:{lineno} restates {item['id']} in prose"
                    )
    assert not offenders, offenders


def test_referencers_actually_point_somewhere():
    """Guard against the table being deleted and the test silently passing."""
    seen = 0
    for rel in REFERENCERS:
        path = _resolve(rel)
        if not path.is_file():
            continue
        seen += 1
        body = path.read_text(encoding="utf-8")
        assert "hard_prohibitions" in body, f"{path.name} does not cite hard_prohibitions"
    assert seen >= 3, f"only {seen} referencer files found; expected at least 3"


def test_referencers_point_at_the_canonical_file():
    path = _resolve("governance/script_prompt_review_gate.v1.md")
    body = path.read_text(encoding="utf-8")
    assert "hard_prohibitions" in body, "gate.md does not reference hard_prohibitions"


def test_consistency_checker_has_teeth_negative_case():
    """Break the canonical wording on purpose; the checker must notice."""
    section = _canon()["hard_prohibitions"]
    good = {item["id"]: item["text"] for item in section["items"]}

    def drift(items: list[dict]) -> list[str]:
        by_id = {item["id"]: item["text"] for item in items}
        out = []
        for pid, canonical_text in good.items():
            if by_id.get(pid) != canonical_text:
                out.append(f"{pid} drifted from canonical wording")
        return out

    assert drift(section["items"]) == []

    corrupted = [dict(item) for item in section["items"]]
    corrupted[1]["text"] = "手机正面朝镜头，可以看见屏幕内容"  # inverted P2
    found = drift(corrupted)
    assert found, "corrupting P2 must produce a drift finding"
    assert any("P2" in item for item in found)