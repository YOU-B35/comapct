#!/usr/bin/env python3
"""AliExpress 卖家后台首次登录：python login_aliexpress.py --tenant-id 1"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from app.browser.ae_session import persist_ae_session
from app.browser.aliexpress_context import get_or_open_csp_page, open_aliexpress_context
from app.config import AE_CSP_HOME, resolve_aliexpress_profile_dir, resolve_tenant_id

DEFAULT_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_chrome_executable() -> str:
    env_path = os.getenv("CHROME_PATH", "").strip()
    candidates = [env_path] if env_path else []
    candidates.extend(DEFAULT_CHROME_PATHS)
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return "chrome"


def run_manual_chrome_login(tenant_id: int, *, session_key: str | None = None) -> None:
    profile_dir = resolve_aliexpress_profile_dir(tenant_id, session_key)
    profile_dir.mkdir(parents=True, exist_ok=True)
    command = [
        find_chrome_executable(),
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--new-window",
        AE_CSP_HOME,
    ]
    print("正在打开普通 Chrome（非 Playwright 控制）...")
    print(f"Profile: {profile_dir}")
    print("请在窗口中完成速卖通登录，成功后关闭 Chrome，再回到终端按 Enter。")
    process = subprocess.Popen(command)
    try:
        input("\n登录完成并关闭 Chrome 后，按 Enter 继续...")
    except KeyboardInterrupt:
        print("\n已取消", file=sys.stderr)
        sys.exit(1)
    if process.poll() is None:
        print("Chrome 仍在运行，请先关闭后再重试。", file=sys.stderr)
        sys.exit(1)
    try:
        with open_aliexpress_context(tenant_id, headless=True, session_key=session_key) as (_, context):
            page = context.new_page()
            page.goto(AE_CSP_HOME, wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(3_000)
            session = persist_ae_session(tenant_id, page, context, session_key=session_key)
            if session.get("logged_in"):
                print(f"已记录登录会话（cookies={session.get('cookie_count', 0)}）。")
            else:
                print("警告：未检测到有效登录态。", file=sys.stderr)
    except Exception as exc:
        print(f"警告：保存会话快照失败: {exc}", file=sys.stderr)
    print(f"登录 Profile 已保存：{profile_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AliExpress 卖家后台登录（有头浏览器）")
    parser.add_argument("--tenant-id", type=int, help="租户 ID")
    parser.add_argument("--session-key", default="", help="卖家会话 key（按账号隔离 Profile）")
    parser.add_argument("--account", default="", help="登录账号（自动生成 session-key）")
    parser.add_argument(
        "--manual",
        action="store_true",
        help="使用普通 Chrome 登录（绕过 Playwright 自动化指纹，登录页报「非法请求」时可试）",
    )
    args = parser.parse_args()

    try:
        tenant_id = resolve_tenant_id(args.tenant_id)
    except ValueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(2)

    from app.session_scope import build_session_key, normalize_session_key
    session_key = normalize_session_key(args.session_key) if args.session_key else None
    if not session_key and args.account:
        session_key = build_session_key(args.account)

    if args.manual:
        run_manual_chrome_login(tenant_id, session_key=session_key)
        return

    print(f"正在打开 AliExpress 卖家后台登录窗口（tenant={tenant_id}, session={session_key or 'default'}）...")
    print("请在浏览器中完成登录后关闭窗口。")

    with open_aliexpress_context(tenant_id, headless=False, session_key=session_key) as (_, context):
        page = get_or_open_csp_page(context)
        page.wait_for_timeout(300_000)
        try:
            session = persist_ae_session(tenant_id, page, context, session_key=session_key)
            if session.get("logged_in"):
                print(f"已记录登录会话（cookies={session.get('cookie_count', 0)}）。")
            else:
                print("警告：未检测到有效登录态，Cookie 可能未保存成功。", file=sys.stderr)
        except Exception as exc:
            print(f"警告：保存会话快照失败: {exc}", file=sys.stderr)

    print("登录窗口已关闭，Profile 已保存。")


if __name__ == "__main__":
    main()
