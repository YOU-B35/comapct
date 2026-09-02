"""1688 buyer login / session probe for Sync Helper agent tasks."""
from __future__ import annotations

import os
import time
from typing import Any

from app.browser.alibaba1688_context import clear_stale_profile_locks, crawl_headless_enabled, profile_dir
from app.browser.alibaba1688_session import (
    is_login_page,
    persist_1688_session,
    session_ready,
)
from app.browser.resource_filter import install_heavy_resource_filter
from app.observability.task_timing import timed_stage

# 采购工作台；未登录时会落到登录页，登录后回到 work.1688.com
HOME_URL = "https://work.1688.com/"
LOGIN_URL = (
    "https://login.1688.com/member/signin.htm?"
    "Done=https%3A%2F%2Fwork.1688.com%2F"
)

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
    # work.1688.com 未登录也可能在同域展示登录框，需页面文案佐证已登录
    markers = ("退出", "我的阿里", "采购车", "采购工作台", "我的进货单", "进货单")
    return any(m in content for m in markers) and "密码登录" not in content and "扫码登录" not in content


def _run_in_clean_thread(fn, *, timeout: float | None = None):
    """Playwright Sync API cannot run when the current thread already has an asyncio loop
    (Helper tray/flask may install one). Always execute browser work on a fresh thread.
    """
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        return fut.result(timeout=timeout)


def _a1688_launch_kwargs(*, headless: bool, args: list[str] | None = None) -> dict[str, Any]:
    """统一使用 Playwright 内置 Chromium（不打开系统 Chrome/Edge，避免风控）。"""
    from app.browser.context import _bundled_chromium_ready

    kwargs: dict[str, Any] = {
        "headless": headless,
        "viewport": {"width": 1280, "height": 900},
        "locale": "zh-CN",
        "args": list(args or []),
    }
    if not _bundled_chromium_ready():
        raise RuntimeError(
            "A1688_BROWSER_UNAVAILABLE: 未检测到 Playwright 内置 Chromium。"
            "1688 登录/同步统一使用内置浏览器（不打开系统 Chrome/Edge），"
            "请先执行 python -m playwright install chromium 后重试"
        )
    return kwargs


def _launch(
    tenant_id: int,
    *,
    headless: bool = True,
    goto: str | None = HOME_URL,
    store_id: str | None = None,
):
    from playwright.sync_api import sync_playwright

    clear_stale_profile_locks(tenant_id, store_id)
    user_data = str(profile_dir(tenant_id, store_id))
    print(f"[1688] launch profile={user_data} headless={headless} goto={goto!r}", flush=True)
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if headless:
        args.append("--headless=new")
    else:
        args.append("--start-maximized")
    launch_kwargs = _a1688_launch_kwargs(headless=headless, args=args)
    pw = sync_playwright().start()
    with timed_stage("browser_launch.1688"):
        context = pw.chromium.launch_persistent_context(
            user_data,
            **launch_kwargs,
        )
    install_heavy_resource_filter(context, headless=headless)
    page = context.pages[0] if context.pages else context.new_page()
    if not headless:
        try:
            page.bring_to_front()
        except Exception:
            pass
    if goto:
        page.goto(goto, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(600)
    print(f"[1688] page url={getattr(page, 'url', '')!r}", flush=True)
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
    payload: dict[str, Any] = {
        "tenant_id": tenant_id,
        "ready": logged_in,
        "logged_in": logged_in,
        "requires_auth": not logged_in,
        "profile_busy": False,
        "message": message,
        "shop_count": 0,
        "shops": [],
    }
    return payload


def _extract_shop_identity(page) -> dict[str, Any]:
    """从卖家工作台页面尽力提取真实店铺名，用于默认会话归属解析。"""
    import re

    info: dict[str, Any] = {}
    try:
        text = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
        m = re.search(r"([^\n]{2,40})\n首页", text)
        if m:
            info["store_name"] = m.group(1).strip()
    except Exception:
        pass
    return info


def probe_session(tenant_id: int, store_id: str | None = None) -> dict[str, Any]:
    def _run() -> dict[str, Any]:
        pw = context = page = None
        try:
            pw, context, page = _launch(
                tenant_id,
                headless=crawl_headless_enabled(),
                goto=HOME_URL,
                store_id=store_id,
            )
            logged_in = _looks_logged_in(page, context)
            persist_1688_session(tenant_id, page, context, store_id)
            print(
                f"[1688Probe] tenant={tenant_id} logged_in={logged_in} url={getattr(page, 'url', '')!r}",
                flush=True,
            )
            payload = _session_payload(
                tenant_id,
                logged_in=logged_in,
                message="1688 已登录" if logged_in else "1688 未登录，请打开登录窗口完成登录",
            )
            if logged_in:
                identity = _extract_shop_identity(page)
                if identity.get("store_name"):
                    payload["shops"] = [{"store_name": identity["store_name"]}]
                    payload["shop_count"] = 1
            return payload
        finally:
            _close(pw, context)

    return _run_in_clean_thread(_run, timeout=180)


def open_login_window(
    tenant_id: int,
    timeout_seconds: int = 600,
    store_id: str | None = None,
) -> dict[str, Any]:
    def _run() -> dict[str, Any]:
        pw = context = page = None
        try:
            pw, context, page = _launch(
                tenant_id,
                headless=False,
                goto=LOGIN_URL,
                store_id=store_id,
            )
            deadline = time.monotonic() + max(30, int(timeout_seconds))
            logged_in = False
            while time.monotonic() < deadline:
                if _looks_logged_in(page, context):
                    try:
                        if is_login_page(page.url or ""):
                            page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60_000)
                            page.wait_for_timeout(800)
                    except Exception:
                        pass
                    persist_1688_session(tenant_id, page, context, store_id)
                    logged_in = True
                    break
                page.wait_for_timeout(800)
            if not logged_in:
                persist_1688_session(tenant_id, page, context)
            return _session_payload(
                tenant_id,
                logged_in=logged_in,
                message="1688 已登录" if logged_in else "登录超时，请重试打开登录窗口",
            )
        finally:
            _close(pw, context)

    return _run_in_clean_thread(_run, timeout=float(timeout_seconds) + 90)
