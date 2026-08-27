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

/** 拼多多会话快照改为按 (tenant_id, store_id) 隔离，使店铺切换时登录态各店独立（对齐 1688）。 */
@Component
@Order(72)
public class V72PddMultiStoreSessionMigration {
    private static final Logger log = LoggerFactory.getLogger(V72PddMultiStoreSessionMigration.class);

    private final JdbcTemplate jdbc;

    public V72PddMultiStoreSessionMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        List<Map<String, Object>> columns = jdbc.queryForList("PRAGMA table_info(pdd_session_snapshot)");
        boolean hasStoreId = columns.stream()
                .anyMatch(c -> "store_id".equalsIgnoreCase(String.valueOf(c.get("name"))));
        if (hasStoreId) {
            log.info("V72 pdd session-store migration already applied");
            return;
        }
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS pdd_session_snapshot_v72 (
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL DEFAULT 'default',
                  payload_json TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  PRIMARY KEY (tenant_id, store_id)
                )
                """);
        jdbc.update("""
                INSERT OR IGNORE INTO pdd_session_snapshot_v72 (tenant_id, store_id, payload_json, updated_at)
                SELECT tenant_id, 'default', payload_json, updated_at FROM pdd_session_snapshot
                """);
        jdbc.execute("DROP TABLE pdd_session_snapshot");
        jdbc.execute("ALTER TABLE pdd_session_snapshot_v72 RENAME TO pdd_session_snapshot");
        log.info("V72 pdd session-store migration applied");
    }
}
