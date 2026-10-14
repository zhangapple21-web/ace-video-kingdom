"""Compare the deployed covers against the local ones, byte for byte.

The CDN serves static assets with Cache-Control: s-maxage=604800 — seven days.
app.css and app.js carry a ?v= query so a version bump busts them. The covers
under assets/entry/ do not, and that is a real operational gap rather than a
hypothetical one: the deleted cover.svg is still being served from the edge with
age ≈ 23.7 hours, well past the deploy that removed it.

Right now this passes because the covers are new and were never cached before.
It would not pass after a cover is regenerated, and the symptom would be "I
changed the picture and the site still shows the old one" for up to a week.

So this check reports the age alongside the hash: equal bytes now, and the age
tells you how long a future change would be invisible.
"""
import hashlib
import pathlib
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
LOCAL = HERE / "public" / "assets" / "entry"
NAMES = ("read", "catalog", "characters", "places", "events", "props")

print(f"{'cover':<12}{'local B':>9}{'live B':>9}{'bytes':>8}{'age(h)':>9}  hash")
print("-" * 62)

all_match = True
for name in NAMES:
    lb = (LOCAL / f"{name}.jpg").read_bytes()
    req = urllib.request.Request(
        f"https://studio.zhangningjing.com/dramai/assets/entry/{name}.jpg",
        headers={"User-Agent": "Mozilla/5.0 (cover audit)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        rb = r.read()
        age = int(r.headers.get("age") or 0)
    same = hashlib.sha256(lb).hexdigest() == hashlib.sha256(rb).hexdigest()
    all_match = all_match and same
    print(f"{name:<12}{len(lb):>9}{len(rb):>9}{('same' if same else 'DIFF'):>8}"
          f"{age/3600:>9.1f}  {hashlib.sha256(rb).hexdigest()[:12]}")

print()
print("线上与本地一致:", all_match)
print()
print("注意：封面 URL 不带版本号，CDN 缓存 7 天（s-maxage=604800）。")
print("     这次一致是因为封面是新的、从没被缓存过。")
print("     将来若重新生成某张封面，旧图可能最长在线一周 —— 见 IMAGE_ROUTES.md。")
raise SystemExit(0 if all_match else 1)