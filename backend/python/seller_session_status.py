#!/usr/bin/env python3
"""检查 Temu 卖家后台登录/选店状态（供 CrossHub API 调用）。"""
from __future__ import annotations

import argparse
import json
import sys

from app.browser.context import describe_session, get_or_open_seller_page, open_temu_context
from app.browser.profile_lock import (
    SESSION_CACHE_BUSY_MAX_AGE_SECONDS,
    is_profile_locked,
    read_profile_lock,
    read_ready_session_cache,
    read_session_cache,
)
from app.browser.session_state import build_session_payload, session_ready
from app.config import is_headless, resolve_tenant_id
from app.temu.session_aggregate import aggregate_tenant_sessions, merge_session_meta, parse_seller_sessions_payload
from app.temu.session_scope import DEFAULT_SESSION_KEY, normalize_session_key


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


def payload_from_cache(
    tenant_id: int,
    cached: dict,
    *,
    profile_busy: bool,
    session_key: str | None = None,
) -> dict:
    payload = build_session_payload(tenant_id, cached, profile_busy=profile_busy)
    payload["session_key"] = normalize_session_key(session_key or cached.get("session_key"))
    return payload


def build_cache_only_payload(
    tenant_id: int,
    session_key: str | None = None,
) -> dict:
    key = normalize_session_key(session_key)
    profile_busy = is_profile_locked(tenant_id, key)
    cached = read_ready_session_cache(tenant_id, session_key=key)
    if not cached and profile_busy:
        cached = read_session_cache(
            tenant_id,
            max_age_seconds=SESSION_CACHE_BUSY_MAX_AGE_SECONDS,
            session_key=key,
        )

    if cached:
        return payload_from_cache(tenant_id, cached, profile_busy=profile_busy, session_key=key)

    if profile_busy:
        lock = read_profile_lock(tenant_id, key)
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
                "session_key": key,
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
            "session_key": key,
        },
        profile_busy=False,
    )


def probe_session_live(tenant_id: int, session_key: str | None = None) -> dict:
    key = normalize_session_key(session_key)
    if is_profile_locked(tenant_id, key):
        cached = read_session_cache(
            tenant_id,
            max_age_seconds=SESSION_CACHE_BUSY_MAX_AGE_SECONDS,
            session_key=key,
        )
        if cached:
            return payload_from_cache(tenant_id, cached, profile_busy=True, session_key=key)
        return build_cache_only_payload(tenant_id, session_key=key)

    # Align with crawl (default headed). Headless probes often false-negative to /auth.
    profile_busy = False
    try:
        with open_temu_context(tenant_id, headless=is_headless(), session_key=key) as (_, context):
            page = get_or_open_seller_page(context)
            page.wait_for_load_state("domcontentloaded", timeout=60_000)
            page.wait_for_timeout(1500)
            status = describe_session(page)
    except Exception as exc:
        if profile_busy_error(exc):
            profile_busy = True
            cached = read_session_cache(
                tenant_id,
                max_age_seconds=SESSION_CACHE_BUSY_MAX_AGE_SECONDS,
                session_key=key,
            )
            if cached:
                return payload_from_cache(tenant_id, cached, profile_busy=True, session_key=key)
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
    payload["session_key"] = key
    if session_ready(status):
        from app.browser.profile_lock import write_session_cache

        write_session_cache(tenant_id, payload, session_key=key)
    return payload


def probe_all_sessions(
    tenant_id: int,
    seller_sessions: list[dict] | None = None,
) -> dict:
    metas = parse_seller_sessions_payload(seller_sessions)
    if not metas:
        metas = [{"session_key": DEFAULT_SESSION_KEY}]

    rows: list[dict] = []
    for meta in metas:
        key = normalize_session_key(str(meta.get("session_key") or DEFAULT_SESSION_KEY))
        cached = build_cache_only_payload(tenant_id, session_key=key)
        if session_ready(cached) and not cached.get("profile_busy"):
            row = dict(cached)
        else:
            row = probe_session_live(tenant_id, session_key=key)
        rows.append(merge_session_meta(row, meta))
    return aggregate_tenant_sessions(tenant_id, rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Temu seller session status")
    parser.add_argument("--tenant-id", type=int, help="租户 ID（或 TENANT_ID）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="仅读取会话缓存，不打开浏览器（供爬取前快速校验）",
    )
    parser.add_argument("--session-key", help="Temu 卖家账号会话 key")
    parser.add_argument(
        "--seller-sessions-json",
        help="JSON 数组：多卖家会话元数据",
    )
    args = parser.parse_args()

    try:
        tenant_id = resolve_tenant_id(args.tenant_id)
    except ValueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(2)

    seller_sessions = None
    if args.seller_sessions_json:
        try:
            seller_sessions = json.loads(args.seller_sessions_json)
        except json.JSONDecodeError as exc:
            print(f"错误: seller-sessions-json 无效: {exc}", file=sys.stderr)
            sys.exit(2)

    if seller_sessions is not None:
        payload = probe_all_sessions(tenant_id, seller_sessions)
    elif args.cache_only:
        if args.session_key:
            payload = build_cache_only_payload(tenant_id, session_key=args.session_key)
        else:
            payload = build_cache_only_payload(tenant_id)
    elif args.session_key:
        payload = probe_session_live(tenant_id, session_key=args.session_key)
    else:
        payload = probe_session_live(tenant_id)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
