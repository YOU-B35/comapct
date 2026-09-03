package com.crosshub.config.migration;

import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(82)
public class V82ZiniaoCliStoreMigration {
    private final JdbcTemplate jdbc;

    public V82ZiniaoCliStoreMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        try {
            jdbc.execute("ALTER TABLE platform_account ADD COLUMN ziniao_cli_store_id TEXT NOT NULL DEFAULT ''");
        } catch (Exception ignored) {
            // The column already exists on upgraded installations.
        }
    }
}
