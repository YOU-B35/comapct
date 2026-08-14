package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(30)
public class V30DouyinCompassMigration {
    private static final Logger log = LoggerFactory.getLogger(V30DouyinCompassMigration.class);

    private final JdbcTemplate jdbc;

    public V30DouyinCompassMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS douyin_compass_snapshot (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  report_day TEXT NOT NULL,
                  date_type INTEGER NOT NULL DEFAULT 1,
                  shop_name TEXT,
                  pay_amt REAL,
                  pay_cnt REAL,
                  pay_ucnt REAL,
                  income_amt REAL,
                  per_usr_pay_amt REAL,
                  product_show_ucnt REAL,
                  product_show_cnt REAL,
                  product_click_ucnt REAL,
                  product_click_cnt REAL,
                  show_click_rate REAL,
                  click_pay_rate REAL,
                  settlement_amt REAL,
                  refund_amt REAL,
                  refund_rate REAL,
                  exp_score REAL,
                  exp_product REAL,
                  exp_service REAL,
                  exp_logistics REAL,
                  carrier_json TEXT,
                  metrics_json TEXT,
                  raw_json TEXT,
                  source_url TEXT,
                  synced_at TEXT,
                  created_at TEXT,
                  updated_at TEXT
                )
                """);
        jdbc.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uk_douyin_compass_snap
                ON douyin_compass_snapshot(tenant_id, store_id, report_day, date_type)
                """);
        jdbc.execute("""
                CREATE INDEX IF NOT EXISTS idx_douyin_compass_tenant_day
                ON douyin_compass_snapshot(tenant_id, report_day, date_type)
                """);
        log.info("V30 douyin_compass_snapshot migration applied");
    }
}
