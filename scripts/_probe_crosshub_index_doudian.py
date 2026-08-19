from pathlib import Path
import urllib.request

url = "https://www.yoto.work/crosshub/assets/index-BixQJRw0.js"
body = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "ignore")
Path(r"D:\YOTO-SASS\SaaS-HZ_WEB_Demo\scripts\_crosshub_index.js").write_text(body, encoding="utf-8")

needles = [
    "没有读取到抖店",
    "没有读取到",
    "抖店助手",
    "抖店 Agent",
    "doudian",
    "douyin",
    "platformOptions",
    "selectedPlatform",
    "product_issue",
    "shop_list",
    "自动上货",
    "Agent 的",
    "拼多多",
    "1688",
    "temu",
    "ozon",
]
for n in needles:
    print(n, body.count(n))

# print contexts around 抖店
idx = 0
count = 0
while count < 15:
    i = body.find("抖店", idx)
    if i < 0:
        break
    print("---", count, "---")
    print(body[max(0, i - 100) : i + 120].replace("\n", " "))
    idx = i + 2
    count += 1

# contexts around 没有读取
idx = 0
count = 0
while count < 10:
    i = body.find("没有读取", idx)
    if i < 0:
        break
    print("READ", count, body[max(0, i - 80) : i + 140].replace("\n", " "))
    idx = i + 2
    count += 1
