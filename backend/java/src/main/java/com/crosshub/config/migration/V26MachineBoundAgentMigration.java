package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Dedupe user-bound agents that share the same machine fingerprint within a tenant
 * so each (tenant_id, machine_fingerprint) has one canonical active row.
 */
@Component
@Order(26)
public class V26MachineBoundAgentMigration {
    private static final Logger log = LoggerFactory.getLogger(V26MachineBoundAgentMigration.class);

    private final JdbcTemplate jdbc;

    public V26MachineBoundAgentMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        retireDuplicateMachineAgents(jdbc);
        jdbc.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_tenant_fp ON integration_agent(tenant_id, machine_fingerprint)"
        );
        log.info("V26MachineBoundAgentMigration applied");
    }

    /**
     * Keep newest heartbeat (then created_at) per (tenant_id, fingerprint); retire the rest.
     * Visible for unit tests with an in-memory JdbcTemplate.
     */
    static int retireDuplicateMachineAgents(JdbcTemplate jdbc) {
        List<Map<String, Object>> rows = jdbc.queryForList(
                """
                SELECT id, tenant_id, machine_fingerprint, last_heartbeat_at, created_at, status
                FROM integration_agent
                WHERE machine_fingerprint IS NOT NULL
                  AND TRIM(machine_fingerprint) != ''
                  AND LOWER(COALESCE(status, '')) = 'active'
                """
        );
        Map<String, List<Map<String, Object>>> groups = new HashMap<>();
        for (Map<String, Object> row : rows) {
            Object tenant = row.get("tenant_id");
            String fp = String.valueOf(row.get("machine_fingerprint")).trim();
            if (tenant == null || fp.isEmpty()) {
                continue;
            }
            String key = tenant + "\0" + fp;
            groups.computeIfAbsent(key, ignored -> new ArrayList<>()).add(row);
        }
        int retired = 0;
        for (List<Map<String, Object>> group : groups.values()) {
            if (group.size() < 2) {
                continue;
            }
            group.sort(Comparator
                    .comparing((Map<String, Object> r) -> nullToEmpty(r.get("last_heartbeat_at")))
                    .thenComparing(r -> nullToEmpty(r.get("created_at")))
                    .reversed());
            for (int i = 1; i < group.size(); i++) {
                String id = String.valueOf(group.get(i).get("id"));
                jdbc.update(
                        "UPDATE integration_agent SET status = 'retired', agent_token = '' WHERE id = ?",
                        id
                );
                retired++;
            }
        }
        if (retired > 0) {
            log.info("V26MachineBoundAgentMigration retired {} duplicate machine agents", retired);
        }
        return retired;
    }

    private static String nullToEmpty(Object value) {
        return value == null ? "" : String.valueOf(value);
    }
}
