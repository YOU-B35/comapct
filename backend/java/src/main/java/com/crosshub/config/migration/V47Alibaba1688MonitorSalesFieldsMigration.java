package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

@Component
@Order(47)
public class V47Alibaba1688MonitorSalesFieldsMigration {
    private static final Logger log = LoggerFactory.getLogger(V47Alibaba1688MonitorSalesFieldsMigration.class);

    private final JdbcTemplate jdbc;

    public V47Alibaba1688MonitorSalesFieldsMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        addColumnIfMissing("moq", "TEXT DEFAULT ''");
        addColumnIfMissing("good_rate", "TEXT DEFAULT ''");
        addColumnIfMissing("delivery_48h_rate", "TEXT DEFAULT ''");
        log.info("V47 alibaba1688 monitor sales-fields migration applied");
    }

    private void addColumnIfMissing(String column, String ddl) {
        List<Map<String, Object>> columns = jdbc.queryForList("PRAGMA table_info(monitor_product_snapshot)");
        boolean exists = columns.stream()
                .anyMatch(c -> column.equalsIgnoreCase(String.valueOf(c.get("name"))));
        if (!exists) {
            jdbc.execute("ALTER TABLE monitor_product_snapshot ADD COLUMN " + column + " " + ddl);
        }
    }
}
