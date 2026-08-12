package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
@Order(22)
public class V22CommanderAutoUploadMenuMigration {
    private static final Logger log = LoggerFactory.getLogger(V22CommanderAutoUploadMenuMigration.class);

    private final JdbcTemplate jdbc;

    public V22CommanderAutoUploadMenuMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        upsertMenu("boss.auto_upload", null, "boss", null, "/boss/auto-upload", "自动上货", "admin", 19);
        upsertMenu("employee.auto_upload", null, "employee", null, "/employee/auto-upload", "自动上货", "base", 96);
        enableForAllTenants("boss.auto_upload");
        enableForAllTenants("employee.auto_upload");
        // New + existing tenants: keep auto-upload on so BFF 代登对所有账号可用
        forceEnable("boss.auto_upload");
        forceEnable("employee.auto_upload");
        log.info("V22CommanderAutoUploadMenuMigration applied");
    }

    private void forceEnable(String featureCode) {
        jdbc.update(
                "UPDATE tenant_feature SET enabled = 1 WHERE feature_code = ?",
                featureCode
        );
    }

    private void upsertMenu(
            String code,
            String parent,
            String portal,
            String platform,
            String path,
            String label,
            String type,
            int sort
    ) {
        jdbc.update("""
                INSERT OR REPLACE INTO sys_menu
                (code, parent_code, portal, platform, path, label, menu_type, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, code, parent, portal, platform, path, label, type, sort);
    }

    private void enableForAllTenants(String featureCode) {
        List<Long> tenantIds = jdbc.query("SELECT id FROM tenant", (rs, i) -> rs.getLong(1));
        if (tenantIds.isEmpty()) {
            tenantIds = List.of(1L);
        }
        for (Long tenantId : tenantIds) {
            jdbc.update("""
                    INSERT OR IGNORE INTO tenant_feature (tenant_id, feature_code, enabled)
                    VALUES (?, ?, 1)
                    """, tenantId, featureCode);
        }
    }
}
