package com.crosshub.temu.service;

import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.agent.service.AgentProfileService;
import com.crosshub.common.TenantCrawlCooldownService;
import com.crosshub.config.CrawlerProperties;
import com.crosshub.platform.service.PlatformAccountService;
import com.crosshub.temu.repository.TemuCrawlJobRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;

import java.time.Duration;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class TemuAgentServiceSessionSnapshotTest {

    private JdbcTemplate jdbc;
    private TemuAgentService service;

    @BeforeEach
    void setUp() {
        SingleConnectionDataSource dataSource = new SingleConnectionDataSource("jdbc:sqlite::memory:", true);
        jdbc = new JdbcTemplate(dataSource);
        jdbc.execute("""
                CREATE TABLE temu_session_snapshot (
                  tenant_id INTEGER PRIMARY KEY,
                  payload_json TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """);

        AgentProfileService agentProfileService = mock(AgentProfileService.class);
        when(agentProfileService.listByTenant(5L, "temu")).thenReturn(List.of());

        service = new TemuAgentService(
                mock(AgentPresenceService.class),
                new CrawlerProperties(),
                mock(TemuCrawlJobRepository.class),
                mock(TemuAgentIngestService.class),
                mock(PlatformAccountService.class),
                mock(TemuSellerSessionService.class),
                mock(TenantCrawlCooldownService.class),
                agentProfileService,
                jdbc,
                new ObjectMapper()
        );
    }

    @Test
    void readSessionSnapshot_upgradesLegacyFlatPayloadWithoutStackOverflow() {
        jdbc.update(
                "INSERT INTO temu_session_snapshot(tenant_id, payload_json, updated_at) VALUES (?,?,?)",
                5L,
                """
                {"tenant_id":5,"ready":true,"logged_in":true,"mall_id":"634418211126671","message":"ok"}
                """,
                "2026-07-30 01:30:00"
        );

        Map<String, Object> snapshot = assertTimeoutPreemptively(
                Duration.ofSeconds(2),
                () -> service.readSessionSnapshot(5L),
                "legacy flat snapshot must not recurse forever"
        );

        assertEquals(5L, ((Number) snapshot.get("tenant_id")).longValue());
        assertTrue(Boolean.TRUE.equals(snapshot.get("ready")));
        assertEquals("634418211126671", String.valueOf(snapshot.get("mall_id")));
        assertInstanceOf(List.class, snapshot.get("sessions"));
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> sessions = (List<Map<String, Object>>) snapshot.get("sessions");
        assertFalse(sessions.isEmpty());
        assertEquals("default", String.valueOf(sessions.get(0).get("session_key")));
        assertEquals(1, ((Number) snapshot.get("session_count")).intValue());
    }

    @Test
    void readSessionSnapshot_upgradesLegacyPayloadThatHasExplicitSessionKey() {
        jdbc.update(
                "INSERT INTO temu_session_snapshot(tenant_id, payload_json, updated_at) VALUES (?,?,?)",
                5L,
                """
                {"tenant_id":5,"session_key":"13861260796","ready":true,"logged_in":true,"mall_id":"111"}
                """,
                "2026-07-31 01:00:00"
        );

        Map<String, Object> snapshot = assertTimeoutPreemptively(
                Duration.ofSeconds(2),
                () -> service.readSessionSnapshot(5L)
        );

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> sessions = (List<Map<String, Object>>) snapshot.get("sessions");
        assertEquals(1, sessions.size());
        assertEquals("13861260796", String.valueOf(sessions.get(0).get("session_key")));
        assertTrue(Boolean.TRUE.equals(snapshot.get("ready")));
    }
}
