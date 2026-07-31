#!/usr/bin/env python3

"""Temu 卖家后台登录：启动与爬取同源的 Playwright 登录助手。"""

from __future__ import annotations



import argparse

import json

import subprocess

import sys

from pathlib import Path



from app.browser.context import close_tenant_profile_browsers

from app.browser.profile_lock import is_profile_locked, read_profile_lock

from app.config import TEMU_SELLER_HOME, resolve_tenant_id



CREATE_NEW_PROCESS_GROUP = 0x00000200

DETACHED_PROCESS = 0x00000008





from app.temu.session_scope import normalize_session_key



def spawn_login_assist(tenant_id: int, session_key: str | None = None) -> dict:
    key = normalize_session_key(session_key)
    if is_profile_locked(tenant_id, key):
        lock = read_profile_lock(tenant_id, key) or {}
        return {
            "tenant_id": tenant_id,
            "session_key": key,
            "opened": False,
            "already_open": True,
            "engine": "playwright",
            "url": TEMU_SELLER_HOME,
            "lock_role": lock.get("role") or "login_assist",
        }

    close_tenant_profile_browsers(tenant_id, session_key=key)

    script_dir = Path(__file__).resolve().parent
    assist = script_dir / "seller_login_assist.py"
    command = [
        sys.executable,
        str(assist),
        "--tenant-id",
        str(tenant_id),
        "--session-key",
        key,
        "--json",
    ]

    popen_kwargs: dict = {

        "cwd": str(script_dir),

        "stdin": subprocess.DEVNULL,

        "stdout": subprocess.DEVNULL,

        "stderr": subprocess.DEVNULL,

    }

    if sys.platform.startswith("win"):

        popen_kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    subprocess.Popen(command, **popen_kwargs)

    return {
        "tenant_id": tenant_id,
        "session_key": key,
        "opened": True,
        "already_open": False,
        "engine": "playwright",
        "url": TEMU_SELLER_HOME,
    }





def main() -> None:

    parser = argparse.ArgumentParser(description="Temu 卖家后台登录窗口")

    parser.add_argument("--tenant-id", type=int, help="租户 ID（或 TENANT_ID）")

    parser.add_argument("--session-key", help="Temu 卖家账号会话 key")

    parser.add_argument(

        "--open-only",

        action="store_true",

        help="启动 Playwright 登录助手后立即退出（供 CrossHub API 调用）",

    )

    parser.add_argument("--json", action="store_true", help="输出 JSON")

    args = parser.parse_args()



    try:

        tenant_id = resolve_tenant_id(args.tenant_id)

    except ValueError as exc:

        print(f"错误: {exc}", file=sys.stderr)

        sys.exit(2)



    if not args.open_only:

        print("=" * 60)

        print("Temu 卖家后台登录")

        print(f"租户 ID: {tenant_id}")

        print()

        print("步骤：")

        print("  1. 在 CrossHub 弹出的浏览器窗口中登录 Temu 卖家后台")

        print("  2. 登录后在左上角选择要同步的店铺")

        print("  3. 回到 CrossHub 点击「我已完成登录」或「刷新数据」")

        print("=" * 60)



    result = spawn_login_assist(tenant_id, session_key=args.session_key)

    if result.get("already_open"):

        result["message"] = (

            "登录窗口已在运行，请勿重复打开。请在已弹出的 CrossHub 浏览器中完成登录并选择店铺。"

        )

    else:

        result["message"] = (

            "已打开 CrossHub 登录窗口。请在该窗口完成 Temu 卖家后台登录并选择店铺，"

            "完成后回到本页点击「我已完成登录」或「刷新数据」。"

        )

    if args.json:

        print(json.dumps(result, ensure_ascii=False))

    elif args.open_only:

        print(result["message"])





if __name__ == "__main__":

    main()

