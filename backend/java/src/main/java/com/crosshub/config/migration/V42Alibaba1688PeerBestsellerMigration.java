package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(42)
public class V42Alibaba1688PeerBestsellerMigration {
    private static final Logger log = LoggerFactory.getLogger(V42Alibaba1688PeerBestsellerMigration.class);

    private final JdbcTemplate jdbc;

    public V42Alibaba1688PeerBestsellerMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS alibaba1688_peer_bestseller (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  offer_id TEXT NOT NULL,
                  shop_name TEXT DEFAULT '',
                  title TEXT DEFAULT '',
                  price TEXT DEFAULT '',
                  sales INTEGER NOT NULL DEFAULT 0,
                  sale_text TEXT DEFAULT '',
                  offer_url TEXT DEFAULT '',
                  image_url TEXT DEFAULT '',
                  suggestion TEXT DEFAULT '',
                  synced_at TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """);
        log.info("V42 alibaba1688_peer_bestseller migration applied");
    }
}
