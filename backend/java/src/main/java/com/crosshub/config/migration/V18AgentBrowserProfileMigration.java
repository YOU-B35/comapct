package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(18)
public class V18AgentBrowserProfileMigration {
    private static final Logger log = LoggerFactory.getLogger(V18AgentBrowserProfileMigration.class);

    private final JdbcTemplate jdbc;

    public V18AgentBrowserProfileMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS agent_browser_profile (
                  tenant_id INTEGER NOT NULL,
                  platform TEXT NOT NULL,
                  session_key TEXT NOT NULL,
                  platform_account_id TEXT NOT NULL DEFAULT '',
                  account TEXT NOT NULL DEFAULT '',
                  bundle_rel_path TEXT NOT NULL DEFAULT '',
                  bundle_sha256 TEXT NOT NULL DEFAULT '',
                  bundle_bytes INTEGER NOT NULL DEFAULT 0,
                  session_json TEXT NOT NULL DEFAULT '{}',
                  updated_at TEXT NOT NULL,
                  updated_by_agent_id TEXT NOT NULL DEFAULT '',
                  PRIMARY KEY (tenant_id, platform, session_key)
                )
                """);
        jdbc.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_browser_profile_tenant_platform
                ON agent_browser_profile (tenant_id, platform)
                """);
        log.info("V18AgentBrowserProfileMigration applied");
    }
}
