import json

with open(r"D:\视频创作\ace-video-kingdom\sites\tinghe-archive\originals_source\fanguan\work.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for ep in data["episodes"]:
    total = 0
    for b in ep["blocks"]:
        if b["k"] == "scene":
            total += len(b.get("place", "")) + len(b.get("time", "")) + len(b.get("light", ""))
        elif b["k"] == "cast":
            total += len("".join(b.get("present", []))) + len("".join(b.get("absent", [])))
        elif b["k"] in ("para", "hook"):
            total += len(b.get("t", ""))
        elif b["k"] == "line":
            total += len(b.get("t", ""))
            if "stage" in b:
                total += len(b["stage"])
    print(f"{ep['id']}: {total} chars")
