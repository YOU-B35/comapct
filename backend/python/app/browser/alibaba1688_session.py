"""1688 session cookie snapshot helpers."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Page

from app.browser.alibaba1688_context import profile_dir

SESSION_CACHE = ".crosshub-1688-session.json"
COOKIE_SNAPSHOT = ".crosshub-1688-cookies.json"
# Common Alibaba/1688 session cookie names (any subset is a signal).
SESSION_COOKIE_NAMES = frozenset(
    {
        "cookie2",
        "_m_h5_tk",
        "_m_h5_tk_enc",
        "lid",
        "ali_apache_id",
        "x5sectag",
        "cna",
        "t",
        "isg",
        "tfstk",
    }
)


def is_login_page(url: str) -> bool:
    lowered = (url or "").lower()
    return (
        "login.1688.com" in lowered
        or "passport.alibaba.com" in lowered
        or "passport.taobao.com" in lowered
        or "signin.htm" in lowered
        or "/member/signin" in lowered
        or "/login" in lowered
    )


def _cookie_snapshot_path(tenant_id: int) -> Path:
    return profile_dir(tenant_id) / COOKIE_SNAPSHOT


def _session_cache_path(tenant_id: int) -> Path:
    return profile_dir(tenant_id) / SESSION_CACHE


def filter_1688_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cookie in cookies:
        domain = str(cookie.get("domain") or "").lower()
        if "1688.com" not in domain and "alibaba.com" not in domain and "taobao.com" not in domain:
            continue
        rows.append(
            {
                "name": cookie.get("name") or "",
                "value": cookie.get("value") or "",
                "domain": cookie.get("domain") or "",
                "path": cookie.get("path") or "/",
                "expires": cookie.get("expires"),
                "httpOnly": bool(cookie.get("httpOnly")),
                "secure": bool(cookie.get("secure")),
                "sameSite": cookie.get("sameSite"),
            }
        )
    return rows


def session_ready(url: str, cookies: list[dict[str, Any]]) -> bool:
    if is_login_page(url or ""):
        return False
    names = {str(c.get("name") or "") for c in filter_1688_cookies(cookies)}
    if not (names & SESSION_COOKIE_NAMES):
        return False
    lowered = (url or "").lower()
    return "1688.com" in lowered or "alibaba.com" in lowered


def persist_1688_session(tenant_id: int, page: Page, context: BrowserContext) -> dict[str, Any]:
    url = ""
    try:
        url = page.url or ""
    except Exception:
        url = ""
    try:
        cookies = context.cookies()
    except Exception:
        cookies = []
    filtered = filter_1688_cookies(cookies)
    logged_in = session_ready(url, cookies)
    payload = {
        "tenant_id": tenant_id,
        "logged_in": logged_in,
        "url": url,
        "cookie_count": len(filtered),
        "cookie_names": sorted({str(c.get("name") or "") for c in filtered if c.get("name")}),
        "saved_at": int(time.time()),
    }
    _session_cache_path(tenant_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _cookie_snapshot_path(tenant_id).write_text(
        json.dumps({"tenant_id": tenant_id, "cookies": filtered, "saved_at": payload["saved_at"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload
