"""Monitor CrossHub 09:30 daily sync (Helper + online Java)."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

API = "https://www.yoto.work"
ACCOUNT = "HangZhouYiTuo"
PASSWORD = "HangZhouYiTuo"
AGENT_TOKEN = "7903b266adc54c64a2074d8a116237374e28e961c1d7415d8f0d5437dad36805"
HELPER_HEALTH = "http://127.0.0.1:18765/health"
HELPER_STATUS = "http://127.0.0.1:18766/api/status"
HELPER_LOG = Path(r"D:\NIUBI\SaaS-HZ_WEB_Demo\backend\python\exports\agent-logs\helper-runtime.log")
POLL_SEC = 30
# Run until 10:15 local unless --once
STOP_HOUR, STOP_MIN = 10, 15


def now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def http_json(url: str, method: str = "GET", body: dict | None = None, headers: dict | None = None, timeout: int = 25):
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {"raw": raw[:300]}
        return exc.code, payload
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}


def login() -> str:
    code, data = http_json(f"{API}/api/auth/login", "POST", {"account": ACCOUNT, "password": PASSWORD})
    if code != 200:
        raise RuntimeError(f"login failed {code}: {data}")
    token = ((data.get("data") or {}).get("token")) or data.get("token")
    if not token:
        raise RuntimeError(f"login no token: {data}")
    return token


def helper_snapshot() -> dict:
    h_code, health = http_json(HELPER_HEALTH, timeout=5)
    s_code, status = http_json(HELPER_STATUS, timeout=5)
    log_tail = []
    if HELPER_LOG.is_file():
        try:
            lines = HELPER_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
            log_tail = lines[-8:]
        except Exception as exc:  # noqa: BLE001
            log_tail = [f"log read error: {exc}"]
    return {
        "health_code": h_code,
        "health": health if isinstance(health, dict) else {"value": health},
        "status_code": s_code,
        "status": status if isinstance(status, dict) else {"value": status},
        "log_tail": log_tail,
    }


def online_snapshot(jwt: str) -> dict:
    headers = {"Authorization": f"Bearer {jwt}"}
    agent_headers = {"X-Agent-Token": AGENT_TOKEN}
    st_code, sync_status = http_json(f"{API}/api/platform/sync-status", headers=headers)
    jobs_code, jobs = http_json(f"{API}/api/agent/amazon/sync-jobs?tenant_id=5", headers=agent_headers)
    return {
        "sync_status_code": st_code,
        "sync_status": sync_status,
        "amazon_jobs_code": jobs_code,
        "amazon_jobs": jobs,
    }


def platform_job_bit(name: str, payload: dict) -> str:
    job = payload.get("last_job") or {}
    status = job.get("status") or payload.get("error_code") or "?"
    created = job.get("created_at") or ""
    err = job.get("error_code") or payload.get("error_code") or ""
    trigger = job.get("trigger") or ""
    return f"{name}={status}/{created}/{err}/{trigger}"


def summarize(online: dict, helper: dict) -> str:
    st = ((online.get("sync_status") or {}).get("data") or online.get("sync_status") or {})
    platforms = st.get("platforms") or {}
    plat_bits = []
    if isinstance(platforms, dict):
        for k, v in platforms.items():
            if isinstance(v, dict):
                plat_bits.append(platform_job_bit(k, v))
            else:
                plat_bits.append(f"{k}={v}")
    plat_txt = ", ".join(plat_bits) or "no-platforms"

    jobs_data = ((online.get("amazon_jobs") or {}).get("data") or online.get("amazon_jobs") or {})
    items = jobs_data.get("items") or []
    latest = items[0] if items else {}
    amz = (
        f"amz_latest={latest.get('status')}/{latest.get('scope')}/{latest.get('created_at')}"
        if latest
        else "amz_latest=none"
    )

    hs = helper.get("status") or {}
    agent_online = st.get("agent_online")
    ziniao = st.get("ziniao_online")
    hb = st.get("last_heartbeat_at")
    return (
        f"helper={hs.get('agent_status')} online={agent_online} ziniao={ziniao} hb={hb} "
        f"task={hs.get('last_task') or '-'} err={hs.get('last_error') or '-'} | "
        f"{plat_txt} | {amz}"
    )


def interesting_log_lines(lines: list[str]) -> list[str]:
    keys = ("日批", "daily", "enqueue", "轮询", "任务", "amazon", "temu", "aliexpress", "失败", "成功", "heartbeat", "心跳")
    out = []
    for line in lines:
        low = line.lower()
        if any(k.lower() in low for k in keys) or "[Agent]" in line or "[Panel]" in line:
            out.append(line)
    return out[-6:]


def once(jwt: str) -> tuple[str, dict, dict]:
    online = online_snapshot(jwt)
    helper = helper_snapshot()
    summary = summarize(online, helper)
    print(f"[{now()}] {summary}", flush=True)
    for line in interesting_log_lines(helper.get("log_tail") or []):
        print(f"    LOG {line}", flush=True)
    # compact dump of sync-status schedule/action if present
    st = ((online.get("sync_status") or {}).get("data") or {})
    if isinstance(st, dict):
        schedule = st.get("schedule") or {}
        if schedule:
            print(f"    schedule={json.dumps(schedule, ensure_ascii=False)}", flush=True)
        if "last_run" in st or "last_daily" in st:
            print(f"    last_run={st.get('last_run') or st.get('last_daily')}", flush=True)
    return summary, online, helper


def main() -> int:
    once_mode = "--once" in sys.argv
    print(f"==> monitor 09:30 daily sync start at {now()} api={API}", flush=True)
    jwt = login()
    print(f"==> logged in as {ACCOUNT}", flush=True)
    once(jwt)
    if once_mode:
        return 0

    while True:
        t = datetime.now()
        if (t.hour > STOP_HOUR) or (t.hour == STOP_HOUR and t.minute >= STOP_MIN):
            print(f"==> stop window reached {now()}", flush=True)
            once(jwt)
            return 0
        time.sleep(POLL_SEC)
        try:
            once(jwt)
        except Exception as exc:  # noqa: BLE001
            print(f"[{now()}] monitor error: {exc}", flush=True)
            try:
                jwt = login()
            except Exception as login_exc:  # noqa: BLE001
                print(f"[{now()}] re-login failed: {login_exc}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
