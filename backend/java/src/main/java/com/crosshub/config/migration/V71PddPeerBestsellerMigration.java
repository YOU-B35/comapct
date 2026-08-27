package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(71)
public class V71PddPeerBestsellerMigration {
    private static final Logger log = LoggerFactory.getLogger(V71PddPeerBestsellerMigration.class);

    private final JdbcTemplate jdbc;

    public V71PddPeerBestsellerMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS pdd_peer_bestseller (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  product_id TEXT NOT NULL,
                  shop_name TEXT,
                  title TEXT,
                  price REAL,
                  sales INTEGER DEFAULT 0,
                  sale_text TEXT,
                  offer_url TEXT,
                  image_url TEXT,
                  quality_score TEXT,
                  suggestion TEXT,
                  synced_at TEXT,
                  created_at TEXT,
                  updated_at TEXT
                )
                """);
        jdbc.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uk_pdd_peer_bestseller_product "
                        + "ON pdd_peer_bestseller(tenant_id, store_id, product_id)"
        );
        jdbc.execute(
                "CREATE INDEX IF NOT EXISTS idx_pdd_peer_bestseller_store_sales "
                        + "ON pdd_peer_bestseller(tenant_id, store_id, sales)"
        );
        log.info("V71PddPeerBestsellerMigration applied");
    }
}
