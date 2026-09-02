"""紫鸟 CDP 会话上下文（登录检测、截图、merchantId）。"""
from __future__ import annotations

import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.amazon.page_urls import HOME_URL
from app.config import (
    AMAZON_LOGIN_MAX_ATTEMPTS,
    AMAZON_LOGIN_POLL_SECONDS,
    AMAZON_LOGIN_WAIT_SECONDS,
)

CAPTURE_DIR = Path(__file__).resolve().parents[3] / "data" / "amazon-captures"


class AmazonLoginRequiredError(RuntimeError):
    def __init__(self, message: str, *, capture_path: str = "") -> None:
        super().__init__(message)
        self.capture_path = capture_path


def extract_debug_port(start_result: dict[str, Any]) -> int:
    for key in ("debuggingPort", "debugPort", "debugging_port", "cdpPort", "port"):
        value = start_result.get(key)
        if value is not None and str(value).strip().isdigit():
            return int(str(value).strip())
    browser = start_result.get("browser")
    if isinstance(browser, dict):
        for key in ("debuggingPort", "debugPort", "debugging_port", "cdpPort", "port"):
            value = browser.get(key)
            if value is not None and str(value).strip().isdigit():
                return int(str(value).strip())
    raise RuntimeError(f"startBrowser 未返回 debuggingPort: {start_result!r}")


def save_capture(page, *, store_name: str, suffix: str) -> str:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\-]+", "_", store_name or "amazon")[:40]
    path = CAPTURE_DIR / f"{safe_name}_{suffix}_{int(time.time())}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def looks_logged_in(body_text: str, url: str) -> bool:
    body = body_text or ""
    lowered = body.lower()
    if "/home" in (url or "") and ("全局快照" in body or "global snapshot" in lowered):
        return True
    if "账户状况" in body or "account health" in lowered:
        return True
    if "seller central" in lowered or "卖家平台" in body:
        return "sign in" not in lowered and "sign-in" not in lowered
    return False


def looks_login_page(body_text: str, url: str) -> bool:
    body = body_text or ""
    lowered = body.lower()
    url_l = (url or "").lower()
    if "两步验证" in body or "one-time password" in lowered or "/ap/mfa" in url_l:
        return True
    if "sign in" in lowered or "sign-in" in lowered:
        return "seller central" not in lowered and "卖家平台" not in body
    if "登录" in body and "账户状况" not in body and "全局快照" not in body:
        return True
    if "/ap/signin" in url_l:
        return True
    return False


def _session_ready(body_text: str, url: str) -> bool:
    return looks_logged_in(body_text, url) and not looks_login_page(body_text, url)


def _read_body_text(page) -> str:
    try:
        text = page.evaluate(
            """() => (document.body && (document.body.innerText || document.body.textContent)) || ''"""
        )
        if text:
            return str(text)
    except Exception:
        pass
    try:
        return str(page.inner_text("body") or "")
    except Exception:
        return ""


def wait_for_seller_page_state(
    page,
    *,
    timeout_seconds: float = 5.0,
    poll_seconds: float = 0.25,
    sleeper: Callable[[float], None] = time.sleep,
) -> str:
    """Wait only until Amazon has a recognizable seller or login page state.

    This replaces unconditional post-navigation sleeps while preserving their
    former upper bound for slow client-side rendering.
    """
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    latest = ""
    while True:
        latest = _read_body_text(page)
        url = getattr(page, "url", "") or ""
        if _session_ready(latest, url) or looks_login_page(latest, url):
            return latest
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return latest
        delay = min(max(0.05, poll_seconds), remaining)
        try:
            page.wait_for_timeout(max(1, int(delay * 1000)))
        except Exception:
            sleeper(delay)


def require_seller_logged_in(page, body_text: str, *, store_name: str = "") -> None:
    if looks_login_page(body_text, page.url):
        capture = save_capture(page, store_name=store_name, suffix="login")
        raise AmazonLoginRequiredError(
            f"Amazon 卖家后台未登录，截图: {capture}",
            capture_path=capture,
        )
    if not looks_logged_in(body_text, page.url):
        capture = save_capture(page, store_name=store_name, suffix="login")
        raise AmazonLoginRequiredError(
            f"Amazon 卖家后台会话无效，请在紫鸟中重新登录 Seller Central。截图: {capture}",
            capture_path=capture,
        )


def ensure_seller_logged_in_with_wait(
    page,
    *,
    body_text: str | None = None,
    store_name: str = "",
    timeout_seconds: int | None = None,
    poll_seconds: float | None = None,
    max_attempts: int | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    home_url: str = HOME_URL,
) -> str:
    """登录/2FA 未完成时等待人工（或插件）完成，最多刷新检测 max_attempts 次。

    与 Temu wait_for_login_and_mall 同类：日批不因一次 2FA 页面立刻失败。
    """
    wait_total = AMAZON_LOGIN_WAIT_SECONDS if timeout_seconds is None else int(timeout_seconds)
    poll = AMAZON_LOGIN_POLL_SECONDS if poll_seconds is None else float(poll_seconds)
    attempts = AMAZON_LOGIN_MAX_ATTEMPTS if max_attempts is None else int(max_attempts)
    attempts = max(1, attempts)
    poll = max(0.5, poll)

    current = body_text if body_text is not None else _read_body_text(page)
    if _session_ready(current, getattr(page, "url", "") or ""):
        return current

    polls_between = max(1, int(max(wait_total, 1) / (attempts * poll)))
    print(
        f"Amazon 卖家后台需要登录或完成两步验证。请在紫鸟窗口完成操作；"
        f"将等待最多 {wait_total}s，刷新检测 {attempts} 次。",
        flush=True,
    )

    for attempt in range(1, attempts + 1):
        print(f"Amazon 登录检测第 {attempt}/{attempts} 次…", flush=True)
        try:
            page.goto(home_url, wait_until="domcontentloaded")
        except Exception as exc:
            print(f"Amazon 打开首页失败（第 {attempt} 次）: {exc}", flush=True)
        current = wait_for_seller_page_state(
            page,
            timeout_seconds=3,
            sleeper=sleeper,
        )
        if _session_ready(current, getattr(page, "url", "") or ""):
            print("Amazon 卖家后台登录已就绪，继续同步。", flush=True)
            return current

        if attempt >= attempts:
            break

        for _ in range(polls_between):
            sleeper(poll)
            current = _read_body_text(page)
            if _session_ready(current, getattr(page, "url", "") or ""):
                print("Amazon 卖家后台登录已就绪，继续同步。", flush=True)
                return current

    capture = save_capture(page, store_name=store_name, suffix="login")
    raise AmazonLoginRequiredError(
        f"Amazon 卖家后台未登录或两步验证未完成（已重试 {attempts} 次），截图: {capture}",
        capture_path=capture,
    )


def goto(page, url: str, wait_ms: int = 10000) -> str:
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(wait_ms)
    return page.inner_text("body")


def resolve_merchant_id(page) -> str:
    try:
        merchant_id = page.evaluate(
            """
            () => {
              const fromUrl = new URL(location.href).searchParams.get('merchantId')
                || new URL(location.href).searchParams.get('merchantid');
              if (fromUrl) return fromUrl;
              const html = document.documentElement.innerHTML || '';
              const patterns = [
                /merchantId["':=\\s]+(A[A-Z0-9]{9,14})/i,
                /"merchantId":"(A[A-Z0-9]{9,14})"/i,
                /merchant_id["':=\\s]+(A[A-Z0-9]{9,14})/i,
              ];
              for (const pattern of patterns) {
                const match = html.match(pattern);
                if (match) return match[1];
              }
              return '';
            }
            """
        )
        return str(merchant_id or "").strip()
    except Exception:
        return ""


class SessionContext:
    def __init__(self, page, *, store_name: str = "", merchant_id: str = "") -> None:
        self.page = page
        self.store_name = store_name
        self.merchant_id = merchant_id

    def screenshot(self, suffix: str) -> str:
        return save_capture(self.page, store_name=self.store_name, suffix=suffix)

    def body_text(self) -> str:
        return self.page.inner_text("body")

    def ensure_merchant_id(self) -> str:
        if self.merchant_id:
            return self.merchant_id
        self.merchant_id = resolve_merchant_id(self.page)
        return self.merchant_id
