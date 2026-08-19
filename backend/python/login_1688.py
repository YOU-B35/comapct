#!/usr/bin/env python3
"""1688 买家登录：python login_1688.py --tenant-id 5

打开有头 Chromium（持久化 Profile），导航到登录页；你在窗口里登录后，
脚本会把 Cookie 快照写到 Profile 目录，供后续 operational_crawl 复用。
"""
from __future__ import annotations

import argparse
import sys
import time

from app.browser.alibaba1688_context import profile_dir
from app.browser.alibaba1688_session import is_login_page, persist_1688_session, session_ready
from app.config import resolve_tenant_id

HOME_URL = "https://work.1688.com/"
LOGIN_URL = (
    "https://login.1688.com/member/signin.htm?"
    "Done=https%3A%2F%2Fwork.1688.com%2F"
)
WAIT_SECONDS = 600


def _logged_in(page, context) -> bool:
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
    # Heuristic fallback when cookie names differ
    if is_login_page(url):
        return False
    try:
        content = page.content()[:5000]
    except Exception:
        content = ""
    markers = ("退出", "我的阿里", "采购车", "采购工作台", "我的进货单", "进货单")
    if any(m in content for m in markers) and "密码登录" not in content and "扫码登录" not in content:
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="1688 买家后台登录（有头浏览器）")
    parser.add_argument("--tenant-id", type=int, help="租户 ID")
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=WAIT_SECONDS,
        help="最长等待登录秒数（默认 600）",
    )
    args = parser.parse_args()

    try:
        tenant_id = resolve_tenant_id(args.tenant_id)
    except ValueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print(f"错误: Playwright 不可用: {exc}", file=sys.stderr)
        sys.exit(1)

    user_data = profile_dir(tenant_id)
    print(f"正在打开 1688 登录窗口（tenant={tenant_id}）...")
    print(f"Profile: {user_data}")
    print("请在弹出的浏览器中完成登录；检测到登录态后会自动保存 Cookie 并关闭窗口。")
    print(f"最长等待 {args.wait_seconds} 秒。")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(user_data),
            headless=False,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90_000)

        deadline = time.monotonic() + max(30, int(args.wait_seconds))
        saved = None
        while time.monotonic() < deadline:
            if _logged_in(page, context):
                # Bounce to home to settle cookies
                try:
                    if is_login_page(page.url or ""):
                        page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60_000)
                        page.wait_for_timeout(2000)
                except Exception:
                    pass
                saved = persist_1688_session(tenant_id, page, context)
                break
            page.wait_for_timeout(2000)

        if not saved:
            # Still dump whatever cookies we have for debugging
            saved = persist_1688_session(tenant_id, page, context)
            context.close()
            print("超时：未检测到稳定登录态。已写入当前 Cookie 快照供排查。", file=sys.stderr)
            print(f"session={saved}")
            sys.exit(1)

        context.close()
        print(
            f"登录成功：cookies={saved.get('cookie_count')} "
            f"names={saved.get('cookie_names')}"
        )
        print(f"Cookie 快照: {user_data / '.crosshub-1688-cookies.json'}")
        print(f"会话元数据: {user_data / '.crosshub-1688-session.json'}")
        print("Profile 已保存，后续 sync/crawl 将复用该登录态。")


if __name__ == "__main__":
    main()
