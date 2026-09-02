"""Upsert 1688 purchase orders into SQLite (no wipe)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.db import connect
from app.timezone import SHANGHAI



def _now() -> str:
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")


def _row_id(row) -> str:
    if row is None:
        return ""
    if hasattr(row, "keys"):
        return str(row["id"])
    return str(row[0])


def _resolve_store_id(conn, tenant_id: int, row: dict[str, Any]) -> str:
    explicit = (row.get("store_id") or "").strip()
    if explicit:
        return explicit
    external = (row.get("external_shop_id") or "").strip()
    if external:
        hit = conn.execute(
            """
            SELECT id FROM platform_account
            WHERE tenant_id = ? AND platform = '1688' AND external_shop_id = ?
            LIMIT 1
            """,
            (tenant_id, external),
        ).fetchone()
        if hit:
            return _row_id(hit)
    rows = conn.execute(
        """
        SELECT id FROM platform_account
        WHERE tenant_id = ? AND platform = '1688'
        ORDER BY created_at DESC
        """,
        (tenant_id,),
    ).fetchall()
    if len(rows) == 1:
        return _row_id(rows[0])
    if len(rows) == 0:
        return f"tenant-{tenant_id}-1688-default"
    raise RuntimeError("A1688_SHOP_MAPPING_REQUIRED: multiple 1688 stores; set external_shop_id")


def upsert_purchase_orders(tenant_id: int, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    conn = connect()
    try:
        count = 0
        now = _now()
        for row in rows:
            store_id = _resolve_store_id(conn, tenant_id, row)
            order_no = str(row.get("order_no") or "").strip()
            if not store_id or not order_no:
                continue
            existing = conn.execute(
                """
                SELECT id FROM alibaba1688_purchase_order
                WHERE tenant_id = ? AND store_id = ? AND order_no = ?
                """,
                (tenant_id, store_id, order_no),
            ).fetchone()
            row_id = _row_id(existing) if existing else uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO alibaba1688_purchase_order (
                  id, tenant_id, store_id, order_no, status, pay_status, ship_status,
                  product_name, sku, supplier_name, supplier_id, quantity, unit_price, amount,
                  currency, linked_platform, expected_arrival_at, expected_ship_at, actual_ship_at,
                  logistics_status, logistics_no, is_delayed, is_stockout, raw_json, synced_at,
                  created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  status=excluded.status,
                  supplier_name=excluded.supplier_name,
                  amount=excluded.amount,
                  expected_arrival_at=excluded.expected_arrival_at,
                  logistics_status=excluded.logistics_status,
                  is_stockout=excluded.is_stockout,
                  synced_at=excluded.synced_at,
                  updated_at=excluded.updated_at
                """,
                (
                    row_id,
                    tenant_id,
                    store_id,
                    order_no,
                    row.get("status"),
                    row.get("pay_status"),
                    row.get("ship_status"),
                    row.get("product_name"),
                    row.get("sku"),
                    row.get("supplier_name"),
                    row.get("supplier_id"),
                    row.get("quantity"),
                    row.get("unit_price"),
                    row.get("amount"),
                    row.get("currency") or "CNY",
                    row.get("linked_platform"),
                    row.get("expected_arrival_at"),
                    row.get("expected_ship_at"),
                    row.get("actual_ship_at"),
                    row.get("logistics_status"),
                    row.get("logistics_no"),
                    int(row.get("is_delayed") or 0),
                    int(row.get("is_stockout") or 0),
                    row.get("raw_json"),
                    row.get("synced_at") or now,
                    now,
                    now,
                ),
            )
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()
