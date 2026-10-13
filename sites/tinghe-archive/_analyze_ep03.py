import json

with open(r"D:\视频创作\ace-video-kingdom\sites\tinghe-archive\originals_source\fanguan\work.json", "r", encoding="utf-8") as f:
    data = json.load(f)

ep03 = [ep for ep in data["episodes"] if ep["id"] == "ep03"][0]

total = 0
details = []
for b in ep03["blocks"]:
    if b["k"] == "scene":
        c = len(b.get("place", "")) + len(b.get("time", "")) + len(b.get("light", ""))
        details.append(f"scene: {c}")
        total += c
    elif b["k"] == "cast":
        c = len("".join(b.get("present", []))) + len("".join(b.get("absent", [])))
        details.append(f"cast: {c}")
        total += c
    elif b["k"] in ("para", "hook"):
        c = len(b.get("t", ""))
        details.append(f"{b['k']}: {c}")
        total += c
    elif b["k"] == "line":
        c = len(b.get("t", ""))
        if "stage" in b:
            c += len(b["stage"])
        details.append(f"line({b.get('who','')}): {c}")
        total += c

for d in details:
    print(d)
print(f"\nTotal: {total}")
print(f"Blocks: {len(ep03['blocks'])}")
