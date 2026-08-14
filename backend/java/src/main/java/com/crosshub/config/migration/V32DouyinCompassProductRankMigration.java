package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(32)
public class V32DouyinCompassProductRankMigration {
    private static final Logger log = LoggerFactory.getLogger(V32DouyinCompassProductRankMigration.class);

    private final JdbcTemplate jdbc;

    public V32DouyinCompassProductRankMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS douyin_compass_product_rank (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  board TEXT NOT NULL,
                  date_window TEXT NOT NULL,
                  report_day TEXT,
                  rank_no INTEGER NOT NULL DEFAULT 0,
                  product_id TEXT NOT NULL,
                  product_name TEXT,
                  main_image TEXT,
                  category_path TEXT,
                  shop_name TEXT,
                  pay_amt REAL,
                  click_cnt REAL,
                  pay_cnt REAL,
                  click_pay_cvr REAL,
                  show_cnt REAL,
                  order_cnt REAL,
                  deal_cnt REAL,
                  is_default_category INTEGER NOT NULL DEFAULT 1,
                  category_id TEXT,
                  category_name TEXT,
                  source_url TEXT,
                  raw_json TEXT,
                  synced_at TEXT,
                  created_at TEXT,
                  updated_at TEXT
                )
                """);
        jdbc.execute("""
                CREATE INDEX IF NOT EXISTS idx_dy_cpr_lookup
                ON douyin_compass_product_rank(tenant_id, store_id, board, date_window, rank_no)
                """);
        jdbc.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uk_dy_cpr_product
                ON douyin_compass_product_rank(tenant_id, store_id, board, date_window, product_id)
                """);
        log.info("V32 douyin_compass_product_rank migration applied");
    }
}
