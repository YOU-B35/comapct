"""1688 buyer login / session probe for Sync Helper agent tasks."""
from __future__ import annotations

import time
from typing import Any

from app.browser.alibaba1688_context import profile_dir
from app.browser.alibaba1688_session import (
    is_login_page,
    persist_1688_session,
    session_ready,
)

LOGIN_URL = "https://login.1688.com/member/signin.htm?Done=https%3A%2F%2Fwww.1688.com%2F"
HOME_URL = "https://www.1688.com/"


def _looks_logged_in(page, context) -> bool:
    try:
        url = page.url or ""
    except Exception:
        url = ""
    try:
        cookies = context.cookies()
    except Exception:
        cookies = []
    if session_ready(url, cookies):
        return True
    if is_login_page(url):
        return False
    try:
        content = page.content()[:5000]
    except Exception:
        content = ""
    return "退出" in content or "我的阿里" in content or "采购车" in content


def _launch(tenant_id: int, *, headless: bool = False, goto: str | None = HOME_URL):
    from playwright.sync_api import sync_playwright

    user_data = str(profile_dir(tenant_id))
    pw = sync_playwright().start()
    context = pw.chromium.launch_persistent_context(
        user_data,
        headless=headless,
        viewport={"width": 1280, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = context.pages[0] if context.pages else context.new_page()
    if goto:
        page.goto(goto, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(1500)
    return pw, context, page


def _close(pw, context) -> None:
    try:
        if context is not None:
            context.close()
    except Exception:
        pass
    try:
        if pw is not None:
            pw.stop()
    except Exception:
        pass


def _session_payload(tenant_id: int, *, logged_in: bool, message: str) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "ready": logged_in,
        "logged_in": logged_in,
        "requires_auth": not logged_in,
        "profile_busy": False,
        "message": message,
        "shop_count": 0,
        "shops": [],
    }


def probe_session(tenant_id: int) -> dict[str, Any]:
    pw = context = page = None
    try:
        pw, context, page = _launch(tenant_id, headless=False, goto=HOME_URL)
        logged_in = _looks_logged_in(page, context)
        persist_1688_session(tenant_id, page, context)
        print(
            f"[1688Probe] tenant={tenant_id} logged_in={logged_in} url={getattr(page, 'url', '')!r}",
            flush=True,
        )
        return _session_payload(
            tenant_id,
            logged_in=logged_in,
            message="1688 已登录" if logged_in else "1688 未登录，请打开登录窗口完成登录",
        )
    finally:
        _close(pw, context)


def open_login_window(tenant_id: int, timeout_seconds: int = 600) -> dict[str, Any]:
    pw = context = page = None
    try:
        pw, context, page = _launch(tenant_id, headless=False, goto=LOGIN_URL)
        print(f"[1688Login] opened login for tenant={tenant_id}", flush=True)
        deadline = time.monotonic() + max(30, int(timeout_seconds))
        logged_in = False
        while time.monotonic() < deadline:
            if _looks_logged_in(page, context):
                try:
                    if is_login_page(page.url or ""):
                        page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60_000)
                        page.wait_for_timeout(2000)
                except Exception:
                    pass
                persist_1688_session(tenant_id, page, context)
                logged_in = True
                break
            page.wait_for_timeout(2000)
        if not logged_in:
            persist_1688_session(tenant_id, page, context)
        return _session_payload(
            tenant_id,
            logged_in=logged_in,
            message="1688 已登录" if logged_in else "登录超时，请重试打开登录窗口",
        )
    finally:
        _close(pw, context)
