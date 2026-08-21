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
@Order(45)
public class V45Alibaba1688MonitorMigration {
    private static final Logger log = LoggerFactory.getLogger(V45Alibaba1688MonitorMigration.class);

    private final JdbcTemplate jdbc;

    public V45Alibaba1688MonitorMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        addColumnIfMissing("monitor_product_snapshot", "shop_name", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "shop_url", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "rank", "INTEGER DEFAULT 0");
        addColumnIfMissing("monitor_product_snapshot", "price_range", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "sale_text", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "dropship_7d", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "dropship_30d", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "dropship_heat", "INTEGER DEFAULT 0");
        addColumnIfMissing("monitor_product_snapshot", "rebuy_rate", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "shop_return_rate", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "quality_rate", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "shop_fans", "INTEGER DEFAULT 0");
        addColumnIfMissing("monitor_product_snapshot", "attrs_json", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "is_pinned", "INTEGER DEFAULT 0");
        addColumnIfMissing("monitor_product_snapshot", "status", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "expired", "INTEGER DEFAULT 0");
        addColumnIfMissing("monitor_product_snapshot", "suspicious", "INTEGER DEFAULT 0");
        addColumnIfMissing("monitor_product_snapshot", "raw_json", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_target", "config_json", "TEXT DEFAULT ''");
        log.info("V45 alibaba1688 monitor migration applied");
    }

    private void addColumnIfMissing(String table, String column, String ddl) {
        List<Map<String, Object>> columns = jdbc.queryForList("PRAGMA table_info(" + table + ")");
        boolean exists = columns.stream()
                .anyMatch(c -> column.equalsIgnoreCase(String.valueOf(c.get("name"))));
        if (!exists) {
            jdbc.execute("ALTER TABLE " + table + " ADD COLUMN " + column + " " + ddl);
        }
    }
}
