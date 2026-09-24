"""把视频王国学习收据单向桥接到 ACE Evolution Kernel。

只接受本仓库 ``research/external_learning_runs`` 下的 JSON 收据，只写入
ACE 的治理收据目录；不执行外部仓库，不上传素材，不改视频生产默认值。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


VIDEO_ROOT = Path(__file__).resolve().parents[1]
ACE_CORE_ROOT = Path(r"C:\tmp\ace_core")
ACE_ROOT = ACE_CORE_ROOT


def _latest_run() -> Path:
    runs = sorted((VIDEO_ROOT / "research" / "external_learning_runs").glob("EL-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not runs:
        raise FileNotFoundError("no_external_learning_run")
    return runs[0]


def publish(run_path: Path, out_path: Path | None = None) -> dict[str, object]:
    run_path = run_path.resolve()
    run_root = (VIDEO_ROOT / "research" / "external_learning_runs").resolve()
    if run_root not in run_path.parents:
        raise ValueError("run_must_be_inside_video_learning_runs")
    if not run_path.name.startswith("EL-") or run_path.suffix.lower() != ".json":
        raise ValueError("run_must_match_EL_json")
    if not run_path.is_file():
        raise FileNotFoundError(str(run_path))
    sys.path.insert(0, str(ACE_CORE_ROOT))
    from core.evolution_kernel import append_packets, ingest_video_run

    packets = ingest_video_run(run_path)
    target = out_path or (ACE_ROOT / "08_GOVERNANCE" / "video_learning_bridge" / "packets.jsonl")
    target = target.resolve()
    allowed_root = (ACE_ROOT / "08_GOVERNANCE" / "video_learning_bridge").resolve()
    if allowed_root not in target.parents:
        raise ValueError("out_must_be_inside_ace_governance_bridge")
    result = append_packets(packets, target)
    result.update({"run": str(run_path), "packets": len(packets), "production_integration": False})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, help="external_learning_runs 下的收据；省略则取最新")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    result = publish(args.run or _latest_run(), args.out)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
