import re
import urllib.request
from pathlib import Path

base = "https://www.yoto.work/crosshub/assets/"
name = "AutoUploadView-D1uN9Wa7.js"
body = urllib.request.urlopen(base + name, timeout=60).read().decode("utf-8", "ignore")
out = Path(r"D:\YOTO-SASS\SaaS-HZ_WEB_Demo\scripts\_AutoUploadView_prod.js")
out.write_text(body, encoding="utf-8")
print("size", len(body))

needles = [
    "没有读取到抖店",
    "没有读取到",
    "抖店助手",
    "抖店 Agent",
    "抖店",
    "doudian",
    "douyin",
    "platformOptions",
    "selectedPlatform",
    "product_issue",
    "shop_list",
    "temu",
    "aliexpress",
    "ozon",
    "pdd",
    "1688",
    "拼多多",
    "Agent 的",
    "请下载运行",
]
for n in needles:
    print(f"{n!r}: {body.count(n)}")

# also pull related chunks referenced nearby if any import paths
imports = re.findall(r"\./[A-Za-z0-9_.-]+\.js", body)
print("imports", sorted(set(imports))[:40])

idx = 0
c = 0
while c < 20:
    i = body.find("抖店", idx)
    if i < 0:
        break
    print(f"\n=== 抖店 {c} ===")
    print(body[max(0, i - 120) : i + 160])
    idx = i + 2
    c += 1

idx = 0
c = 0
while c < 10:
    i = body.find("没有读取", idx)
    if i < 0:
        break
    print(f"\n=== 没有读取 {c} ===")
    print(body[max(0, i - 120) : i + 180])
    idx = i + 2
    c += 1
