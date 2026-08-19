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
@Order(41)
public class V41Alibaba1688RetailOrderItemUnitPriceMigration {
    private static final Logger log = LoggerFactory.getLogger(V41Alibaba1688RetailOrderItemUnitPriceMigration.class);

    private final JdbcTemplate jdbc;

    public V41Alibaba1688RetailOrderItemUnitPriceMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        List<Map<String, Object>> columns = jdbc.queryForList("PRAGMA table_info(alibaba1688_order_item)");
        boolean exists = columns.stream()
                .anyMatch(col -> "actual_unit_price".equals(String.valueOf(col.get("name"))));
        if (!exists) {
            jdbc.execute("""
                    ALTER TABLE alibaba1688_order_item
                    ADD COLUMN actual_unit_price TEXT DEFAULT ''
                    """);
            log.info("V41 alibaba1688_order_item.actual_unit_price migration applied");
        } else {
            log.info("V41 alibaba1688_order_item.actual_unit_price already present");
        }
    }
}
