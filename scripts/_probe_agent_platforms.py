from pathlib import Path
import re

data = Path(r"C:\Users\Administrator\Desktop\Agent_windows_amd64_3.4.5\Agent.exe").read_bytes()
text = data.decode("utf-8", errors="ignore")

needles = [
    "该平台暂未开通",
    "没有读取到",
    "抖店",
    "助手",
    "重新开启",
    "请下载",
    "PlatformDxm",
    "factory/doudian",
    "factory/douyin",
    "factory/pdd",
    "factory/temu",
    "factory/1688",
    "doudian",
    "tiktok",
    "jinritemai",
]
for n in needles:
    i = text.find(n)
    print(f"{'FOUND' if i>=0 else 'MISS ':5} {n!r} @ {i}")
    if i >= 0:
        print(" ", repr(text[max(0, i - 60) : i + len(n) + 80]))

print("\n=== factory package paths ===")
for m in re.finditer(r"factory/[a-z0-9_]+/[A-Za-z0-9_.]+", text):
    print(m.group(0))

print("\n=== unique factory dirs ===")
print(sorted(set(re.findall(r"factory/([a-z0-9_]+)/", text))))
