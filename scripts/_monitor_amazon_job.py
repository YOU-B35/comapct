"""Monitor an existing Amazon sync job by job_id."""
from __future__ import annotations

import json
import sys
import time

import requests

JAVA = "http://127.0.0.1:18080"
ACCOUNT = "HangZhouYiTuo"
PASSWORD = "HangZhouYiTuo"


def login() -> str:
    res = requests.post(
        f"{JAVA}/api/auth/login",
        json={"account": ACCOUNT, "password": PASSWORD, "portalRole": "boss"},
        timeout=15,
    )
    res.raise_for_status()
    body = res.json()
    data = body.get("data") or body
    token = data.get("token") or data.get("access_token")
    if not token:
        raise RuntimeError(f"login failed: {body}")
    return token


def main() -> None:
    job_id = sys.argv[1]
    max_polls = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    token = login()
    print("monitoring:", job_id)
    final = None
    for i in range(max_polls):
        time.sleep(3)
        job = requests.get(
            f"{JAVA}/api/amazon/sync/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        ).json()
        data = job.get("data") or job
        status = data.get("status")
        err = (data.get("error_message") or "")[:100]
        if i % 10 == 0 or status not in {"pending", "running"}:
            print(f"[{i + 1}] {status} started={data.get('started_at')} err={err}")
        if status in {"success", "failed", "error", "partial"}:
            final = data
            break
    if not final:
        print("TIMEOUT")
        sys.exit(2)
    print("FINAL:", json.dumps(final, ensure_ascii=False)[:1000])
    if final.get("status") != "success":
        sys.exit(3)
    insights = requests.get(
        f"{JAVA}/api/amazon/insights",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    ).json()
    products = (insights.get("data") or insights).get("products") or []
    acos_vals = sorted({round(float(p.get("acos") or 0), 2) for p in products if float(p.get("acos") or 0) > 0})
    print(f"products={len(products)} distinct_acos={len(acos_vals)} sample={acos_vals[:8]}")
    for row in products[:5]:
        print(row.get("asin"), "ad=", row.get("adSpend7d"), "acos=", row.get("acos"))


if __name__ == "__main__":
    main()
