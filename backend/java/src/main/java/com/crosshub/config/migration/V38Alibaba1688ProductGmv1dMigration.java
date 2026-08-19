package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(38)
public class V38Alibaba1688ProductGmv1dMigration {
    private static final Logger log = LoggerFactory.getLogger(V38Alibaba1688ProductGmv1dMigration.class);

    private final JdbcTemplate jdbc;

    public V38Alibaba1688ProductGmv1dMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        addColumnIfMissing("alibaba1688_product", "gmv_1d", "TEXT DEFAULT ''");
        log.info("V38 alibaba1688_product.gmv_1d migration applied");
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
