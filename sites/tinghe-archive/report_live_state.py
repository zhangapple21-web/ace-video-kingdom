"""Report what production is actually serving, and whether a reader would see it.

The UI has been deployed for a while. If it still looks unchanged in a browser,
the likeliest cause is not the deploy — it is this project's own asset policy:
the CDN serves static files with a seven-day max-age, so anything already in a
visitor's cache keeps its old bytes until that expires. app.css and app.js carry
a ?v= query that changes on every restyle, which is exactly why those bust. The
six covers and og/hero images have no query, so those do not.

So this prints three things: what the origin is serving, what the CDN reports for
age, and what a reader has to do to actually see the new UI.
"""
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (live check)"}
BASE = "https://studio.zhangningjing.com/dramai"


def get(path):
    req = urllib.request.Request(BASE + path, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace"), dict(r.headers)


html, head = get("/")
css = re.findall(r"app\.css\?v=([0-9a-zA-Z\-]+)", html)
js = re.findall(r"app\.js\?v=([0-9a-zA-Z\-]+)", html)
colors = re.findall(r'theme-color" content="([^"]+)"', html)

print("=== 线上 index.html ===")
print("  app.css?v =", css)
print("  app.js?v  =", js)
print("  主题切换按钮 =", 'id="theme-open"' in html)
print("  theme-color  =", colors)
print("  CDN age     =", head.get("age", "0"), "秒")

if css:
    sheet, sheet_head = get(f"/assets/app.css?v={css[0]}")
    print()
    print(f"=== 线上 app.css（{len(sheet)} 字符，age {sheet_head.get('age','0')}s）===")
    checks = {
        "六张封面引用": all(f"entry/{n}.jpg" in sheet
                        for n in ("read", "catalog", "characters", "places", "events", "props")),
        "无衬线令牌": "--sans:" in sheet,
        "星空层": ".starfield" in sheet,
        "主题按钮样式": ".nav-theme" in sheet,
        "深色为默认面": "--paper: #080c11" in sheet,
        "圆角令牌": "--r-lg: 20px" in sheet,
        "花括号配平": sheet.count("{") == sheet.count("}"),
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'NO '}  {k}")

print()
print("=== 读者如果没看到变化 ===")
print("  本站 CSS/JS 都带 ?v= 版本串，改版时会变 —— 所以不是普通的浏览器缓存。")
print("  最可能的情况（按概率）：")
print("   1. 你在看的是别的页面（首页是 /dramai/，章节是 /dramai/read/cNNN 无扩展名）")
print("   2. 之前打开的标签页没刷新 —— 按 Ctrl+Shift+R 强制刷新")
print("   3. 移动端 App 内置浏览器缓存顽固，需要关掉页面重进")
print()
print("  注意：六张封面和 hero/og 图 **不带版本号**，CDN 缓存 7 天。")
print("       它们今天刚上线所以是新的；将来换图不会立刻生效。")