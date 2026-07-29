#!/usr/bin/env python3

"""后台登录助手：用 Playwright 打开卖家后台并等待运营完成登录（与爬取共用同一 Profile）。"""

from __future__ import annotations



import argparse

import json

import os

import sys



from app.browser.context import (

    close_temu_runtime,

    describe_session,

    get_or_create_temu_runtime,

    get_or_open_seller_page,

    wait_for_login_and_mall,

)

from app.browser.profile_lock import clear_profile_lock, write_profile_lock, write_session_cache

from app.browser.session_state import build_session_payload, cache_payload_from_status

from app.config import resolve_tenant_id





def cache_login_progress(tenant_id: int, status: dict) -> None:

    write_session_cache(tenant_id, cache_payload_from_status(tenant_id, status))





def main() -> None:

    parser = argparse.ArgumentParser(description="Temu seller login assist")

    parser.add_argument("--tenant-id", type=int, help="租户 ID（或 TENANT_ID）")

    parser.add_argument("--timeout-seconds", type=int, default=1800)

    parser.add_argument("--json", action="store_true", help="结束时输出 JSON")

    args = parser.parse_args()



    try:

        tenant_id = resolve_tenant_id(args.tenant_id)

    except ValueError as exc:

        print(f"错误: {exc}", file=sys.stderr)

        sys.exit(2)



    result = {

        "tenant_id": tenant_id,

        "success": False,

        "ready": False,

        "mall_id": "",

        "message": "",

    }



    write_profile_lock(tenant_id, pid=os.getpid(), role="login_assist")

    try:

        close_temu_runtime(tenant_id)
        runtime = get_or_create_temu_runtime(tenant_id, headless=False)
        page = get_or_open_seller_page(runtime.context)

        try:

            page.bring_to_front()

        except Exception:

            pass

        mall_id = wait_for_login_and_mall(

            page,

            tenant_id=tenant_id,

            timeout_seconds=max(60, args.timeout_seconds),

            on_poll=lambda status: cache_login_progress(tenant_id, status),

        )

        status = describe_session(page)

        page.wait_for_timeout(1000)

        payload = build_session_payload(tenant_id, status, profile_busy=False)

        write_session_cache(tenant_id, payload)

        result.update(

            {

                "success": True,

                "ready": True,

                "mall_id": mall_id,

                "mall_count": status.get("mall_count") or 0,

                "message": "Temu 卖家后台登录已完成，浏览器将继续保留给后续 discover / 同步任务复用。",

            }

        )

    except Exception as exc:

        result["message"] = str(exc)

        if args.json:

            print(json.dumps(result, ensure_ascii=False))

        sys.exit(1)

    finally:

        clear_profile_lock(tenant_id)



    if args.json:

        print(json.dumps(result, ensure_ascii=False))

    else:

        print(result["message"])





if __name__ == "__main__":

    main()

