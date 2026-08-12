package com.crosshub.commander.service;

import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class CommanderProxyServiceTest {
    @Test
    void rewritesCommanderPrefixToUpstreamApiV1() {
        assertEquals(
                "/api/v1/agent/list",
                CommanderProxyService.toCommanderPath("/api/commander/v1/agent/list", null)
        );
        assertEquals(
                "/api/v1/agent/task_list?page=1",
                CommanderProxyService.toCommanderPath("/api/commander/v1/agent/task_list", "page=1")
        );
    }

    @Test
    void rejectsNonV1Paths() {
        assertThrows(
                ResponseStatusException.class,
                () -> CommanderProxyService.toCommanderPath("/api/commander/other", null)
        );
    }

    @Test
    void extractsTokenShapes() {
        assertEquals("tok-a", CommanderSessionService.extractToken("{\"code\":0,\"data\":\"tok-a\"}"));
        assertEquals("tok-b", CommanderSessionService.extractToken("{\"code\":0,\"data\":{\"token\":\"tok-b\"}}"));
        assertEquals("tok-c", CommanderSessionService.extractToken("{\"token\":\"tok-c\"}"));
    }

    @Test
    void stripsCrLfFromCommanderSecrets() {
        assertEquals("admin", CommanderSessionService.sanitizeSecret("admin\r\n"));
        assertEquals("admin123", CommanderSessionService.sanitizeSecret("admin123\r"));
        assertEquals("https://www.yoto.work", CommanderSessionService.normalizeBaseUrl("https://www.yoto.work/\r\n"));
    }
}
