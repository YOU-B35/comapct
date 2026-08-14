package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(31)
public class V31DouyinOpportunityMigration {
    private static final Logger log = LoggerFactory.getLogger(V31DouyinOpportunityMigration.class);

    private final JdbcTemplate jdbc;

    public V31DouyinOpportunityMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS douyin_opportunity_product (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  category_key TEXT NOT NULL,
                  category_id TEXT,
                  category_name TEXT,
                  category_query TEXT,
                  is_default_category INTEGER NOT NULL DEFAULT 1,
                  rank_no INTEGER NOT NULL DEFAULT 0,
                  clue_id TEXT NOT NULL,
                  product_name TEXT,
                  main_image TEXT,
                  category_path TEXT,
                  price_min REAL,
                  price_max REAL,
                  search_heat REAL,
                  search_pv_range TEXT,
                  pay_growth_rate REAL,
                  pay_amt_range TEXT,
                  labels_json TEXT,
                  overview_json TEXT,
                  raw_json TEXT,
                  source_url TEXT,
                  synced_at TEXT,
                  created_at TEXT,
                  updated_at TEXT
                )
                """);
        jdbc.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uk_douyin_opp_product
                ON douyin_opportunity_product(tenant_id, store_id, category_key, clue_id)
                """);
        jdbc.execute("""
                CREATE INDEX IF NOT EXISTS idx_douyin_opp_tenant_store_cat
                ON douyin_opportunity_product(tenant_id, store_id, category_key, rank_no)
                """);
        log.info("V31 douyin_opportunity_product migration applied");
    }
}
