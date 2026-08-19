package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(39)
public class V39Alibaba1688ProductCategoryMigration {
    private static final Logger log = LoggerFactory.getLogger(V39Alibaba1688ProductCategoryMigration.class);

    private final JdbcTemplate jdbc;

    public V39Alibaba1688ProductCategoryMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS alibaba1688_product_category (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  offer_id TEXT NOT NULL,
                  category_code TEXT NOT NULL,
                  source_sync_id TEXT,
                  synced_at TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE (tenant_id, store_id, offer_id, category_code)
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS alibaba1688_product_category_sync (
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  category_code TEXT NOT NULL,
                  status TEXT NOT NULL,
                  error_code TEXT DEFAULT '',
                  error_message TEXT DEFAULT '',
                  source_sync_id TEXT DEFAULT '',
                  synced_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  PRIMARY KEY (tenant_id, store_id, category_code)
                )
                """);
        jdbc.execute("""
                CREATE INDEX IF NOT EXISTS idx_a1688_product_category_lookup
                ON alibaba1688_product_category(tenant_id, store_id, category_code, offer_id)
                """);
        log.info("V39 alibaba1688_product_category migration applied");
    }
}