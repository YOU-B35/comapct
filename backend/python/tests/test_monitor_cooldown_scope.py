"""Monitor crawl success must write scope=monitor:{target_id}, not platform."""
from __future__ import annotations

import sqlite3

import pytest

from app.monitor_worker_service import record_monitor_crawl_success


@pytest.fixture
def tmp_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE tenant_crawl_cooldown (
          tenant_id INTEGER NOT NULL,
          scope TEXT NOT NULL DEFAULT 'platform',
          last_success_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY (tenant_id, scope)
        )
        """
    )
    conn.commit()
    yield conn
    conn.close()


def test_record_monitor_success_uses_monitor_scope(tmp_db):
    record_monitor_crawl_success(tmp_db, 5, "mt_abc")

    rows = tmp_db.execute(
        "SELECT tenant_id, scope FROM tenant_crawl_cooldown ORDER BY scope"
    ).fetchall()
    scopes = [row["scope"] for row in rows]

    assert scopes == ["monitor:mt_abc"]
    assert "platform" not in scopes
    assert rows[0]["tenant_id"] == 5


def test_record_monitor_success_upserts_same_monitor_scope(tmp_db):
    record_monitor_crawl_success(tmp_db, 5, "mt_abc")
    first = tmp_db.execute(
        "SELECT last_success_at FROM tenant_crawl_cooldown WHERE scope = ?",
        ("monitor:mt_abc",),
    ).fetchone()["last_success_at"]

    record_monitor_crawl_success(tmp_db, 5, "mt_abc")
    second = tmp_db.execute(
        "SELECT last_success_at FROM tenant_crawl_cooldown WHERE scope = ?",
        ("monitor:mt_abc",),
    ).fetchone()["last_success_at"]

    count = tmp_db.execute("SELECT COUNT(*) AS c FROM tenant_crawl_cooldown").fetchone()["c"]
    assert count == 1
    assert second >= first


def test_record_monitor_success_does_not_touch_existing_platform_row(tmp_db):
    tmp_db.execute(
        """
        INSERT INTO tenant_crawl_cooldown (tenant_id, scope, last_success_at, updated_at)
        VALUES (5, 'platform', '2026-01-01 00:00:00', '2026-01-01 00:00:00')
        """
    )
    tmp_db.commit()

    record_monitor_crawl_success(tmp_db, 5, "mt_abc")

    rows = {
        row["scope"]: row["last_success_at"]
        for row in tmp_db.execute(
            "SELECT scope, last_success_at FROM tenant_crawl_cooldown"
        ).fetchall()
    }
    assert rows["platform"] == "2026-01-01 00:00:00"
    assert "monitor:mt_abc" in rows
