#!/usr/bin/env python3

"""检查 Temu 卖家后台登录/选店状态（供 CrossHub API 调用）。"""

from __future__ import annotations



import argparse

import json

import sys



from app.browser.context import describe_session, get_or_open_seller_page, open_temu_context

from app.browser.profile_lock import is_profile_locked, read_profile_lock, read_session_cache

from app.browser.session_state import build_session_payload, session_ready

from app.config import resolve_tenant_id





def profile_busy_error(exc: Exception) -> bool:

    text = str(exc).lower()

    return any(

        token in text

        for token in (

            "singletonlock",

            "user data directory",

            "already in use",

            "profile",

            "process_singleton",

        )

    )





def payload_from_cache(tenant_id: int, cached: dict, *, profile_busy: bool) -> dict:
    return build_session_payload(tenant_id, cached, profile_busy=profile_busy)





def build_cache_only_payload(tenant_id: int) -> dict:

    profile_busy = is_profile_locked(tenant_id)

    cached = read_session_cache(tenant_id, max_age_seconds=1800)

    if cached:

        return payload_from_cache(tenant_id, cached, profile_busy=profile_busy)



    lock = read_profile_lock(tenant_id)

    if profile_busy:

        return build_session_payload(

            tenant_id,

            {

                "requires_auth": True,

                "logged_in": False,

                "mall_id": "",

                "mall_count": 0,

                "malls": [],

                "url": "",

                "title": "",

            },

            profile_busy=True,

        )



    return build_session_payload(

        tenant_id,

        {

            "requires_auth": True,

            "logged_in": False,

            "mall_id": "",

            "mall_count": 0,

            "malls": [],

            "url": "",

            "title": "",

        },

        profile_busy=False,

    )





def main() -> None:

    parser = argparse.ArgumentParser(description="Temu seller session status")

    parser.add_argument("--tenant-id", type=int, help="租户 ID（或 TENANT_ID）")

    parser.add_argument("--json", action="store_true", help="输出 JSON")

    parser.add_argument(

        "--cache-only",

        action="store_true",

        help="仅读取会话缓存，不打开浏览器（供爬取前快速校验）",

    )

    args = parser.parse_args()



    try:

        tenant_id = resolve_tenant_id(args.tenant_id)

    except ValueError as exc:

        print(f"错误: {exc}", file=sys.stderr)

        sys.exit(2)



    if args.cache_only:

        payload = build_cache_only_payload(tenant_id)

        if args.json:

            print(json.dumps(payload, ensure_ascii=False))

        else:

            print(json.dumps(payload, ensure_ascii=False, indent=2))

        return



    if is_profile_locked(tenant_id):

        cached = read_session_cache(tenant_id, max_age_seconds=1800)

        if cached:

            payload = payload_from_cache(tenant_id, cached, profile_busy=True)

            if args.json:

                print(json.dumps(payload, ensure_ascii=False))

            else:

                print(json.dumps(payload, ensure_ascii=False, indent=2))

            return



        payload = build_session_payload(

            tenant_id,

            {

                "requires_auth": True,

                "logged_in": False,

                "mall_id": "",

                "mall_count": 0,

                "malls": [],

                "url": "",

                "title": "",

            },

            profile_busy=True,

        )

        if args.json:

            print(json.dumps(payload, ensure_ascii=False))

        else:

            print(json.dumps(payload, ensure_ascii=False, indent=2))

        return



    profile_busy = False

    status: dict

    try:

        with open_temu_context(tenant_id, headless=True) as (_, context):

            page = get_or_open_seller_page(context)

            page.wait_for_load_state("domcontentloaded", timeout=60_000)

            page.wait_for_timeout(1500)

            status = describe_session(page)

    except Exception as exc:

        if profile_busy_error(exc):

            profile_busy = True

            cached = read_session_cache(tenant_id, max_age_seconds=1800)

            if cached:

                payload = payload_from_cache(tenant_id, cached, profile_busy=True)

                if args.json:

                    print(json.dumps(payload, ensure_ascii=False))

                else:

                    print(json.dumps(payload, ensure_ascii=False, indent=2))

                return

            status = {

                "url": "",

                "title": "",

                "requires_auth": True,

                "logged_in": False,

                "mall_id": "",

                "mall_count": 0,

                "malls": [],

            }

        else:

            raise



    payload = build_session_payload(tenant_id, status, profile_busy=profile_busy)

    if session_ready(status):

        from app.browser.profile_lock import write_session_cache



        write_session_cache(tenant_id, payload)

    if args.json:

        print(json.dumps(payload, ensure_ascii=False))

    else:

        print(json.dumps(payload, ensure_ascii=False, indent=2))





if __name__ == "__main__":

    main()

