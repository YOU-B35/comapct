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
@Order(46)
public class V46Alibaba1688MonitorImageMigration {
    private static final Logger log = LoggerFactory.getLogger(V46Alibaba1688MonitorImageMigration.class);

    private final JdbcTemplate jdbc;

    public V46Alibaba1688MonitorImageMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        List<Map<String, Object>> columns = jdbc.queryForList("PRAGMA table_info(monitor_product_snapshot)");
        boolean exists = columns.stream()
                .anyMatch(c -> "image_url".equalsIgnoreCase(String.valueOf(c.get("name"))));
        if (!exists) {
            jdbc.execute("ALTER TABLE monitor_product_snapshot ADD COLUMN image_url TEXT DEFAULT ''");
        }
        log.info("V46 alibaba1688 monitor image migration applied");
    }
}
