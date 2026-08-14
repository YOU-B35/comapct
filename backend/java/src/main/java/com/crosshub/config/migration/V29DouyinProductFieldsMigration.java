package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(29)
public class V29DouyinProductFieldsMigration {
    private static final Logger log = LoggerFactory.getLogger(V29DouyinProductFieldsMigration.class);

    private final JdbcTemplate jdbc;

    public V29DouyinProductFieldsMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        addColumnIfMissing("douyin_product", "article_no", "TEXT");
        addColumnIfMissing("douyin_product", "quality_score", "REAL");
        addColumnIfMissing("douyin_product", "published_at", "TEXT");
        addColumnIfMissing("douyin_product", "good_rate", "REAL");
        log.info("V29 douyin_product fields migration applied");
    }

    private void addColumnIfMissing(String table, String column, String ddlType) {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(1) FROM pragma_table_info(?) WHERE name = ?",
                Integer.class,
                table,
                column
        );
        if (count != null && count > 0) {
            return;
        }
        jdbc.execute("ALTER TABLE " + table + " ADD COLUMN " + column + " " + ddlType);
    }
}
