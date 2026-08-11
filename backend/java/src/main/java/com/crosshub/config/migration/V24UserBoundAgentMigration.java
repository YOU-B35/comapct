package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(24)
public class V24UserBoundAgentMigration {
    private static final Logger log = LoggerFactory.getLogger(V24UserBoundAgentMigration.class);

    private final JdbcTemplate jdbc;

    public V24UserBoundAgentMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        addColumnIfMissing("integration_agent", "bound_user_id", "INTEGER NULL");
        addColumnIfMissing("integration_agent", "machine_fingerprint", "TEXT NOT NULL DEFAULT ''");
        jdbc.execute("CREATE INDEX IF NOT EXISTS idx_agent_bound_user ON integration_agent(bound_user_id)");
        log.info("V24UserBoundAgentMigration applied");
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
