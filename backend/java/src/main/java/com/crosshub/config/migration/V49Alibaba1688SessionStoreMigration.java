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

/** 1688 会话快照改为按 (tenant_id, store_id) 隔离，使店铺切换时登录态各店独立。 */
@Component
@Order(49)
public class V49Alibaba1688SessionStoreMigration {
    private static final Logger log = LoggerFactory.getLogger(V49Alibaba1688SessionStoreMigration.class);

    private final JdbcTemplate jdbc;

    public V49Alibaba1688SessionStoreMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        List<Map<String, Object>> columns = jdbc.queryForList("PRAGMA table_info(alibaba1688_session_snapshot)");
        boolean hasStoreId = columns.stream()
                .anyMatch(c -> "store_id".equalsIgnoreCase(String.valueOf(c.get("name"))));
        if (hasStoreId) {
            log.info("V49 alibaba1688 session-store migration already applied");
            return;
        }
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS alibaba1688_session_snapshot_v49 (
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL DEFAULT 'default',
                  payload_json TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  PRIMARY KEY (tenant_id, store_id)
                )
                """);
        jdbc.update("""
                INSERT OR IGNORE INTO alibaba1688_session_snapshot_v49 (tenant_id, store_id, payload_json, updated_at)
                SELECT tenant_id, 'default', payload_json, updated_at FROM alibaba1688_session_snapshot
                """);
        jdbc.execute("DROP TABLE alibaba1688_session_snapshot");
        jdbc.execute("ALTER TABLE alibaba1688_session_snapshot_v49 RENAME TO alibaba1688_session_snapshot");
        log.info("V49 alibaba1688 session-store migration applied");
    }
}
