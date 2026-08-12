package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(21)
public class V21AssignedTaskNudgeMigration {
    private static final Logger log = LoggerFactory.getLogger(V21AssignedTaskNudgeMigration.class);

    private final JdbcTemplate jdbc;

    public V21AssignedTaskNudgeMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        addColumnIfMissing("assigned_task", "nudged_at", "TEXT NOT NULL DEFAULT ''");
        addColumnIfMissing("assigned_task", "nudged_by", "TEXT NOT NULL DEFAULT ''");
        log.info("V21AssignedTaskNudgeMigration applied");
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
