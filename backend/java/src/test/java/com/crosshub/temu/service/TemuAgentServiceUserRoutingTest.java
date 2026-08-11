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
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class TemuAgentServiceUserRoutingTest {

    private AgentPresenceService agentPresenceService;
    private TemuAgentService service;
    private TemuSellerSessionService sellerSessionService;

    @BeforeEach
    void setUp() {
        agentPresenceService = mock(AgentPresenceService.class);
        sellerSessionService = mock(TemuSellerSessionService.class);
        CrawlerProperties crawlerProperties = new CrawlerProperties();
        crawlerProperties.setUseAgent(true);

        service = new TemuAgentService(
                agentPresenceService,
                crawlerProperties,
                mock(TemuCrawlJobRepository.class),
                mock(TemuAgentIngestService.class),
                mock(PlatformAccountService.class),
                sellerSessionService,
                mock(TenantCrawlCooldownService.class),
                mock(AgentProfileService.class),
                mock(JdbcTemplate.class),
                new ObjectMapper()
        );
    }

    @Test
    void enqueueLoginOpenRequiresUserOnlineHelper() {
        when(agentPresenceService.isAgentOnlineForUser(42L)).thenReturn(false);

        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> service.enqueueLoginOpenForUser(5L, 42L, null)
        );

        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, ex.getStatusCode());
        assertEquals("本机同步助手未在线，请先安装并绑定", ex.getReason());
    }
}
