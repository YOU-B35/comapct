"""Shared monitor schema helpers for the Java/Python competitor monitor flow."""
from __future__ import annotations

import sqlite3


MONITOR_SCHEMA = """
CREATE TABLE IF NOT EXISTS monitor_target (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  platform TEXT NOT NULL,
  target_type TEXT NOT NULL,
  label TEXT NOT NULL,
  target_url TEXT NOT NULL,
  host TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active',
  crawl_strategy TEXT NOT NULL DEFAULT '',
  freshness_minutes INTEGER NOT NULL DEFAULT 1440,
  config_json TEXT NOT NULL DEFAULT '',
  latest_snapshot_id TEXT,
  latest_snapshot_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_monitor_target_tenant_platform_status
ON monitor_target (tenant_id, platform, status);

CREATE TABLE IF NOT EXISTS monitor_schedule (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  target_id TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  schedule_type TEXT NOT NULL DEFAULT 'interval',
  cron_expr TEXT NOT NULL DEFAULT '',
  interval_minutes INTEGER NOT NULL DEFAULT 1440,
  next_run_at TEXT,
  last_run_at TEXT,
  max_products INTEGER NOT NULL DEFAULT 100,
  retry_limit INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_monitor_schedule_target
ON monitor_schedule (tenant_id, target_id);

CREATE TABLE IF NOT EXISTS monitor_job (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  target_id TEXT NOT NULL,
  schedule_id TEXT,
  platform TEXT NOT NULL,
  trigger_type TEXT NOT NULL,
  force INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  attempt_no INTEGER NOT NULL DEFAULT 1,
  queued_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  worker_id TEXT,
  error_code TEXT,
  error_message TEXT,
  error_detail TEXT,
  snapshot_id TEXT,
  created_by INTEGER,
  reason TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_monitor_job_status_queued
ON monitor_job (tenant_id, status, queued_at DESC);
CREATE INDEX IF NOT EXISTS idx_monitor_job_target_created
ON monitor_job (tenant_id, target_id, queued_at DESC);
"""


MONITOR_RESULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS monitor_snapshot (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  target_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  snapshot_at TEXT NOT NULL,
  product_count INTEGER NOT NULL DEFAULT 0,
  recent_launch_count INTEGER NOT NULL DEFAULT 0,
  sales_outlier_count INTEGER NOT NULL DEFAULT 0,
  report_md_path TEXT NOT NULL DEFAULT '',
  report_xlsx_path TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_monitor_snapshot_target_time
ON monitor_snapshot (tenant_id, target_id, snapshot_at DESC);

CREATE TABLE IF NOT EXISTS monitor_product_snapshot (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  snapshot_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  product_name TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT '',
  price REAL NOT NULL DEFAULT 0,
  daily_sales INTEGER NOT NULL DEFAULT 0,
  total_sales INTEGER NOT NULL DEFAULT 0,
  listed_at TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL DEFAULT '',
  image_url TEXT NOT NULL DEFAULT '',
  shop_name TEXT NOT NULL DEFAULT '',
  shop_url TEXT NOT NULL DEFAULT '',
  rank INTEGER NOT NULL DEFAULT 0,
  price_range TEXT NOT NULL DEFAULT '',
  sale_text TEXT NOT NULL DEFAULT '',
  dropship_7d TEXT NOT NULL DEFAULT '',
  dropship_30d TEXT NOT NULL DEFAULT '',
  dropship_heat INTEGER NOT NULL DEFAULT 0,
  rebuy_rate TEXT NOT NULL DEFAULT '',
  shop_return_rate TEXT NOT NULL DEFAULT '',
  quality_rate TEXT NOT NULL DEFAULT '',
  shop_fans INTEGER NOT NULL DEFAULT 0,
  attrs_json TEXT NOT NULL DEFAULT '',
  is_pinned INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT '',
  expired INTEGER NOT NULL DEFAULT 0,
  suspicious INTEGER NOT NULL DEFAULT 0,
  raw_json TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_monitor_product_snapshot_unique
ON monitor_product_snapshot (tenant_id, snapshot_id, product_id);
CREATE INDEX IF NOT EXISTS idx_monitor_product_snapshot_target_product
ON monitor_product_snapshot (tenant_id, target_id, product_id);

CREATE TABLE IF NOT EXISTS monitor_signal (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  snapshot_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  signal_type TEXT NOT NULL,
  signal_score REAL NOT NULL DEFAULT 0,
  signal_value TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_monitor_signal_snapshot_type
ON monitor_signal (tenant_id, snapshot_id, signal_type);

CREATE TABLE IF NOT EXISTS tenant_crawl_cooldown (
  tenant_id INTEGER NOT NULL,
  scope TEXT NOT NULL DEFAULT 'platform',
  last_success_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (tenant_id, scope)
);

CREATE TABLE IF NOT EXISTS ingest_batch (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  platform TEXT NOT NULL,
  report_day TEXT,
  scope TEXT,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  detail_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_ingest_batch_tenant_platform_time
ON ingest_batch (tenant_id, platform, started_at DESC);
"""


def init_monitor_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(MONITOR_SCHEMA)
    conn.commit()


def init_monitor_result_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(MONITOR_RESULT_SCHEMA)
    conn.commit()
