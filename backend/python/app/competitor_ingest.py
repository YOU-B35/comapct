"""Persist Temu competitor crawler snapshots into the shared SQLite DB."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from .crawler.competitor_crawler import crawl_competitor_products
from .db import connect, init_schema, seed_users

SHANGHAI = ZoneInfo("Asia/Shanghai")


def init_competitor_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS temu_competitor (
          id TEXT PRIMARY KEY,
          tenant_id INTEGER NOT NULL,
          label TEXT NOT NULL,
          url TEXT NOT NULL,
          host TEXT NOT NULL DEFAULT '',
          last_analyzed_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS temu_competitor_snapshot (
          id TEXT PRIMARY KEY,
          tenant_id INTEGER NOT NULL,
          competitor_id TEXT NOT NULL,
          snapshot_date TEXT NOT NULL,
          product_id TEXT NOT NULL,
          product_name TEXT NOT NULL,
          category TEXT NOT NULL DEFAULT '',
          price REAL NOT NULL DEFAULT 0,
          daily_sales INTEGER NOT NULL DEFAULT 0,
          total_sales INTEGER NOT NULL DEFAULT 0,
          listed_at TEXT NOT NULL,
          url TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_temu_competitor_snapshot_unique
        ON temu_competitor_snapshot (tenant_id, competitor_id, snapshot_date, product_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_temu_competitor_snapshot_report
        ON temu_competitor_snapshot (tenant_id, competitor_id, snapshot_date DESC)
        """
    )
    conn.commit()


def replace_competitor_snapshot(
    conn: sqlite3.Connection,
    tenant_id: int,
    competitor_id: str,
    snapshot_date: str,
    products: list[dict],
) -> int:
    conn.execute(
        """
        DELETE FROM temu_competitor_snapshot
        WHERE tenant_id = ? AND competitor_id = ? AND snapshot_date = ?
        """,
        (tenant_id, competitor_id, snapshot_date),
    )
    now = datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")
    for product in products:
        conn.execute(
            """
            INSERT INTO temu_competitor_snapshot (
              id, tenant_id, competitor_id, snapshot_date, product_id, product_name,
              category, price, daily_sales, total_sales, listed_at, url, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"cs_{competitor_id}_{snapshot_date.replace('-', '')}_{product['product_id']}",
                tenant_id,
                competitor_id,
                snapshot_date,
                product["product_id"],
                product["product_name"],
                product.get("category", ""),
                float(product.get("price") or 0),
                int(product.get("daily_sales") or 0),
                int(product.get("total_sales") or 0),
                product.get("listed_at") or snapshot_date,
                product.get("url", ""),
                now,
            ),
        )
    return len(products)


def run_competitor_ingest(
    *,
    tenant_id: int,
    competitor_id: str,
    competitor_url: str,
    label: str = "",
    crawl_date: str | None = None,
    max_products: int = 80,
) -> dict:
    payload = crawl_competitor_products(
        tenant_id=tenant_id,
        competitor_url=competitor_url,
        max_products=max_products,
        crawl_date=crawl_date,
    )
    conn = connect()
    try:
        init_schema(conn)
        seed_users(conn)
        init_competitor_schema(conn)
        rows = replace_competitor_snapshot(
            conn,
            tenant_id,
            competitor_id,
            payload["snapshot_date"],
            payload["products"],
        )
        now = datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """
            UPDATE temu_competitor
            SET last_analyzed_at = ?, updated_at = ?
            WHERE tenant_id = ? AND id = ?
            """,
            (now, now, tenant_id, competitor_id),
        )
        conn.commit()
        return {
            "tenant_id": tenant_id,
            "competitor_id": competitor_id,
            "label": label,
            "snapshot_date": payload["snapshot_date"],
            "rows": rows,
            "raw_count": payload["raw_count"],
        }
    finally:
        conn.close()
