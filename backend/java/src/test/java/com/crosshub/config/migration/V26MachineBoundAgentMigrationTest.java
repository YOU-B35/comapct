package com.crosshub.config.migration;

import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

import static org.junit.jupiter.api.Assertions.assertEquals;

class V26MachineBoundAgentMigrationTest {

    @Test
    void retiresOlderDuplicatesKeepingNewestHeartbeat() throws Exception {
        DriverManagerDataSource ds = new DriverManagerDataSource();
        ds.setDriverClassName("org.sqlite.JDBC");
        ds.setUrl("jdbc:sqlite:file:v26mig?mode=memory&cache=shared");
        JdbcTemplate jdbc = new JdbcTemplate(ds);
        // Hold one connection open so shared in-memory DB survives across statements.
        try (var keepAlive = ds.getConnection()) {
            jdbc.execute("""
                    CREATE TABLE integration_agent (
                      id TEXT PRIMARY KEY,
                      tenant_id INTEGER,
                      machine_fingerprint TEXT,
                      last_heartbeat_at TEXT,
                      created_at TEXT,
                      status TEXT,
                      agent_token TEXT
                    )
                    """);
            jdbc.update(
                    "INSERT INTO integration_agent VALUES (?,?,?,?,?,?,?)",
                    "old", 5, "fp-1", "2026-08-01 10:00:00", "2026-08-01 09:00:00", "active", "tok-old"
            );
            jdbc.update(
                    "INSERT INTO integration_agent VALUES (?,?,?,?,?,?,?)",
                    "new", 5, "fp-1", "2026-08-11 12:00:00", "2026-08-02 09:00:00", "active", "tok-new"
            );
            jdbc.update(
                    "INSERT INTO integration_agent VALUES (?,?,?,?,?,?,?)",
                    "other", 5, "fp-2", "2026-08-11 12:00:00", "2026-08-02 09:00:00", "active", "tok-o"
            );

            int retired = V26MachineBoundAgentMigration.retireDuplicateMachineAgents(jdbc);
            assertEquals(1, retired);
            assertEquals("active", jdbc.queryForObject(
                    "SELECT status FROM integration_agent WHERE id = ?", String.class, "new"));
            assertEquals("retired", jdbc.queryForObject(
                    "SELECT status FROM integration_agent WHERE id = ?", String.class, "old"));
            assertEquals("", jdbc.queryForObject(
                    "SELECT agent_token FROM integration_agent WHERE id = ?", String.class, "old"));
            assertEquals("active", jdbc.queryForObject(
                    "SELECT status FROM integration_agent WHERE id = ?", String.class, "other"));
        }    }
}
