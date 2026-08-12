"""
Temu 全托管运营数据爬虫

Playwright 持久化浏览器 + 卖家后台 API（与 Commander Agent 同路径）
"""
from __future__ import annotations

import time
from datetime import date

from app.browser.context import (
    close_tenant_profile_browsers,
    describe_session,
    ensure_logged_in,
    fetch_mall_list,
    get_or_open_seller_page,
    open_temu_context,
    set_mall_id,
    wait_for_login_and_mall,
)
from app.browser.profile_lock import (
    SESSION_CACHE_BUSY_MAX_AGE_SECONDS,
    clear_profile_lock,
    clear_session_cache,
    is_profile_locked,
    read_ready_session_cache,
    read_session_cache,
    write_session_cache,
)
from app.browser.session_state import cache_payload_from_status, session_ready
from app.config import is_headless
from app.crawler.mapper import map_sales_batches
from app.crawler.temu_api import TemuApiClient
from app.temu.session_aggregate import parse_seller_sessions_payload
from app.temu.session_scope import DEFAULT_SESSION_KEY, normalize_session_key
from app.temu.shop_scope import filter_malls_by_shop_ids


def ensure_profile_available(
    tenant_id: int,
    *,
    session_key: str | None = None,
    timeout_seconds: int = 30,
) -> None:
    from app.browser.context import close_temu_runtime

    # Always drop in-process login/crawl runtimes first (lock file may be absent).
    try:
        close_temu_runtime(tenant_id, session_key=session_key)
    except Exception:
        pass

    cached = read_ready_session_cache(tenant_id, session_key=session_key)
    if cached and session_ready(cached):
        close_tenant_profile_browsers(tenant_id, session_key=session_key)
        clear_profile_lock(tenant_id, session_key)
        time.sleep(1.5)
        return

    deadline = time.monotonic() + max(0, timeout_seconds)
    while is_profile_locked(tenant_id, session_key) and time.monotonic() < deadline:
        try:
            close_temu_runtime(tenant_id, session_key=session_key)
        except Exception:
            pass
        close_tenant_profile_browsers(tenant_id, session_key=session_key)
        clear_profile_lock(tenant_id, session_key)
        time.sleep(2)

    if is_profile_locked(tenant_id, session_key):
        cached = read_session_cache(
            tenant_id,
            max_age_seconds=SESSION_CACHE_BUSY_MAX_AGE_SECONDS,
            session_key=session_key,
        )
        if cached and session_ready(cached):
            close_tenant_profile_browsers(tenant_id, session_key=session_key)
            clear_profile_lock(tenant_id, session_key)
            time.sleep(1.5)
            return
        raise RuntimeError(
            "Temu 登录窗口仍在使用中。请关闭 CrossHub 弹出的登录浏览器，再点击「刷新数据」。"
        )

    # Even without a lock file, kill leftover Chrome holding this profile.
    close_tenant_profile_browsers(tenant_id, session_key=session_key)
    time.sleep(0.8)


def _resolve_malls(page, fallback_mall_id: str) -> list[dict]:
    malls = fetch_mall_list(page)
    if malls:
        return malls
    if fallback_mall_id:
        return [{"mallId": fallback_mall_id, "mallName": ""}]
    raise RuntimeError("未获取到可同步的 Temu 店铺列表，请重新登录并选择店铺。")


def crawl_temu_sales_live(
    report_day: str | None = None,
    *,
    tenant_id: int = 1,
    session_key: str | None = None,
    shop_ids: list | None = None,
) -> dict:
    key = normalize_session_key(session_key)
    report_time = report_day or date.today().isoformat()
    cached = read_ready_session_cache(tenant_id, session_key=key)

    ensure_profile_available(tenant_id, session_key=key)
    close_tenant_profile_browsers(tenant_id, session_key=key)

    with open_temu_context(tenant_id, headless=is_headless(), session_key=key) as (_, context):
        page = get_or_open_seller_page(context)
        try:
            if cached and session_ready(cached):
                mall_id = ensure_logged_in(page)
            else:
                mall_id = wait_for_login_and_mall(
                    page,
                    tenant_id=tenant_id,
                    timeout_seconds=90,
                    on_poll=lambda status: write_session_cache(
                        tenant_id,
                        cache_payload_from_status(tenant_id, status),
                        session_key=key,
                    ),
                )
        except RuntimeError:
            clear_session_cache(tenant_id, session_key=key)
            raise

        client = TemuApiClient(page)
        client.ensure_sales_context()
        malls = filter_malls_by_shop_ids(_resolve_malls(page, mall_id), shop_ids)
        if not malls:
            raise RuntimeError(
                "当前账号下没有权限范围内的 Temu 店铺可同步，请确认店铺授权后重试。"
            )
        all_rows: list[dict] = []
        shops: list[dict] = []
        seen_shop_ids: set[str] = set()

        for mall in malls:
            current_mall_id = str(mall.get("mallId") or "").strip()
            if not current_mall_id:
                continue
            client.switch_mall(current_mall_id)
            shop_name, shop_id = client.get_shop_info()
            if not shop_name:
                shop_name = str(mall.get("mallName") or shop_id)
            batches = client.fetch_all_sales()
            all_rows.extend(
                map_sales_batches(
                    batches,
                    shop_id=shop_id,
                    shop_name=shop_name,
                    report_time=report_time,
                    tenant_id=tenant_id,
                )
            )
            if shop_id not in seen_shop_ids:
                seen_shop_ids.add(shop_id)
                shops.append(
                    {
                        "shop_id": shop_id,
                        "shop_name": shop_name,
                        "is_upload": True,
                        "tenant_id": tenant_id,
                    }
                )

        if not shops:
            raise RuntimeError("未同步到任何 Temu 店铺数据，请确认卖家后台已登录并选择店铺。")

        set_mall_id(page, str(shops[0]["shop_id"]))
        session = describe_session(page)
        write_session_cache(
            tenant_id,
            cache_payload_from_status(
                tenant_id,
                {
                    **session,
                    "logged_in": True,
                    "mall_id": shops[0]["shop_id"],
                    "mall_count": len(shops),
                    "malls": [
                        {"mallId": s["shop_id"], "mallName": s["shop_name"]}
                        for s in shops
                    ],
                    "requires_auth": False,
                },
            ),
            session_key=key,
        )
        return {
            "report_time": report_time,
            "shops": shops,
            "rows": all_rows,
            "session_key": key,
        }


def crawl_temu_sales_all_sessions(
    report_day: str | None = None,
    *,
    tenant_id: int = 1,
    seller_sessions: list[dict] | None = None,
    max_parallel: int | None = None,
    shop_ids: list | None = None,
) -> dict:
    """并行爬取租户下各 Temu 卖家账号 Profile（默认最多 3 路），每个会话内 switch_mall 拉全店。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import os

    sessions = parse_seller_sessions_payload(seller_sessions)
    if not sessions:
        sessions = [{"session_key": DEFAULT_SESSION_KEY}]

    report_time = report_day or date.today().isoformat()
    all_shops: list[dict] = []
    all_rows: list[dict] = []
    seen_shop_ids: set[str] = set()
    errors: list[str] = []

    workers = max_parallel
    if workers is None:
        try:
            workers = int(os.getenv("TEMU_CRAWL_MAX_PARALLEL", "3"))
        except ValueError:
            workers = 3
    workers = max(1, min(int(workers), len(sessions)))

    def _one(meta: dict) -> tuple[str, dict]:
        key = normalize_session_key(str(meta.get("session_key") or DEFAULT_SESSION_KEY))
        label = str(meta.get("account") or key).strip() or key
        payload = crawl_temu_sales_live(
            report_day, tenant_id=tenant_id, session_key=key, shop_ids=shop_ids
        )
        return label, payload

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_one, meta): meta for meta in sessions}
        for fut in as_completed(futures):
            meta = futures[fut]
            key = normalize_session_key(str(meta.get("session_key") or DEFAULT_SESSION_KEY))
            label = str(meta.get("account") or key).strip() or key
            try:
                _label, payload = fut.result()
                for shop in payload.get("shops") or []:
                    shop_id = str(shop.get("shop_id") or "").strip()
                    if shop_id and shop_id not in seen_shop_ids:
                        seen_shop_ids.add(shop_id)
                        all_shops.append(shop)
                all_rows.extend(payload.get("rows") or [])
            except Exception as exc:
                errors.append(f"{label}: {exc}")

    if not all_shops:
        detail = "; ".join(errors[:3])
        raise RuntimeError(
            detail or "未同步到任何 Temu 店铺数据，请为每个卖家账号完成登录后再刷新。"
        )

    return {
        "report_time": report_time,
        "shops": all_shops,
        "rows": all_rows,
        "session_errors": errors,
        "sessions_synced": len(sessions) - len(errors),
    }


def crawl_temu_sales(
    report_day: str | None = None,
    *,
    use_seed: bool = False,
    tenant_id: int = 1,
    session_key: str | None = None,
    seller_sessions: list[dict] | None = None,
    shop_ids: list | None = None,
) -> dict:
    if use_seed:
        raise RuntimeError("种子数据模式已关闭，请完成 Temu 登录后使用真实爬取")
    if seller_sessions:
        return crawl_temu_sales_all_sessions(
            report_day,
            tenant_id=tenant_id,
            seller_sessions=seller_sessions,
            shop_ids=shop_ids,
        )
    return crawl_temu_sales_live(
        report_day, tenant_id=tenant_id, session_key=session_key, shop_ids=shop_ids
    )
