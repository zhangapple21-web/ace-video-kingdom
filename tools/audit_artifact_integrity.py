"""Report, per shot, which artifact facts still hold — and which do not.

Why this exists
---------------
``tools/artifact_facts.py`` can answer five separate questions about a
generation record, and the renderer and assembler now enforce the answer. But
nothing looked across the whole project and said which shots are actually
deliverable. That gap is how three ``COMPLETED`` records sat in
``experiments/agnes_tasks.json`` whose files were gone and whose provider tasks
had been evicted: correct per-shot behaviour, invisible aggregate state.

This is a read-only inspection. It never downloads, never calls a provider and
never edits a record. Its verdict is about artifact availability only and
approves nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.atomic_io import atomic_write_json
from tools import artifact_facts
from tools.artifact_facts import LOCAL_VERIFIED

ROOT = Path(__file__).resolve().parents[1]

sys.stdout.reconfigure(encoding="utf-8")  # Bug #1 fix: prevent UnicodeEncodeError on GBK console

RECEIPT_SCHEMA = "video_kingdom.artifact_integrity_audit.v1"


def load_records(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else [data]
    return [row for row in rows if isinstance(row, dict) and row.get("shot_id")]


MEDIA_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def find_by_hash(expected_sha256: str, roots: list[Path], *, size_hint: int | None = None) -> list[str]:
    """Locate files whose *content* matches a recorded hash.

    Matching by content rather than by filename is the only trustworthy way to
    answer "is this media still anywhere?". Names get rewritten when material is
    archived or re-exported, so a same-named file proves nothing and a
    differently-named file can still be the exact artifact. Recorded byte counts
    are used to skip obvious non-matches before hashing.

    Read-only. Returns locations; never moves or edits anything.
    """
    if not expected_sha256:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                if Path(name).suffix.lower() not in MEDIA_SUFFIXES:
                    continue
                candidate = Path(dirpath) / name
                key = str(candidate)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    if size_hint and candidate.stat().st_size != size_hint:
                        continue
                    if hashlib.sha256(candidate.read_bytes()).hexdigest() == expected_sha256:
                        found.append(key)
                except OSError:
                    continue
    return found


def audit(
    manifests: list[Path],
    *,
    verify_hash: bool = True,
    roots: list[Path] | None = None,
    search_roots: list[Path] | None = None,
) -> dict:
    """Assess every record in every manifest. Fails closed on unreadable input."""
    search_roots = list(search_roots or [])
    resolve_roots = list(roots or [ROOT])
    shots: list[dict] = []
    unreadable: list[str] = []
    for manifest in manifests:
        try:
            rows = load_records(manifest)
        except (OSError, ValueError) as error:
            unreadable.append(f"{manifest}: {error}")
            continue
        for record in rows:
            assessment = artifact_facts.assess(
                record,
                manifest_dir=manifest.resolve().parent,
                roots=resolve_roots,
                verify_hash=verify_hash,
            )
            shot = {
                "shot_id": record.get("shot_id"),
                "manifest": str(manifest),
                "status": record.get("status"),
                "generation": assessment["generation"]["generated"],
                "generation_source": assessment["generation"]["source"],
                "local": assessment["local"]["state"],
                "remote": assessment["remote"]["state"],
                "recoverable": assessment["recoverable"],
                "delivery_ready": assessment["delivery_ready"],
                "block_reason": artifact_facts.delivery_block_reason(assessment),
            }
            # An absent local artifact is only "gone" once the recorded content
            # hash has been looked for elsewhere. Matching on hash rather than
            # filename is what makes that claim true.
            if shot["local"] != LOCAL_VERIFIED and search_roots:
                matches = find_by_hash(
                    str(record.get("artifact_sha256") or ""),
                    search_roots,
                    size_hint=record.get("bytes") if isinstance(record.get("bytes"), int) else None,
                )
                if matches:
                    shot["recoverable_offline"] = True
                    shot["recovery_locations"] = matches
                else:
                    shot["recoverable_offline"] = False
            shots.append(shot)

    not_ready = [shot for shot in shots if not shot["delivery_ready"]]
    unrecoverable = [
        shot for shot in shots
        if shot["generation"] and not shot["recoverable"] and not shot.get("recoverable_offline")
    ]
    recovered_offline = [shot for shot in shots if shot.get("recoverable_offline")]
    by_local: dict[str, int] = {}
    for shot in shots:
        by_local[shot["local"]] = by_local.get(shot["local"], 0) + 1

    if unreadable:
        verdict = "BLOCKED"
    elif not_ready:
        verdict = "REVIEW_REQUIRED"
    else:
        verdict = "PASS"

    return {
        "schema": RECEIPT_SCHEMA,
        "verdict": verdict,
        "approves_delivery": False,
        "totals": {
            "records": len(shots),
            "delivery_ready": len(shots) - len(not_ready),
            "not_delivery_ready": len(not_ready),
            "generated_but_unrecoverable": len(unrecoverable),
            "recovered_offline": len(recovered_offline),
        },
        "local_states": by_local,
        "searched_roots": [str(root) for root in resolve_roots],
        "content_search_roots": [str(root) for root in search_roots],
        "not_delivery_ready": not_ready,
        "generated_but_unrecoverable": unrecoverable,
        "recovered_offline": recovered_offline,
        "unreadable_manifests": unreadable,
        "note": (
            "Artifact availability only. A delivery_ready shot still requires the creative, "
            "continuity, audio and delivery gates; this audit approves nothing."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only artifact availability audit across generation manifests.")
    parser.add_argument("--manifest", type=Path, action="append", required=True, help="manifest to audit; repeatable")
    parser.add_argument("--search-root", type=Path, action="append", default=[],
                        help="also look for absent artifacts here, matching on recorded content hash; repeatable")
    parser.add_argument("--output", type=Path, help="write the receipt here")
    parser.add_argument("--no-hash", action="store_true", help="skip content hashing; reports presence only")
    parser.add_argument("--quiet", action="store_true", help="print the receipt JSON only")
    args = parser.parse_args(argv)

    receipt = audit(args.manifest, verify_hash=not args.no_hash, search_roots=args.search_root)
    if args.output:
        atomic_write_json(args.output, receipt)
    if args.quiet:
        print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        totals = receipt["totals"]
        print(f"verdict              {receipt['verdict']}")
        print(f"records              {totals['records']}")
        print(f"delivery ready       {totals['delivery_ready']}")
        print(f"not delivery ready   {totals['not_delivery_ready']}")
        print(f"generated, no way back {totals['generated_but_unrecoverable']}")
        print(f"recovered by content    {totals['recovered_offline']}")
        print(f"local states         {receipt['local_states']}")
        for shot in receipt["recovered_offline"]:
            for location in shot["recovery_locations"]:
                print(f"  * {shot['shot_id']} found at {location}")
        for shot in receipt["not_delivery_ready"]:
            if shot.get("recoverable_offline"):
                continue
            print(f"  - {shot['shot_id']}: {shot['block_reason']}")
        for note in receipt["unreadable_manifests"]:
            print(f"  ! {note}")
        if args.output:
            print(f"receipt written: {args.output}")
    return 0 if receipt["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
