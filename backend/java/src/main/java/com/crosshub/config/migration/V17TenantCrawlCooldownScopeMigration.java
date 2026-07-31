package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Locale;

@Component
@Order(17)
public class V17TenantCrawlCooldownScopeMigration {
    private static final Logger log = LoggerFactory.getLogger(V17TenantCrawlCooldownScopeMigration.class);

    private final JdbcTemplate jdbc;

    public V17TenantCrawlCooldownScopeMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        if (!tableExists("tenant_crawl_cooldown")) {
            createScopedTable("tenant_crawl_cooldown");
            log.info("V17TenantCrawlCooldownScopeMigration created scoped table");
            return;
        }
        if (hasScopeColumn()) {
            log.info("V17TenantCrawlCooldownScopeMigration already applied");
            return;
        }

        log.info("Rebuilding tenant_crawl_cooldown with (tenant_id, scope) PK");
        createScopedTable("tenant_crawl_cooldown_v17");
        jdbc.execute("""
                INSERT OR IGNORE INTO tenant_crawl_cooldown_v17 (
                  tenant_id, scope, last_success_at, updated_at
                )
                SELECT tenant_id, 'platform', last_success_at, updated_at
                FROM tenant_crawl_cooldown
                """);
        jdbc.execute("DROP TABLE tenant_crawl_cooldown");
        jdbc.execute("ALTER TABLE tenant_crawl_cooldown_v17 RENAME TO tenant_crawl_cooldown");
        log.info("V17TenantCrawlCooldownScopeMigration completed");
    }

    private boolean tableExists(String table) {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(1) FROM sqlite_master WHERE type = 'table' AND name = ?",
                Integer.class,
                table
        );
        return count != null && count > 0;
    }

    private boolean hasScopeColumn() {
        List<String> cols = jdbc.query(
                "PRAGMA table_info(tenant_crawl_cooldown)",
                (rs, rowNum) -> rs.getString("name").toLowerCase(Locale.ROOT)
        );
        return cols.stream().anyMatch(c -> c.equals("scope"));
    }

    private void createScopedTable(String name) {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS %s (
                  tenant_id INTEGER NOT NULL,
                  scope TEXT NOT NULL DEFAULT 'platform',
                  last_success_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  PRIMARY KEY (tenant_id, scope)
                )
                """.formatted(name));
    }
}
