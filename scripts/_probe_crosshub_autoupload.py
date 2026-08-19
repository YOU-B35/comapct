from pathlib import Path

body = Path(r"D:\YOTO-SASS\SaaS-HZ_WEB_Demo\scripts\_crosshub_index.js").read_text(encoding="utf-8")

for n in [
    "自动上货",
    "commander",
    "Commander",
    "/api/commander",
    "agent/list",
    "product_issue",
    "selectedPlatform",
    "platformOptions",
    "TEMU",
    "AliExpress",
    "Ozon",
    "抖店",
    "没有在线",
    "Agent",
]:
    print(f"{n!r}: {body.count(n)}")

idx = 0
c = 0
while c < 8:
    i = body.find("自动上货", idx)
    if i < 0:
        break
    print(f"\n=== auto-upload ctx {c} ===")
    print(body[max(0, i - 150) : i + 200])
    idx = i + 4
    c += 1
