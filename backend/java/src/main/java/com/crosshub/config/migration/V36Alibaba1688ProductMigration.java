package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(36)
public class V36Alibaba1688ProductMigration {
    private static final Logger log = LoggerFactory.getLogger(V36Alibaba1688ProductMigration.class);

    private final JdbcTemplate jdbc;

    public V36Alibaba1688ProductMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS alibaba1688_product (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL DEFAULT '',
                  offer_id TEXT NOT NULL DEFAULT '',
                  product_name TEXT DEFAULT '',
                  goods_no TEXT DEFAULT '',
                  quality_score REAL,
                  price TEXT DEFAULT '',
                  stock INTEGER,
                  search_expose_7d INTEGER,
                  visitor_30d INTEGER,
                  gmv_30d TEXT DEFAULT '',
                  product_updated_at TEXT DEFAULT '',
                  status TEXT DEFAULT '',
                  tag_potential INTEGER NOT NULL DEFAULT 0,
                  tag_yanxuan INTEGER NOT NULL DEFAULT 0,
                  tag_underperform INTEGER NOT NULL DEFAULT 0,
                  index_score TEXT DEFAULT '',
                  raw_json TEXT DEFAULT '',
                  synced_at TEXT DEFAULT '',
                  created_at TEXT DEFAULT '',
                  updated_at TEXT DEFAULT ''
                )
                """);
        jdbc.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uk_a1688_product_offer
                ON alibaba1688_product(tenant_id, store_id, offer_id)
                """);
        jdbc.execute("""
                CREATE INDEX IF NOT EXISTS idx_a1688_product_tenant_status
                ON alibaba1688_product(tenant_id, status)
                """);
        log.info("V36 alibaba1688_product migration applied");
    }
}
