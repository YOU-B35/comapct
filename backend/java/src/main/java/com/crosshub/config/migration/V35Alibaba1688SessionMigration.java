package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(35)
public class V35Alibaba1688SessionMigration {
    private static final Logger log = LoggerFactory.getLogger(V35Alibaba1688SessionMigration.class);

    private final JdbcTemplate jdbc;

    public V35Alibaba1688SessionMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS alibaba1688_session_snapshot (
                  tenant_id INTEGER PRIMARY KEY,
                  payload_json TEXT NOT NULL,
                  updated_at TEXT
                )
                """);
        log.info("V35 alibaba1688_session_snapshot migration applied");
    }
}
