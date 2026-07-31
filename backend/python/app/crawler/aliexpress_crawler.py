"""AliExpress 运营数据爬虫（全托管 JIT + 仓发备货）。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.browser.ae_session import persist_ae_session, resolve_headless_for_ae_crawl
from app.browser.aliexpress_context import (
    get_or_open_csp_page,
    open_aliexpress_context,
    wait_for_ae_login,
)
from app.config import AE_ORDER_PAGE
from app.crawler.aliexpress_api import AliExpressApiClient
from app.crawler.aliexpress_mapper import (
    map_jit_consign_orders,
    map_product_from_order,
    map_punish_list_violations,
    map_warehouse_purchase_orders,
)
from app.db import connect


def _load_bound_stores(tenant_id: int) -> list[dict[str, str]]:
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT id,
                   store_name,
                   external_shop_id
            FROM platform_account
            WHERE tenant_id = ? AND lower(platform) = 'aliexpress'
            ORDER BY bound_at DESC, store_name ASC
            """,
            (tenant_id,),
        ).fetchall()
    finally:
        conn.close()

    stores: list[dict[str, str]] = []
    for row in rows:
        platform_account_id = str(row[0] or "").strip()
        store_name = str(row[1] or platform_account_id or "AliExpress 店铺").strip()
        external_shop_id = str(row[2] or "").strip()
        # 语义约定：
        # - store_id：优先使用外部店铺 ID（external_shop_id），否则退化为 platform_account.id（绑定记录 id）
        # - platform_account_id：永远是绑定记录 id，用于可追溯与后续迁移
        store_id = external_shop_id or platform_account_id
        if store_id:
            stores.append(
                {
                    "store_id": store_id,
                    "store_name": store_name,
                    "platform_account_id": platform_account_id,
                    "external_shop_id": external_shop_id,
                }
            )
    if not stores:
        stores.append({"store_id": "default", "store_name": "AliExpress 店铺"})
    return stores


def _detect_permission_denied(page) -> str | None:
    try:
        text = page.evaluate("() => (document.body && document.body.innerText) || ''") or ""
    except Exception:
        return None
    markers = (
        "无权访问",
        "无权限",
        "权限访问该页面",
        "not authorized",
        "no permission",
    )
    lowered = text.lower()
    if any(marker in text for marker in markers) or "permission" in lowered:
        return text[:300]
    return None


def crawl_aliexpress_operational(
    report_day: str | None = None,
    *,
    tenant_id: int = 1,
    scope: str = "all",
    store_id: str | None = None,
    store_name: str | None = None,
    session_key: str | None = None,
) -> dict[str, Any]:
    report_time = report_day or date.today().isoformat()
    stores = _load_bound_stores(tenant_id)
    if store_id:
        stores = [s for s in stores if s["store_id"] == store_id] or [
            {"store_id": store_id, "store_name": store_name or store_id}
        ]

    all_orders: list[dict[str, Any]] = []
    all_violations: list[dict[str, Any]] = []
    debug: dict[str, Any] = {"stores": [], "permission_errors": [], "session_key": session_key or "default"}

    headless = resolve_headless_for_ae_crawl(tenant_id, session_key=session_key)
    with open_aliexpress_context(tenant_id, headless=headless, session_key=session_key) as (_, context):
        page = get_or_open_csp_page(context)
        wait_for_ae_login(page, tenant_id=tenant_id, context=context, session_key=session_key)
        persist_ae_session(tenant_id, page, context, session_key=session_key)

        denied = _detect_permission_denied(page)
        if denied and AE_ORDER_PAGE in (page.url or ""):
            debug["permission_errors"].append(denied)

        client = AliExpressApiClient(page)
        jit_rows: list[dict[str, Any]] = []
        warehouse_rows: list[dict[str, Any]] = []
        violation_rows: list[dict[str, Any]] = []

        if scope in ("all", "orders", "operational"):
            try:
                jit_rows = client.fetch_jit_consign_orders(report_time)
                debug["jit_rows"] = len(jit_rows)
            except Exception as exc:
                debug["jit_error"] = str(exc)
            try:
                warehouse_rows = client.fetch_warehouse_purchase_orders(report_time)
                debug["warehouse_rows"] = len(warehouse_rows)
            except Exception as exc:
                debug["warehouse_error"] = str(exc)

        if scope in ("all", "violations"):
            try:
                violation_rows = client.fetch_violations()
                debug["violation_rows"] = len(violation_rows)
            except Exception as exc:
                debug["violation_error"] = str(exc)

        for store in stores:
            sid = store["store_id"]
            sname = store["store_name"]
            if scope in ("all", "orders", "operational"):
                all_orders.extend(
                    map_jit_consign_orders(
                        jit_rows,
                        tenant_id=tenant_id,
                        store_id=sid,
                        store_name=sname,
                        report_day=report_time,
                    )
                )
                all_orders.extend(
                    map_warehouse_purchase_orders(
                        warehouse_rows,
                        tenant_id=tenant_id,
                        store_id=sid,
                        store_name=sname,
                        report_day=report_time,
                    )
                )
            if scope in ("all", "violations"):
                all_violations.extend(
                    map_punish_list_violations(
                        violation_rows,
                        tenant_id=tenant_id,
                        store_id=sid,
                        store_name=sname,
                    )
                )
            debug["stores"].append(
                {
                    "store_id": sid,
                    "orders": len(all_orders),
                    "violations": len(all_violations),
                }
            )

    products_by_sku: dict[str, dict[str, Any]] = {}
    for order in all_orders:
        sku = order.get("sku") or ""
        if not sku:
            continue
        product = map_product_from_order(order)
        existing = products_by_sku.get(sku)
        if existing:
            existing["daily_sales"] = int(existing.get("daily_sales") or 0) + int(order.get("quantity") or 0)
        else:
            products_by_sku[sku] = product

    products = list(products_by_sku.values())
    shops = [
        {"shop_id": store["store_id"], "shop_name": store["store_name"], "tenant_id": tenant_id}
        for store in stores
    ]
    return {
        "report_time": report_time,
        "shops": shops,
        "orders": all_orders,
        "violations": all_violations,
        "products": products,
        "broadcasts": [],
        "debug": debug,
    }
