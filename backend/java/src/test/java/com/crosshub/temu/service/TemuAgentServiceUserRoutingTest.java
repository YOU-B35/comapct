package com.crosshub.temu.service;

import com.crosshub.agent.entity.IntegrationAgent;
import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.agent.service.AgentProfileService;
import com.crosshub.common.TenantCrawlCooldownService;
import com.crosshub.config.CrawlerProperties;
import com.crosshub.platform.service.PlatformAccountService;
import com.crosshub.temu.entity.TemuCrawlJob;
import com.crosshub.temu.repository.TemuCrawlJobRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class TemuAgentServiceUserRoutingTest {

    private AgentPresenceService agentPresenceService;
    private TemuAgentService service;
    private TemuSellerSessionService sellerSessionService;
    private TemuCrawlJobRepository jobRepository;
    private JdbcTemplate jdbc;

    @BeforeEach
    void setUp() {
        agentPresenceService = mock(AgentPresenceService.class);
        sellerSessionService = mock(TemuSellerSessionService.class);
        jobRepository = mock(TemuCrawlJobRepository.class);
        jdbc = mock(JdbcTemplate.class);
        CrawlerProperties crawlerProperties = new CrawlerProperties();
        crawlerProperties.setUseAgent(true);

        service = new TemuAgentService(
                agentPresenceService,
                crawlerProperties,
                jobRepository,
                mock(TemuAgentIngestService.class),
                mock(PlatformAccountService.class),
                sellerSessionService,
                mock(TenantCrawlCooldownService.class),
                mock(AgentProfileService.class),
                jdbc,
                new ObjectMapper()
        );
        when(jobRepository.save(any(TemuCrawlJob.class))).thenAnswer(inv -> inv.getArgument(0));
        when(sellerSessionService.listSellerSessions(any())).thenReturn(List.of());
    }

    @Test
    void enqueueLoginOpenRequiresUserOnlineHelper() {
        when(agentPresenceService.findLatestOnlineAgentForUser(42L)).thenReturn(null);

        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> service.enqueueLoginOpenForUser(5L, 42L, null)
        );

        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, ex.getStatusCode());
        assertEquals("本机同步助手未在线，请先安装并绑定", ex.getReason());
    }

    @Test
    void enqueueCrawlJobFailsClosedForUserWhenHelperOffline() {
        TemuCrawlJob job = new TemuCrawlJob();
        job.setId("job-1");
        job.setTenantId(5L);
        job.setTriggeredBy(42L);
        job.setMode("full");
        when(agentPresenceService.findLatestOnlineAgentForUser(42L)).thenReturn(null);

        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> service.enqueueCrawlJob(job)
        );

        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, ex.getStatusCode());
        assertEquals("本机同步助手未在线，请先安装并绑定", ex.getReason());
        verify(jdbc, never()).update(anyString(), any(), any(), any(), any(), any(), any(), any(), any(), any(), any(), any(), any());
    }

    @Test
    void enqueueCrawlJobInsertsBoundAgentIdWhenUserHelperOnline() {
        TemuCrawlJob job = new TemuCrawlJob();
        job.setId("job-2");
        job.setTenantId(5L);
        job.setTriggeredBy(42L);
        job.setMode("full");

        IntegrationAgent agent = new IntegrationAgent();
        agent.setId("agt-user-42");
        when(agentPresenceService.findLatestOnlineAgentForUser(42L)).thenReturn(agent);

        service.enqueueCrawlJob(job);

        ArgumentCaptor<Object> agentIdCaptor = ArgumentCaptor.forClass(Object.class);
        verify(jdbc).update(
                anyString(),
                any(),
                eq(5L),
                agentIdCaptor.capture(),
                eq(TemuAgentTasks.CRAWL),
                any(),
                any(),
                any(),
                any(),
                any(),
                any(),
                any(),
                any()
        );
        assertEquals("agt-user-42", agentIdCaptor.getValue());
        assertTrue(job.getAgentTaskId() != null && !job.getAgentTaskId().isBlank());
    }
}
