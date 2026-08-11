package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(23)
public class V23TemuCrawlRetryMigration {
    private static final Logger log = LoggerFactory.getLogger(V23TemuCrawlRetryMigration.class);

    private final JdbcTemplate jdbc;

    public V23TemuCrawlRetryMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        addColumnIfMissing("temu_crawl_job", "retry_count", "INTEGER NOT NULL DEFAULT 0");
        addColumnIfMissing("temu_crawl_job", "max_retry_count", "INTEGER NOT NULL DEFAULT 8");
        addColumnIfMissing("temu_crawl_job", "next_retry_at", "TEXT NOT NULL DEFAULT ''");
        addColumnIfMissing("temu_crawl_job", "retry_exhausted", "INTEGER NOT NULL DEFAULT 0");
        log.info("V23TemuCrawlRetryMigration applied");
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
