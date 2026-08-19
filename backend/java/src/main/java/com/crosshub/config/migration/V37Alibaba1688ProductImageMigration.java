package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(37)
public class V37Alibaba1688ProductImageMigration {
    private static final Logger log = LoggerFactory.getLogger(V37Alibaba1688ProductImageMigration.class);

    private final JdbcTemplate jdbc;

    public V37Alibaba1688ProductImageMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        addColumnIfMissing("alibaba1688_product", "image_url", "TEXT DEFAULT ''");
        log.info("V37 alibaba1688_product.image_url migration applied");
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
