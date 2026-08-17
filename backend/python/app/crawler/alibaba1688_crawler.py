"""1688 purchase crawler (Day0-gated)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.browser.alibaba1688_context import profile_dir
from app.crawler.alibaba1688_constants import (
    LOGIN_OK_URL_SUBSTRINGS,
    PURCHASE_LIST_URL,
    STOCKOUT_KEYWORDS,
)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def login_probe(*, tenant_id: int, headed: bool = True) -> dict[str, Any]:
    """Open 1688 and report need_login vs success. Does not invent selectors."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        return {
            "status": "failed",
            "message": f"Playwright unavailable: {exc}",
            "rows": 0,
        }

    user_data = str(profile_dir(tenant_id))
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data,
            headless=not headed,
            viewport={"width": 1280, "height": 800},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.1688.com/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        url = page.url or ""
        content = ""
        try:
            content = page.content()
        except Exception:
            content = ""
        logged_in = any(s in url for s in LOGIN_OK_URL_SUBSTRINGS) and (
            "登录" not in content[:4000] or "退出" in content or "我的阿里" in content
        )
        # Prefer explicit login wall
        if "login.1688.com" in url or "passport" in url.lower():
            logged_in = False
        context.close()
        if not logged_in:
            return {"status": "need_login", "message": "1688 未登录，请在弹出的浏览器中完成登录后重试", "rows": 0}
        return {"status": "success", "message": "session ok", "rows": 0}


def crawl_purchase_orders(*, tenant_id: int, headed: bool = True) -> dict[str, Any]:
    """Live crawl blocked until Day0 fills PURCHASE_LIST_URL. Optional fixture via env."""
    import os

    if os.getenv("A1688_USE_FIXTURE") == "1":
        return {"status": "partial", "message": "fixture rows (Day0 URL empty)", "rows": _fixture_rows(tenant_id)}

    if not PURCHASE_LIST_URL or not STOCKOUT_KEYWORDS:
        return {
            "status": "partial",
            "message": "Day0 incomplete: PURCHASE_LIST_URL / STOCKOUT_KEYWORDS empty — live sync blocked",
            "rows": [],
        }

    # Live path placeholder — selectors must come from Day0 attachment
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        return {"status": "failed", "message": f"Playwright unavailable: {exc}", "rows": []}

    user_data = str(profile_dir(tenant_id))
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data,
            headless=not headed,
            viewport={"width": 1280, "height": 800},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(PURCHASE_LIST_URL, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(2000)
        url = page.url or ""
        if "login" in url.lower() or "passport" in url.lower():
            context.close()
            return {"status": "need_login", "message": "1688 未登录", "rows": []}
        # Without Day0 XHR mapping we cannot safely scrape — return partial empty
        context.close()
        return {
            "status": "partial",
            "message": "Day0 XHR mapping not implemented yet; opened list URL only",
            "rows": [],
        }


def _fixture_rows(tenant_id: int) -> list[dict[str, Any]]:
    eta_past = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    return [
        {
            "store_id": "",  # filled by ingest from platform_account
            "order_no": f"FIX{tenant_id}001",
            "status": "pending_shipment",
            "product_name": "1688 fixture SKU",
            "supplier_name": "Fixture Supplier",
            "quantity": 10,
            "unit_price": 12.5,
            "amount": 125.0,
            "currency": "CNY",
            "expected_arrival_at": eta_past,
            "logistics_status": "缺货待补",
            "is_stockout": 1,
            "synced_at": _now(),
        }
    ]
