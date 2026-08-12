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
@Order(20)
public class V20OpsTeamMigration {
    private static final Logger log = LoggerFactory.getLogger(V20OpsTeamMigration.class);

    private final JdbcTemplate jdbc;

    public V20OpsTeamMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS ops_team (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  tenant_id INTEGER NOT NULL,
                  name TEXT NOT NULL DEFAULT '',
                  leader_user_id INTEGER NOT NULL,
                  status TEXT NOT NULL DEFAULT 'active',
                  created_by INTEGER,
                  created_at TEXT NOT NULL DEFAULT '',
                  updated_at TEXT NOT NULL DEFAULT ''
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS ops_team_member (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  tenant_id INTEGER NOT NULL,
                  team_id INTEGER NOT NULL,
                  user_id INTEGER NOT NULL,
                  joined_at TEXT NOT NULL DEFAULT '',
                  added_by INTEGER
                )
                """);
        jdbc.execute("CREATE INDEX IF NOT EXISTS idx_ops_team_tenant ON ops_team(tenant_id)");
        jdbc.execute("CREATE INDEX IF NOT EXISTS idx_ops_team_leader ON ops_team(tenant_id, leader_user_id, status)");
        jdbc.execute("CREATE INDEX IF NOT EXISTS idx_ops_team_member_team ON ops_team_member(team_id)");
        jdbc.execute("CREATE UNIQUE INDEX IF NOT EXISTS uk_ops_team_member_user ON ops_team_member(user_id)");

        seedMenus();
        seedTenantFeatures();
        log.info("V20OpsTeamMigration applied");
    }

    private void seedMenus() {
        Object[][] rows = {
                {"boss.ops_teams", "boss.settings", "boss", null, "/boss/ops-teams", "运营小组", "admin", 121},
                {"employee.ops_team", null, "employee", null, "/employee/ops-team", "我的小组", "module", 86},
                {"employee.team_tasks", null, "employee", null, "/employee/team-tasks", "任务分配", "module", 87},
                {"employee.team_binding", null, "employee", null, "/employee/team-binding", "运营绑定", "module", 88},
        };
        for (Object[] row : rows) {
            jdbc.update("""
                    INSERT OR REPLACE INTO sys_menu
                    (code, parent_code, portal, platform, path, label, menu_type, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, row);
        }
        // keep boss.employees sort after ops_teams
        jdbc.update("UPDATE sys_menu SET sort_order = 122 WHERE code = 'boss.employees'");
        jdbc.update("UPDATE sys_menu SET sort_order = 123 WHERE code = 'boss.warehouse_sites'");
        jdbc.update("UPDATE sys_menu SET sort_order = 124 WHERE code = 'boss.warehouse_staff'");
        jdbc.update("UPDATE sys_menu SET sort_order = 125 WHERE code = 'boss.accounts'");
        jdbc.update("UPDATE sys_menu SET sort_order = 126 WHERE code = 'boss.features'");
    }

    private void seedTenantFeatures() {
        List<String> codes = List.of(
                "boss.ops_teams",
                "employee.ops_team",
                "employee.team_tasks",
                "employee.team_binding"
        );
        List<Long> tenantIds = jdbc.query("SELECT id FROM tenant", (rs, i) -> rs.getLong(1));
        if (tenantIds.isEmpty()) {
            tenantIds = List.of(1L);
        }
        for (Long tenantId : tenantIds) {
            for (String code : codes) {
                jdbc.update("""
                        INSERT OR IGNORE INTO tenant_feature (tenant_id, feature_code, enabled)
                        VALUES (?, ?, 1)
                        """, tenantId, code);
            }
        }
    }
}
