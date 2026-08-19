from pathlib import Path
import re

data = Path(r"C:\Users\Administrator\Desktop\Agent_windows_amd64_3.4.5\Agent.exe").read_bytes()
text = data.decode("utf-8", errors="ignore")

# CJK phrases
cjk = re.findall(r"[\u4e00-\u9fffA-Za-z0-9【】\[\]（）()·\s]{6,80}", text)
keys = ("Agent", "助手", "读取", "抖店", "拼多", "上货", "店铺", "平台", "下载", "开启", "没有")
hits = sorted({s.strip() for s in cjk if any(k in s for k in keys)})
print("=== CJK/agent phrases ===")
for s in hits[:120]:
    print(s)

print("\n=== Go source paths mentioning platforms ===")
for m in re.finditer(r"[\w./\\-]{5,120}\.(?:go|vue|ts|js)", text):
    s = m.group(0)
    low = s.lower()
    if any(k in low for k in ("doudian", "douyin", "pdd", "1688", "temu", "ozon", "aliexpress", "agent", "product", "shop")):
        print(s)

print("\n=== Resty*/Factory symbols ===")
for m in re.finditer(r"Resty\w+|[\w]*Factory|Platform\w+|platform\w+", text):
    s = m.group(0)
    if len(s) > 5 and any(k in s.lower() for k in ("temu", "ozon", "ali", "1688", "pdd", "dou", "platform", "resty")):
        print(s)
