package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(16)
public class V16TemuSkuCostMigration {
    private static final Logger log = LoggerFactory.getLogger(V16TemuSkuCostMigration.class);

    private final JdbcTemplate jdbc;

    public V16TemuSkuCostMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS temu_sku_cost (
                  tenant_id INTEGER NOT NULL,
                  ext_code TEXT NOT NULL,
                  cost INTEGER NOT NULL DEFAULT 0,
                  updated_at TEXT NOT NULL DEFAULT '',
                  PRIMARY KEY (tenant_id, ext_code)
                )
                """);
        jdbc.execute("""
                CREATE INDEX IF NOT EXISTS idx_temu_sku_cost_tenant
                ON temu_sku_cost (tenant_id)
                """);
        log.info("V16 temu_sku_cost migration completed");
    }
}
