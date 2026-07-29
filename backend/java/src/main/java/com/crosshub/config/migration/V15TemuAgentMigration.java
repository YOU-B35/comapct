package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(15)
public class V15TemuAgentMigration {
    private static final Logger log = LoggerFactory.getLogger(V15TemuAgentMigration.class);

    private final JdbcTemplate jdbc;

    public V15TemuAgentMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        addColumnIfMissing("temu_crawl_job", "agent_task_id", "TEXT NOT NULL DEFAULT ''");
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS temu_session_snapshot (
                  tenant_id INTEGER PRIMARY KEY,
                  payload_json TEXT NOT NULL DEFAULT '{}',
                  updated_at TEXT NOT NULL DEFAULT ''
                )
                """);
        log.info("V15 temu agent migration completed");
    }

    private void addColumnIfMissing(String table, String column, String definition) {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM pragma_table_info(?) WHERE name = ?",
                Integer.class,
                table,
                column
        );
        if (count != null && count > 0) {
            return;
        }
        jdbc.execute("ALTER TABLE " + table + " ADD COLUMN " + column + " " + definition);
    }
}
