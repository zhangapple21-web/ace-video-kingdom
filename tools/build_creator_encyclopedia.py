"""Build a conservative, Quartz-compatible creator encyclopedia export.

This is a creator-layer read model. It never edits wave truth, never infers
family/relationship facts, and never emits production contracts. Every record
keeps its source wave/scene and unknown fields stay explicit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCENE_RE = re.compile(r"^第\s*(\d+)\s*场(?:续)?[｜|].*$", re.M)
FIELD_RE = re.compile(r"(?:^|[；;])\s*(世界|关系|物件|未决|已发生|新登场|离场/生死|关键道具|世界开门还是收束|一句话)\s*[：:]\s*(.*?)(?=(?:[；;])\s*(?:世界|关系|物件|未决|已发生|新登场|离场/生死|关键道具|世界开门还是收束|一句话)\s*[：:]|$)")
FAMILY_WORDS = ("父", "母", "娘", "爹", "祖", "姐", "妹", "兄", "弟", "养女", "养子", "妻", "夫", "孙", "侄", "叔", "姑", "婶", "家族", "宗族", "本支", "三房", "二房")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def dump(path: Path, obj: Any) -> None:
    write(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_items(value: str) -> list[str]:
    value = value.strip(" 。")
    if not value or value.upper() == "UNKNOWN":
        return []
    # Split only at top-level separators. Chinese commas inside a parenthesis
    # are character descriptions, not separate people.
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in value:
        if ch in "（(":
            depth += 1
        elif ch in "）)" and depth:
            depth -= 1
        if ch in "、,，;；" and depth == 0:
            item = "".join(buf).strip()
            if item:
                parts.append(item)
            buf = []
        else:
            buf.append(ch)
    item = "".join(buf).strip()
    if item:
        parts.append(item)
    return parts


def clean_name(raw: str) -> str:
    value = raw.strip(" 、，;；")
    # Keep the stable display label before an optional descriptive tail. Any
    # alias in parentheses remains evidence in the scene source, not a silent
    # identity merge.
    value = re.split(r"[（(]", value, maxsplit=1)[0].strip()
    value = value.strip(" 、，;；）)")
    value = re.sub(r"\s+(?:后到|先到|离场|未到)$", "", value)
    return value.strip(" 、，")


def extract_field(text: str, label: str) -> str:
    # Presence/relationship/state labels are contractual one-line fields.
    # Do not let the following scene prose become part of a character name.
    if label in ("在场", "人物状态", "关系状态"):
        m = re.search(r"(?m)^\s*%s\s*[：:]([^\n]*)" % re.escape(label), text)
        return m.group(1).strip() if m else "UNKNOWN"
    m = re.search(r"(?:^|\n)\s*%s\s*[：:](.*?)(?=\n(?:环境|在场|其他人|本场变化|【本波快照】|第\s*\d+\s*场)|\Z)" % re.escape(label), text, re.S)
    return m.group(1).strip() if m else "UNKNOWN"


def parse_change(raw: str) -> dict[str, str]:
    body = raw.strip()
    out = {"world_change": "UNKNOWN", "relationship_change": "UNKNOWN", "props": "UNKNOWN", "unresolved": "UNKNOWN"}
    # Models sometimes put all fields on one line and sometimes use lines.
    for key, aliases in {
        "world_change": ("世界", "已发生", "本场变化"),
        "relationship_change": ("关系",),
        "props": ("物件", "关键道具"),
        "unresolved": ("未决", "未解决"),
    }.items():
        for alias in aliases:
            m = re.search(r"%s\s*[：:]\s*(.*?)(?=(?:；|;|\n)\s*(?:世界|已发生|本场变化|关系|物件|关键道具|未决|未解决)\s*[：:]|\Z)" % re.escape(alias), body, re.S)
            if m:
                out[key] = m.group(1).strip()
                break
    return out


def scene_blocks(wave_path: Path) -> list[tuple[int, str, str]]:
    text = read(wave_path).strip()
    matches = list(SCENE_RE.finditer(text))
    blocks: list[tuple[int, str, str]] = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else text.find("【本波快照】", match.end())
        if end < 0:
            end = len(text)
        heading = match.group(0).strip()
        number = int(match.group(1))
        blocks.append((number, heading, text[match.start():end].strip()))
    return blocks


def parse_run(run_dir: Path) -> dict[str, Any]:
    waves_dir = run_dir / "world_live_waves"
    scenes: list[dict[str, Any]] = []
    names: set[str] = set()
    places: dict[str, dict[str, Any]] = {}
    props: dict[str, dict[str, Any]] = {}
    relationships: list[dict[str, Any]] = []
    family_records: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []

    for wave_path in sorted(waves_dir.glob("wave_*.md")):
        wave = int(re.search(r"(\d+)", wave_path.stem).group(1))
        text = read(wave_path)
        if "【本波快照】" in text:
            snapshots.append({"wave": wave, "source_file": wave_path.name, "raw": text.split("【本波快照】", 1)[1].strip()})
        for scene_no, heading, block in scene_blocks(wave_path):
            parts = re.split(r"[｜|]", heading)
            time_label = parts[1].strip() if len(parts) > 1 else "UNKNOWN"
            place_label = parts[-1].strip() if len(parts) > 2 else "UNKNOWN"
            present_raw = extract_field(block, "在场")
            present = [clean_name(x) for x in split_items(present_raw)]
            present = [x for x in present if x and "其余人物" not in x and x.upper() != "UNKNOWN"]
            names.update(present)
            place_id = "place-" + hashlib.sha1(place_label.encode("utf-8")).hexdigest()[:10]
            places.setdefault(place_id, {"id": place_id, "name": place_label, "status": "stated", "sources": []})["sources"].append({"wave": wave, "scene": scene_no})
            change_raw = extract_field(block, "本场变化")
            change = parse_change(change_raw)
            for item in split_items(change["props"]):
                prop_id = "prop-" + hashlib.sha1(item.encode("utf-8")).hexdigest()[:10]
                props.setdefault(prop_id, {"id": prop_id, "name": item, "status": "stated", "sources": []})["sources"].append({"wave": wave, "scene": scene_no})
            rel_statement = change["relationship_change"]
            if rel_statement != "UNKNOWN":
                participants = sorted({n for n in names if n and n in rel_statement})
                rec = {"id": f"rel-s{scene_no:03d}", "participants": participants or ["UNKNOWN"], "statement": rel_statement, "status": "stated", "source": {"wave": wave, "scene": scene_no, "file": wave_path.name}}
                relationships.append(rec)
                if any(w in rel_statement for w in FAMILY_WORDS):
                    family_records.append({"id": f"family-s{scene_no:03d}", "participants": participants or ["UNKNOWN"], "statement": rel_statement, "status": "stated_not_resolved", "source": rec["source"]})
            scenes.append({
                "id": f"S{scene_no:03d}",
                "number": scene_no,
                "wave": wave,
                "heading": heading,
                "time": time_label,
                "place": {"id": place_id, "name": place_label},
                "present": present,
                "character_state": extract_field(block, "人物状态"),
                "relationship_state": extract_field(block, "关系状态"),
                "happened": change["world_change"],
                "props": change["props"],
                "unresolved": change["unresolved"],
                "source": {"file": wave_path.name, "sha256": sha256(wave_path)},
                "raw_available": True,
            })

    # Initial anchors are explicit seed entities, not inferred from later text.
    for cid, path in (("C001", run_dir / "C001.persona_dna.v1.json"), ("C002", run_dir / "C002.persona_dna.v1.json")):
        if path.exists():
            data = json.loads(read(path))
            names.add("周培" if cid == "C001" else "林墨")

    characters = []
    stable_ids = {"周培": "C001", "林墨": "C002"}
    for name in sorted(names):
        appearances = [s["id"] for s in scenes if name in s["present"]]
        characters.append({"id": stable_ids.get(name, "char-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]), "name": name, "aliases": [], "appearances": appearances, "status": "stated", "identity_resolution": "stable_anchor" if name in stable_ids else "UNKNOWN", "family_relations": "UNKNOWN unless explicitly stated in family_records", "source_count": len(appearances)})

    receipt = {}
    receipt_path = run_dir / "world_live_receipt.v1.json"
    if receipt_path.exists():
        receipt = json.loads(read(receipt_path))
    latest_snapshot = snapshots[-1] if snapshots else {"raw": "UNKNOWN"}
    return {
        "schema": "video_kingdom.creator_encyclopedia.v1",
        "layer": "CREATOR_LIVE",
        "production_integration": False,
        "source_run": str(run_dir.relative_to(ROOT)).replace("\\", "/") if run_dir.is_relative_to(ROOT) else str(run_dir),
        "source_of_truth": "wave markdown files; summaries are derived only",
        "no_invention": True,
        "world": {"title": "莲蓬鬼话", "chapter": "残荷诡影", "status": receipt.get("closed_by_world", False) and "CLOSED" or "LIVE", "latest_snapshot": latest_snapshot},
        "characters": characters,
        "places": sorted(places.values(), key=lambda x: x["name"]),
        "family_relations": family_records,
        "relationships": relationships,
        "props": sorted(props.values(), key=lambda x: x["name"]),
        "events": [{"id": f"event-s{s['number']:03d}", "scene_id": s["id"], "who_did_what": "UNKNOWN; see scene body", "world_change": s["happened"], "relationship_change": s["relationship_state"], "new_information": s["happened"], "left_open": s["unresolved"], "status": "stated_from_scene", "source": s["source"]} for s in scenes],
        "scenes": scenes,
        "snapshots": snapshots,
        "unknown_policy": "未在正文明确写出的家族关系、动机、身份、时间和因果保持 UNKNOWN；不由百科生成器补写。",
    }


def md_frontmatter(title: str, tags: list[str]) -> str:
    return "---\ntitle: %s\ntags: [%s]\n---\n\n" % (title, ", ".join(tags))


def render(data: dict[str, Any], out_dir: Path) -> None:
    content = out_dir / "content"
    dump(out_dir / "data" / "encyclopedia.v1.json", data)
    dump(out_dir / "data" / "characters.v1.json", {"characters": data["characters"]})
    dump(out_dir / "data" / "relationships.v1.json", {"relationships": data["relationships"], "family_relations": data["family_relations"]})
    dump(out_dir / "data" / "events.v1.json", {"events": data["events"], "scenes": data["scenes"]})
    dump(out_dir / "data" / "places_props.v1.json", {"places": data["places"], "props": data["props"]})
    write(content / "index.md", md_frontmatter("残荷诡影｜创者百科", ["creator-live", "残荷诡影"]) + "# 残荷诡影｜创者百科\n\n这是从 CREATOR_LIVE 真源派生的只读百科。原始推演仍是唯一真源，本百科不锁主线、不替人工定结局。\n\n- [[世界总览]]\n- [[人物索引]]\n- [[关系与家族]]\n- [[事件索引]]\n- [[地点与道具]]\n\n> 当前状态：%s；场次：%s；未知信息保持 UNKNOWN。\n" % (data["world"]["status"], len(data["scenes"])))
    write(content / "世界总览.md", md_frontmatter("世界总览", ["world-state", "creator-live"]) + "# 世界总览\n\n- 作品：莲蓬鬼话\n- 篇章：残荷诡影\n- 世界状态：%s\n- 真源运行目录：`%s`\n- 生产集成：否\n\n## 最新快照（原文派生）\n\n%s\n" % (data["world"]["status"], data["source_run"], data["world"]["latest_snapshot"]["raw"]))
    lines = [md_frontmatter("人物索引", ["characters", "creator-live"]), "# 人物索引", ""]
    for c in data["characters"]:
        lines.append(f"- [[人物/{c['id']}|{c['name']}]]：出场 {len(c['appearances'])} 场；家族关系：{c['family_relations']}")
        # Stable ID filenames avoid Windows-invalid characters and keep links
        # stable when a display name is later corrected.
        write(content / "人物" / f"{c['id']}.md", md_frontmatter(c["name"], ["character", "creator-live"]) + f"# {c['name']}\n\n- 稳定ID：`{c['id']}`\n- 状态：{c['status']}\n- 出场场次：{', '.join(c['appearances']) or 'UNKNOWN'}\n- 家族关系：UNKNOWN，除非关系与家族页有明确证据。\n")
    write(content / "人物索引.md", "\n".join(lines) + "\n")
    rel_lines = [md_frontmatter("关系与家族", ["relationships", "family"]), "# 关系与家族", "\n以下只列正文明确出现的关系表述，不把表述自动解释成完整家谱。\n"]
    for r in data["relationships"]:
        rel_lines.append(f"- {', '.join(r['participants'])}：{r['statement']}（[[事件索引#{r['source']['scene']}|第{r['source']['scene']}场]]）")
    rel_lines.append("\n## 家族关系\n")
    for r in data["family_relations"]:
        rel_lines.append(f"- {', '.join(r['participants'])}：{r['statement']}；状态：{r['status']}。")
    rel_lines.append("\n未明确的亲属边：UNKNOWN。")
    write(content / "关系与家族.md", "\n".join(rel_lines) + "\n")
    event_lines = [md_frontmatter("事件索引", ["events", "timeline"]), "# 事件索引", ""]
    for e in data["events"]:
        event_lines.append(f"- 第{e['scene_id'][1:]}场：{e['world_change']}；未决：{e['left_open']}")
    write(content / "事件索引.md", "\n".join(event_lines) + "\n")
    pp_lines = [md_frontmatter("地点与道具", ["places", "props"]), "# 地点与道具", "\n## 地点\n"]
    pp_lines.extend(f"- {p['name']}（来源 {len(p['sources'])} 场）" for p in data["places"])
    pp_lines.append("\n## 道具\n")
    pp_lines.extend(f"- {p['name']}（状态：{p['status']}）" for p in data["props"])
    write(content / "地点与道具.md", "\n".join(pp_lines) + "\n")
    receipt = {"schema": "video_kingdom.creator_encyclopedia_build_receipt.v1", "status": "COMPLETED", "source_run": data["source_run"], "counts": {k: len(data[k]) for k in ("scenes", "characters", "places", "family_relations", "relationships", "props", "events", "snapshots")}, "unknown_policy": data["unknown_policy"], "production_integration": False, "quartz_compatible": True, "output": str(out_dir.relative_to(ROOT)).replace("\\", "/")}
    dump(out_dir / "creator_encyclopedia_build_receipt.v1.json", receipt)
    write(out_dir / "README.md", "# 创者百科导出\n\n这是 Quartz 兼容的 Markdown/JSON 只读导出。原始推演真源不在此目录；任何未在正文明确的关系、家族和动机保持 UNKNOWN。\n\n当前仅本地构建，未部署到域名。\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    data = parse_run(run_dir)
    render(data, out_dir)
    print(json.dumps({"status": "COMPLETED", "out_dir": str(out_dir), "scenes": len(data["scenes"]), "characters": len(data["characters"]), "events": len(data["events"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
