"""安全、幂等的公开资料学习采集器。

它只抓取登记过的公开一手仓库元数据/README，形成最小学习单元和验证候选。
不执行外部代码、不上传本地文件、不创建媒体任务、不改生产路由；候选必须
经过本地 baseline→change→test→evaluation→painful_review 才能晋升。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "research" / "external_learning_sources.v1.json"
LEDGER = ROOT / "research" / "public_street_learning_ledger.v1.json"
RUN_DIR = ROOT / "research" / "external_learning_runs"
USER_AGENT = "ACE-video-kingdom-public-learning/1.0"
MAX_README_BYTES = 256 * 1024
ALLOWED_LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0"}
PLACEHOLDER = {"", "unknown", "未知", "none", "null"}
LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _get_json(url: str, opener: Callable[..., Any] | None = None) -> dict[str, Any]:
    open_fn = opener or urllib.request.urlopen
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with open_fn(req, timeout=20) as response:
        payload = response.read(512 * 1024)
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("source metadata must be an object")
    return value


def _get_text(url: str, opener: Callable[..., Any] | None = None) -> bytes:
    open_fn = opener or urllib.request.urlopen
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/plain"})
    with open_fn(req, timeout=20) as response:
        return response.read(MAX_README_BYTES + 1)[:MAX_README_BYTES]


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default


def _local_context() -> dict[str, Any]:
    failure = ROOT / "research" / "failure_replay_db.v2.jsonl"
    capability = ROOT / "research" / "capability_growth.v1.json"
    failures = 0
    if failure.exists():
        failures = sum(1 for line in failure.read_text(encoding="utf-8").splitlines() if line.strip())
    growth = _load_json(capability, {})
    caps = growth.get("capabilities", {}) if isinstance(growth, dict) else {}
    return {"failure_replay_count": failures, "promoted_capability_count": len(caps) if isinstance(caps, dict) else 0}


def _existing_keys(ledger: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for entry in ledger.get("entries", []) if isinstance(ledger, dict) else []:
        if isinstance(entry, dict):
            key = str(entry.get("source_content_key") or "")
            if key:
                keys.add(key)
    return keys


def _headings(readme: str) -> list[str]:
    return [m.group(1).strip()[:120] for m in re.finditer(r"^#{1,3}\s+(.+?)\s*$", readme, re.M)][:8]


def collect(*, opener: Callable[..., Any] | None = None, now: datetime | None = None) -> dict[str, Any]:
    config = _load_json(SOURCES, {})
    if not isinstance(config, dict) or not isinstance(config.get("sources"), list):
        raise ValueError("external learning source registry is invalid")
    ledger = _load_json(LEDGER, {})
    if not isinstance(ledger, dict):
        ledger = {"contract_version": "ace.video_kingdom.public_street_learning_ledger.v1", "entries": []}
    keys = _existing_keys(ledger)
    now = now or datetime.now(LOCAL_TZ)
    run_id = "EL-" + now.strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:8]
    records: list[dict[str, Any]] = []
    new_entries: list[dict[str, Any]] = []
    for source in config["sources"]:
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("source_id") or "").strip()
        try:
            metadata = _get_json(str(source["api_url"]), opener)
            readme_bytes = _get_text(str(source["readme_url"]), opener)
            readme_sha = _sha256(readme_bytes)
            license_info = metadata.get("license") if isinstance(metadata.get("license"), dict) else {}
            spdx = str(license_info.get("spdx_id") or "UNKNOWN")
            content_key = f"{source_id}:{readme_sha}"
            changed = content_key not in keys
            status = "NEW_OR_CHANGED" if changed else "UNCHANGED"
            record = {
                "source_id": source_id,
                "status": status,
                "api_url": source.get("api_url"),
                "readme_url": source.get("readme_url"),
                "repository_sha": str(metadata.get("default_branch") or "") + ":" + str(metadata.get("pushed_at") or ""),
                "readme_sha256": readme_sha,
                "source_content_key": content_key,
                "license": spdx,
                "license_decision": "ALLOW_FOR_RESEARCH" if spdx in ALLOWED_LICENSES else "RESEARCH_ONLY_LICENSE_REVIEW",
                "focus": source.get("focus"),
                "observable_headings": _headings(readme_bytes.decode("utf-8", errors="replace")),
                "production_authority": "NONE",
                "promotion_status": "NOT_PROMOTED",
                "next_probe": "用本地虚构样本做一次隔离 A/B；记录 baseline/change/test/evaluation/painful_review 后再决定",
            }
            records.append(record)
            if changed:
                new_entries.append({
                    "entry_id": f"psl_{now.strftime('%Y%m%d')}_{source_id}_{readme_sha[:8]}",
                    "date": now.date().isoformat(),
                    "source_url": source.get("readme_url"),
                    "source_kind": "PUBLIC_OPEN_SOURCE_REPOSITORY",
                    "source_content_key": content_key,
                    "license_or_availability": spdx,
                    "linked_public_repositories": [source.get("api_url")],
                    "problem_observed": "外部仓库公开文档出现可复核的工作流/审计/恢复机制候选，尚未证明适合本项目。",
                    "minimum_mechanism": source.get("focus"),
                    "local_fit": "对照本地失败复盘与能力账本，先做影子验证，不进入生产控制面。",
                    "limitations": ["仅采集公开元数据和 README", "未执行外部代码", "未证明对本项目有收益"],
                    "decision": "REVIEW_REQUIRED",
                    "next_verification": record["next_probe"],
                    "production_integration": False,
                })
        except (KeyError, OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            records.append({"source_id": source_id, "status": "FETCH_FAILED", "error": type(exc).__name__ + ": " + str(exc), "production_authority": "NONE"})
    return {
        "schema": "video_kingdom.external_learning_run.v1",
        "run_id": run_id,
        "started_at": now.isoformat(),
        "source_boundary": "PUBLIC_PRIMARY_SOURCES_ONLY",
        "local_context": _local_context(),
        "records": records,
        "new_ledger_entries": new_entries,
        "promotion": {"status": "NONE", "reason": "采集阶段不能自动晋升能力", "production_integration": False},
    }


def persist(result: dict[str, Any], *, out_dir: Path = RUN_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (result["run_id"] + ".json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ledger = _load_json(LEDGER, {"contract_version": "ace.video_kingdom.public_street_learning_ledger.v1", "scope": "FREE_ZONE_RESEARCH_ONLY", "production_integration": False, "entries": []})
    if not isinstance(ledger, dict):
        ledger = {"contract_version": "ace.video_kingdom.public_street_learning_ledger.v1", "scope": "FREE_ZONE_RESEARCH_ONLY", "production_integration": False, "entries": []}
    known = _existing_keys(ledger)
    for entry in result.get("new_ledger_entries", []):
        if entry.get("source_content_key") not in known:
            ledger.setdefault("entries", []).append(entry)
            known.add(str(entry.get("source_content_key")))
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=RUN_DIR)
    args = parser.parse_args(argv)
    result = collect()
    out = persist(result, out_dir=args.out_dir)
    print(json.dumps({"run_id": result["run_id"], "out": str(out), "new": len(result["new_ledger_entries"]), "failed": sum(r.get("status") == "FETCH_FAILED" for r in result["records"])}, ensure_ascii=False))
    return 0 if result["records"] and not all(r.get("status") == "FETCH_FAILED" for r in result["records"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
