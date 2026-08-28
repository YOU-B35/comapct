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

/** 拼多多订单/商品查询性能索引：覆盖 listOrders 日期+状态过滤与排序、商品按店铺查询。 */
@Component
@Order(73)
public class V73PddOrderIndexMigration {
    private static final Logger log = LoggerFactory.getLogger(V73PddOrderIndexMigration.class);

    private final JdbcTemplate jdbc;

    public V73PddOrderIndexMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        // 订单：覆盖 listOrders 主查询（tenant + 日期范围 + 状态过滤）
        jdbc.execute("CREATE INDEX IF NOT EXISTS idx_pdd_order_tenant_day_status ON pdd_order(tenant_id, report_day, status)");
        // 订单：覆盖排序字段（paid_at 降序）
        jdbc.execute("CREATE INDEX IF NOT EXISTS idx_pdd_order_tenant_paid ON pdd_order(tenant_id, paid_at)");
        // 商品：覆盖 listProducts 查询（tenant + store）
        jdbc.execute("CREATE INDEX IF NOT EXISTS idx_pdd_product_tenant_store ON pdd_product(tenant_id, store_id)");
        log.info("V73 pdd order/product indexes applied");
    }
}
