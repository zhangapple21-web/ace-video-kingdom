#!/usr/bin/env python3
"""Prove quarantine holds an episode back without destroying it.

Added 2026-10-07 after eight published episodes were found carrying FAIL
verdicts. The requirement is narrow and exact: a failing episode must leave the
reader (desk.json and the public file) but stay in the authored source, because
the source is the only copy and a continuity defect is normally repairable.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("build_originals", HERE / "build_originals.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def main() -> int:
    original = {k: getattr(mod, k) for k in ("ROOT", "SOURCE", "PUBLIC", "DESK")}
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="quarantine_"))
    try:
        src = tmp / "originals_source" / "wtest"
        (src).mkdir(parents=True)
        (src / "work.json").write_text(json.dumps({
            "id": "wtest", "title": "W", "tone": "t", "format": "f",
            "status": "EP01–02 可读", "logline": "l", "chars": ["a"],
            "episodes": [
                {"id": "ep01", "no": 1, "title": "一", "beat": "b",
                 "blocks": [{"k": "scene", "place": "p", "time": "t", "light": "l"},
                            {"k": "cast", "present": ["a"]},
                            {"k": "para", "t": "x"},
                            {"k": "hook", "t": "y"}]},
                {"id": "ep02", "no": 2, "title": "二", "beat": "b",
                 "blocks": [{"k": "scene", "place": "p", "time": "t", "light": "l"},
                            {"k": "cast", "present": ["a"]},
                            {"k": "para", "t": "x"},
                            {"k": "hook", "t": "y"}]},
            ],
        }, ensure_ascii=False), encoding="utf-8")

        pub = tmp / "public" / "data" / "originals"
        pub.mkdir(parents=True)
        (pub / "wtest").mkdir()
        (pub / "desk.json").write_text(json.dumps(
            {"schema": "tinghe.originals.v1", "works": []}, ensure_ascii=False), encoding="utf-8")

        mod.ROOT = tmp
        mod.SOURCE = tmp / "originals_source"
        mod.PUBLIC = pub
        mod.DESK = pub / "desk.json"

        # No quarantine file at all -> everything publishes (the common case).
        check(mod.load_quarantine() == {}, "no quarantine.json means nothing is held back")
        mod.build()
        desk = json.loads((pub / "desk.json").read_text(encoding="utf-8"))
        check(len(desk["works"][0]["episodes"]) == 2, "both episodes published by default")
        check((pub / "wtest" / "ep02.json").is_file(), "ep02 rendered to public")

        # Hold ep02 back.
        (tmp / "quarantine.json").write_text(json.dumps({
            "schema": "tinghe.quarantine.v1",
            "held": [{"work": "wtest", "episode": "ep02", "reason": "re-audit pending"}],
        }, ensure_ascii=False), encoding="utf-8")
        check(mod.load_quarantine().get(("wtest", "ep02")) == "re-audit pending",
              "quarantine entry is read with its reason")

        mod.build()
        desk = json.loads((pub / "desk.json").read_text(encoding="utf-8"))
        ids = [e["id"] for e in desk["works"][0]["episodes"]]
        check(ids == ["ep01"], f"desk.json drops the held episode (got {ids})")
        check(not (pub / "wtest" / "ep02.json").exists(),
              "the held episode's file is removed from public, not just unlisted")
        check((pub / "wtest" / "ep01.json").is_file(), "the other episode is untouched")

        authored = json.loads((src / "work.json").read_text(encoding="utf-8"))
        check([e["id"] for e in authored["episodes"]] == ["ep01", "ep02"],
              "authored source still holds BOTH episodes (the only copy survives)")

        # Reversibility: removing the entry republishes.
        (tmp / "quarantine.json").write_text(json.dumps({"held": []}, ensure_ascii=False),
                                            encoding="utf-8")
        mod.build()
        desk = json.loads((pub / "desk.json").read_text(encoding="utf-8"))
        check(len(desk["works"][0]["episodes"]) == 2, "clearing quarantine republishes")
        check((pub / "wtest" / "ep02.json").is_file(), "republished file is back on disk")

        # Fail-closed: a corrupt control file must stop publication entirely.
        (tmp / "quarantine.json").write_text("{ not json", encoding="utf-8")
        try:
            mod.build()
            check(False, "corrupt quarantine.json blocks the build")
        except SystemExit as exc:
            check("quarantine" in str(exc), "corrupt quarantine.json blocks the build")

        print()
        if failures:
            print(f"FAILED {len(failures)} check(s):")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("RESULT: quarantine holds back without destroying, and is reversible")
        return 0
    finally:
        for k, v in original.items():
            setattr(mod, k, v)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
