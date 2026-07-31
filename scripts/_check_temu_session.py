import json
import urllib.request

# Get a boss JWT for tenant5 first
login_req = urllib.request.Request(
    "http://localhost:18080/api/auth/login",
    data=json.dumps({"username": "HangZhouYiTuo", "password": "HangZhouYiTuo"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(login_req, timeout=15) as resp:
    body = json.loads(resp.read().decode())
token = body.get("accessToken") or body.get("token") or (body.get("data") or {}).get("accessToken")
print("login_keys=", list(body.keys()) if isinstance(body, dict) else type(body))
if isinstance(body, dict) and "data" in body:
    print("data_keys=", list(body["data"].keys()) if isinstance(body["data"], dict) else body["data"])
    token = token or body["data"].get("accessToken") or body["data"].get("token")
print("token_prefix=", (token or "")[:20])

req = urllib.request.Request(
    "http://localhost:18080/api/temu/session",
    headers={"Authorization": f"Bearer {token}"},
)
with urllib.request.urlopen(req, timeout=20) as resp:
    print(resp.read().decode()[:2000])
