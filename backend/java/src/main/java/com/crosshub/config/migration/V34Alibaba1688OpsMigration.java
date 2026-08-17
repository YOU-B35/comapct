package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(34)
public class V34Alibaba1688OpsMigration {
    private static final Logger log = LoggerFactory.getLogger(V34Alibaba1688OpsMigration.class);

    private final JdbcTemplate jdbc;

    public V34Alibaba1688OpsMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS alibaba1688_crawl_job (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT,
                  triggered_by INTEGER NOT NULL,
                  status TEXT NOT NULL,
                  job_type TEXT NOT NULL,
                  progress INTEGER DEFAULT 0,
                  message TEXT,
                  error_code TEXT,
                  error_message TEXT,
                  rows_count INTEGER DEFAULT 0,
                  started_at TEXT,
                  finished_at TEXT,
                  created_at TEXT NOT NULL
                )
                """);
        jdbc.execute(
                "CREATE INDEX IF NOT EXISTS idx_a1688_job_tenant ON alibaba1688_crawl_job(tenant_id, created_at)"
        );

        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS alibaba1688_purchase_order (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  order_no TEXT NOT NULL,
                  status TEXT,
                  pay_status TEXT,
                  ship_status TEXT,
                  product_name TEXT,
                  sku TEXT,
                  supplier_name TEXT,
                  supplier_id TEXT,
                  quantity INTEGER,
                  unit_price REAL,
                  amount REAL,
                  currency TEXT DEFAULT 'CNY',
                  linked_platform TEXT,
                  expected_arrival_at TEXT,
                  expected_ship_at TEXT,
                  actual_ship_at TEXT,
                  logistics_status TEXT,
                  logistics_no TEXT,
                  is_delayed INTEGER DEFAULT 0,
                  is_stockout INTEGER DEFAULT 0,
                  raw_json TEXT,
                  synced_at TEXT,
                  created_at TEXT,
                  updated_at TEXT
                )
                """);
        jdbc.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uk_a1688_po ON alibaba1688_purchase_order(tenant_id, store_id, order_no)"
        );

        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS alibaba1688_supplier_alert (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  type TEXT NOT NULL,
                  supplier_name TEXT,
                  related_order_no TEXT,
                  level TEXT,
                  message TEXT,
                  is_open INTEGER DEFAULT 1,
                  created_at TEXT,
                  resolved_at TEXT,
                  updated_at TEXT
                )
                """);
        jdbc.execute(
                "CREATE INDEX IF NOT EXISTS idx_a1688_alert_open ON alibaba1688_supplier_alert(tenant_id, is_open)"
        );

        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS alibaba1688_supplier_stat (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  supplier_key TEXT NOT NULL,
                  supplier_name TEXT,
                  order_count INTEGER DEFAULT 0,
                  total_amount REAL DEFAULT 0,
                  on_time_rate REAL DEFAULT 0,
                  last_order_at TEXT,
                  window_days INTEGER DEFAULT 90,
                  updated_at TEXT
                )
                """);
        jdbc.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uk_a1688_stat ON alibaba1688_supplier_stat(tenant_id, store_id, supplier_key, window_days)"
        );

        log.info("V34Alibaba1688OpsMigration applied");
    }
}
