package com.crosshub.config.migration;

import com.crosshub.alibaba1688.service.Alibaba1688StoreKeyResolver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/**
 * 修复历史 1688 订单 store_id 为 'default' 的问题：
 * 把默认会话对应的订单迁移到平台账号 UUID，使店铺切换时数据可见。
 */
@Component
@Order(48)
public class V48Alibaba1688OrderStoreDefaultMigration {
    private static final Logger log = LoggerFactory.getLogger(V48Alibaba1688OrderStoreDefaultMigration.class);

    private final JdbcTemplate jdbc;
    private final Alibaba1688StoreKeyResolver storeKeyResolver;

    public V48Alibaba1688OrderStoreDefaultMigration(JdbcTemplate jdbc, Alibaba1688StoreKeyResolver storeKeyResolver) {
        this.jdbc = jdbc;
        this.storeKeyResolver = storeKeyResolver;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        List<Map<String, Object>> tenants = jdbc.queryForList(
                "SELECT DISTINCT tenant_id FROM alibaba1688_order WHERE store_id = 'default'"
        );
        int totalOrders = 0;
        int totalItems = 0;
        for (Map<String, Object> row : tenants) {
            Long tenantId = toLong(row.get("tenant_id"));
            String defaultAccountId = storeKeyResolver.resolveDefaultAccountId(tenantId);
            if (defaultAccountId == null || defaultAccountId.isBlank()) {
                log.info("[V48] tenant {} skipped: no resolvable default 1688 account", tenantId);
                continue;
            }
            int orders = jdbc.update(
                    "UPDATE alibaba1688_order SET store_id = ? WHERE tenant_id = ? AND store_id = 'default'",
                    defaultAccountId, tenantId
            );
            int items = jdbc.update(
                    "UPDATE alibaba1688_order_item SET store_id = ? WHERE tenant_id = ? AND store_id = 'default'",
                    defaultAccountId, tenantId
            );
            totalOrders += orders;
            totalItems += items;
            log.info("[V48] tenant {} migrated {} orders / {} items to store_id={}", tenantId, orders, items, defaultAccountId);
        }
        log.info("V48 alibaba1688 order-store migration applied (orders={}, items={})", totalOrders, totalItems);
    }

    private Long toLong(Object value) {
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (Exception ex) {
            return 0L;
        }
    }
}
