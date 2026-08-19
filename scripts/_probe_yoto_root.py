import re
import urllib.request
from pathlib import Path

# Commander main site (not /crosshub)
urls = [
    "https://www.yoto.work/",
    "https://www.yoto.work/index.html",
    "https://www.yoto.work/auto-upload",
    "https://www.yoto.work/AutoUpload",
]
for u in urls:
    try:
        req = urllib.request.Request(u, method="GET")
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", "ignore")
            print("OK", u, "status", resp.status, "len", len(body), "title?", "title" in body.lower())
            print(body[:400].replace("\n", " "))
            js = sorted(set(re.findall(r"(?:src|href)=[\"']([^\"']+\\.js)[\"']", body)))
            print(" js", js[:20])
    except Exception as e:
        print("FAIL", u, type(e).__name__, e)
