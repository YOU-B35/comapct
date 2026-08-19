import re
import urllib.request
from pathlib import Path

html = urllib.request.urlopen("https://www.yoto.work/crosshub/", timeout=30).read().decode("utf-8", "ignore")
Path(r"D:\YOTO-SASS\SaaS-HZ_WEB_Demo\scripts\_crosshub_index.html").write_text(html, encoding="utf-8")
js = sorted(set(re.findall(r"assets/[^\"']+\.js", html)))
print("count", len(js))
for j in js:
    print(j)

# download and search for doudian-related error
needle = "没有读取到抖店"
needle2 = "抖店助手"
needle3 = "doudian"
for j in js:
    url = "https://www.yoto.work/crosshub/" + j
    try:
        body = urllib.request.urlopen(url, timeout=60).read()
    except Exception as e:
        print("fail", j, e)
        continue
    text = body.decode("utf-8", "ignore")
    flags = []
    if needle in text:
        flags.append("ERR_MSG")
    if needle2 in text:
        flags.append("HELPER")
    if needle3 in text or "抖店" in text:
        flags.append("DOUDIAN")
    if "自动上货" in text or "AutoUpload" in text or "product_issue" in text:
        flags.append("UPLOAD")
    if "platformOptions" in text or "aliexpress" in text:
        flags.append("PLAT")
    if flags:
        print(j, flags, "size", len(body))
        if "ERR_MSG" in flags or "HELPER" in flags:
            i = text.find(needle) if needle in text else text.find(needle2)
            print(" context:", text[max(0, i - 80) : i + 120])
