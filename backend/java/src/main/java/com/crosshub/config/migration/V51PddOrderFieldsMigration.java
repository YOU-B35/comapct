package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * 为 {@code pdd_order} 补齐经营驾驶舱/订单列表所需字段，对齐 {@code alibaba1688_order}。
 *
 * <p>新增列：{@code paid_amount / refunded_amount / paid_at / refunded_at / buyer_masked /
 * synced_at / unit_price / item_amount / image_url / sku_text}。
 *
 * <p>这些字段为 agent 携带 cookie 抓取订单 XHR 后回写预留，确保用户登录账号拿到数据后
 * 可直接通过 {@code /api/pdd/orders} / {@code /api/pdd/operations/summary|trend|overview} 同步读取。
 */
@Component
@Order(51)
public class V51PddOrderFieldsMigration {
    private static final Logger log = LoggerFactory.getLogger(V51PddOrderFieldsMigration.class);

    private final JdbcTemplate jdbc;

    public V51PddOrderFieldsMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        addColumnIfMissing("pdd_order", "paid_amount", "TEXT NOT NULL DEFAULT '0'");
        addColumnIfMissing("pdd_order", "refunded_amount", "TEXT NOT NULL DEFAULT '0'");
        addColumnIfMissing("pdd_order", "paid_at", "TEXT DEFAULT ''");
        addColumnIfMissing("pdd_order", "refunded_at", "TEXT DEFAULT ''");
        addColumnIfMissing("pdd_order", "buyer_masked", "TEXT DEFAULT ''");
        addColumnIfMissing("pdd_order", "synced_at", "TEXT DEFAULT ''");
        addColumnIfMissing("pdd_order", "unit_price", "TEXT NOT NULL DEFAULT '0'");
        addColumnIfMissing("pdd_order", "item_amount", "TEXT NOT NULL DEFAULT '0'");
        addColumnIfMissing("pdd_order", "image_url", "TEXT DEFAULT ''");
        addColumnIfMissing("pdd_order", "sku_text", "TEXT DEFAULT ''");
        log.info("V51 pdd_order operational fields migration applied");
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
