import json
import time
import urllib.error
import urllib.request

API = "https://www.yoto.work"
AGENT = "7903b266adc54c64a2074d8a116237374e28e961c1d7415d8f0d5437dad36805"


def http(url, method="GET", body=None, headers=None, timeout=60):
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw[:800]}
        return e.code, payload


def main() -> None:
    _, login = http(f"{API}/api/auth/login", "POST", {"account": "HangZhouYiTuo", "password": "HangZhouYiTuo"})
    jwt = ((login.get("data") or {}).get("token"))
    auth = {"Authorization": f"Bearer {jwt}"}
    agent = {"X-Agent-Token": AGENT}

    code, amz = http(f"{API}/api/agent/amazon/sync?tenant_id=5", "POST", {"scope": "account_health"}, agent)
    print("amazon_sync", code, json.dumps(amz, ensure_ascii=False)[:800])

    for i in range(10):
        time.sleep(6)
        _, st = http(f"{API}/api/platform/sync-status", headers=auth)
        data = st.get("data") or st
        platforms = data.get("platforms") or {}
        temu = (platforms.get("temu") or {}).get("last_job") or {}
        amazon = platforms.get("amazon") or {}
        aj = amazon.get("last_job") or {}
        ae = (platforms.get("aliexpress") or {}).get("last_job") or {}
        print(
            f"[{i}] temu={temu.get('status')}/{temu.get('created_at')}/{temu.get('error_code')} "
            f"amz={aj.get('status')}/{aj.get('created_at') or aj.get('job_id')}/{amazon.get('error_code')} "
            f"ae={ae.get('status')}/{ae.get('error_code')}"
        )
        try:
            with urllib.request.urlopen("http://127.0.0.1:18766/api/status", timeout=5) as r:
                hs = json.loads(r.read().decode())
            print(
                "  helper",
                hs.get("agent_status"),
                "task",
                hs.get("last_task"),
                "err",
                (hs.get("last_error") or "")[:160],
            )
        except Exception as ex:  # noqa: BLE001
            print("  helper err", ex)


if __name__ == "__main__":
    main()
