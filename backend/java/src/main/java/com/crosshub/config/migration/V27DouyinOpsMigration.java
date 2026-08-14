package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(27)
public class V27DouyinOpsMigration {
    private static final Logger log = LoggerFactory.getLogger(V27DouyinOpsMigration.class);

    private final JdbcTemplate jdbc;

    public V27DouyinOpsMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS douyin_order (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  external_shop_id TEXT,
                  report_day TEXT NOT NULL,
                  order_no TEXT NOT NULL,
                  product_name TEXT,
                  channel TEXT,
                  sku TEXT,
                  quantity INTEGER DEFAULT 1,
                  amount REAL,
                  currency TEXT DEFAULT 'CNY',
                  status TEXT,
                  ship_deadline TEXT,
                  ordered_at TEXT,
                  order_key TEXT NOT NULL,
                  raw_json TEXT,
                  created_at TEXT,
                  updated_at TEXT
                )
                """);
        jdbc.execute("CREATE UNIQUE INDEX IF NOT EXISTS uk_douyin_order_key ON douyin_order(order_key)");
        jdbc.execute(
                "CREATE INDEX IF NOT EXISTS idx_douyin_order_day ON douyin_order(tenant_id, store_id, report_day)"
        );

        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS douyin_issue (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  type TEXT,
                  type_label TEXT,
                  sku TEXT,
                  product_name TEXT,
                  detail TEXT,
                  priority TEXT,
                  resolved INTEGER DEFAULT 0,
                  reported_at TEXT,
                  resolved_at TEXT,
                  note TEXT,
                  external_id TEXT,
                  source TEXT,
                  created_at TEXT,
                  updated_at TEXT
                )
                """);
        jdbc.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uk_douyin_issue ON douyin_issue(tenant_id, store_id, external_id)"
        );

        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS douyin_sync_job (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  scope TEXT NOT NULL,
                  status TEXT NOT NULL,
                  store_id TEXT,
                  agent_task_id TEXT,
                  orders_count INTEGER DEFAULT 0,
                  issues_count INTEGER DEFAULT 0,
                  error_code TEXT,
                  error_message TEXT,
                  message TEXT,
                  created_at TEXT,
                  updated_at TEXT,
                  finished_at TEXT
                )
                """);
        jdbc.execute(
                "CREATE INDEX IF NOT EXISTS idx_douyin_sync_job_tenant ON douyin_sync_job(tenant_id, created_at)"
        );

        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS douyin_session_snapshot (
                  tenant_id INTEGER PRIMARY KEY,
                  payload_json TEXT NOT NULL,
                  updated_at TEXT
                )
                """);

        log.info("V27DouyinOpsMigration applied");
    }
}
