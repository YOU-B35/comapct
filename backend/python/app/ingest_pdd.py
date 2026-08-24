"""Upsert PDD data into SQLite (orders / products / compass)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.db import connect

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _now() -> str:
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")


def _resolve_store_id(conn, tenant_id: int, row: dict[str, Any]) -> str:
    """Resolve store_id from row or platform_account mapping."""
    explicit = (row.get("store_id") or "").strip()
    if explicit and explicit != "all":
        return explicit

    external = (row.get("external_shop_id") or "").strip()
    if external:
        hit = conn.execute(
            """
            SELECT id FROM platform_account
            WHERE tenant_id = ? AND platform = 'pdd' AND external_shop_id = ?
            LIMIT 1
            """,
            (tenant_id, external),
        ).fetchone()
        if hit:
            return str(hit[0])

    # 尝试获取默认的拼多多店铺
    rows = conn.execute(
        """
        SELECT id FROM platform_account
        WHERE tenant_id = ? AND platform = 'pdd'
        ORDER BY created_at DESC
        """,
        (tenant_id,),
    ).fetchall()

    if len(rows) == 1:
        return str(rows[0][0])
    if len(rows) == 0:
        return f"tenant-{tenant_id}-pdd-default"

    # 多个店铺时使用第一个
    return str(rows[0][0])


def upsert_orders(tenant_id: int, rows: list[dict[str, Any]]) -> int:
    """Upsert PDD orders into pdd_order table (no wipe, idempotent)."""
    if not rows:
        return 0

    conn = connect()
    try:
        count = 0
        now = _now()
        today = datetime.now(SHANGHAI).date().isoformat()
        date_window = "today"

        for row in rows:
            store_id = _resolve_store_id(conn, tenant_id, row)
            order_no = str(row.get("order_no") or "").strip()

            if not store_id or not order_no:
                continue

            # 检查订单是否已存在
            existing = conn.execute(
                """
                SELECT id FROM pdd_order
                WHERE tenant_id = ? AND store_id = ? AND order_no = ?
                """,
                (tenant_id, store_id, order_no),
            ).fetchone()

            row_id = str(existing[0]) if existing else uuid.uuid4().hex

            # Upsert 订单
            conn.execute(
                """
                INSERT INTO pdd_order (
                  id, tenant_id, store_id, external_shop_id, report_day, date_window,
                  order_no, product_name, channel, sku, quantity, amount, currency, status,
                  ship_deadline, ordered_at, order_key, raw_json, created_at, updated_at,
                  paid_amount, refunded_amount, paid_at, refunded_at, buyer_masked,
                  synced_at, unit_price, item_amount, image_url, sku_text
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  status=excluded.status,
                  paid_amount=excluded.paid_amount,
                  refunded_amount=excluded.refunded_amount,
                  paid_at=excluded.paid_at,
                  refunded_at=excluded.refunded_at,
                  synced_at=excluded.synced_at,
                  updated_at=excluded.updated_at
                """,
                (
                    row_id,
                    tenant_id,
                    store_id,
                    row.get("external_shop_id", ""),
                    today,
                    date_window,
                    order_no,
                    row.get("product_name", ""),
                    row.get("channel", ""),
                    row.get("sku", ""),
                    row.get("quantity", 1),
                    row.get("amount", 0),
                    row.get("currency", "CNY"),
                    row.get("status", ""),
                    row.get("ship_deadline", ""),
                    row.get("ordered_at", now),
                    str(row.get("order_key") or f"{store_id}:{order_no}"),
                    str(row),
                    now,
                    now,
                    row.get("paid_amount", "0"),
                    row.get("refunded_amount", "0"),
                    row.get("paid_at", ""),
                    row.get("refunded_at", ""),
                    row.get("buyer_masked", ""),
                    now,
                    row.get("unit_price", "0"),
                    row.get("item_amount", "0"),
                    row.get("image_url", ""),
                    row.get("sku_text", ""),
                ),
            )
            count += 1

        conn.commit()
        return count
    finally:
        conn.close()


def upsert_products(tenant_id: int, rows: list[dict[str, Any]]) -> int:
    """Upsert PDD products into pdd_product table."""
    if not rows:
        return 0

    conn = connect()
    try:
        count = 0
        now = _now()

        for row in rows:
            store_id = _resolve_store_id(conn, tenant_id, row)
            product_key = str(row.get("product_key") or row.get("product_id") or "").strip()

            if not store_id or not product_key:
                continue

            # 检查商品是否已存在
            existing = conn.execute(
                """
                SELECT id FROM pdd_product
                WHERE tenant_id = ? AND store_id = ? AND product_key = ?
                """,
                (tenant_id, store_id, product_key),
            ).fetchone()

            row_id = str(existing[0]) if existing else uuid.uuid4().hex

            # Upsert 商品
            conn.execute(
                """
                INSERT INTO pdd_product (
                  id, tenant_id, store_id, external_shop_id, product_id, product_key,
                  product_name, status, status_label, price, stock, sales,
                  main_image, category, article_no, sku_count, skus_json,
                  raw_json, synced_at, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  price=excluded.price,
                  stock=excluded.stock,
                  sales=excluded.sales,
                  status=excluded.status,
                  synced_at=excluded.synced_at,
                  updated_at=excluded.updated_at
                """,
                (
                    row_id,
                    tenant_id,
                    store_id,
                    row.get("external_shop_id", ""),
                    row.get("product_id", ""),
                    product_key,
                    row.get("product_name", ""),
                    row.get("status", ""),
                    row.get("status_label", ""),
                    row.get("price"),
                    row.get("stock"),
                    row.get("sales"),
                    row.get("main_image", ""),
                    row.get("category", ""),
                    row.get("article_no", ""),
                    row.get("sku_count", 0),
                    row.get("skus_json", ""),
                    str(row),
                    now,
                    row.get("created_at", now),
                    now,
                ),
            )
            count += 1

        conn.commit()
        return count
    finally:
        conn.close()


def upsert_compass(tenant_id: int, payload: dict[str, Any], date_type: int = 1) -> bool:
    """Upsert PDD compass snapshot."""
    if not payload:
        return False

    conn = connect()
    try:
        now = _now()
        store_id = _resolve_store_id(conn, tenant_id, payload)

        # 使用 date_type + date_window 作为唯一键
        window_map = {1: "realtime", 20: "d1", 21: "d7", 23: "d30"}
        date_window = window_map.get(date_type, "realtime")

        # 检查是否已存在
        existing = conn.execute(
            """
            SELECT id FROM pdd_compass_snapshot
            WHERE tenant_id = ? AND store_id = ? AND date_type = ? AND date_window = ?
            """,
            (tenant_id, store_id, date_type, date_window),
        ).fetchone()

        snapshot_id = str(existing[0]) if existing else uuid.uuid4().hex

        # Payload JSON 序列化
        payload_json = str(payload) if isinstance(payload, dict) else payload

        # Upsert 罗盘
        conn.execute(
            """
            INSERT INTO pdd_compass_snapshot (
              id, tenant_id, store_id, date_type, date_window,
              payload_json, raw_json, synced_at, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              payload_json=excluded.payload_json,
              synced_at=excluded.synced_at,
              updated_at=excluded.updated_at
            """,
            (
                snapshot_id,
                tenant_id,
                store_id,
                date_type,
                date_window,
                payload_json,
                "",
                now,
                now,
                now,
            ),
        )

        conn.commit()
        return True
    finally:
        conn.close()
