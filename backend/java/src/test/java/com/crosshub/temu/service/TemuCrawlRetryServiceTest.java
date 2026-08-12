package com.crosshub.temu.service;

import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.common.AppErrorCode;
import com.crosshub.temu.entity.TemuCrawlJob;
import com.crosshub.temu.repository.TemuCrawlJobRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class TemuCrawlRetryServiceTest {
    private TemuCrawlJobRepository jobRepository;
    private TemuAgentService temuAgentService;
    private AgentPresenceService agentPresenceService;
    private TemuCrawlRetryService service;

    @BeforeEach
    void setUp() {
        jobRepository = mock(TemuCrawlJobRepository.class);
        temuAgentService = mock(TemuAgentService.class);
        agentPresenceService = mock(AgentPresenceService.class);
        service = new TemuCrawlRetryService(jobRepository, temuAgentService, agentPresenceService);
        when(jobRepository.save(any(TemuCrawlJob.class))).thenAnswer(inv -> inv.getArgument(0));
    }

    @Test
    void backoffScheduleMatchesApprovedPlan() {
        assertEquals(2, TemuCrawlRetryService.backoffMinutesForNextAttempt(1));
        assertEquals(5, TemuCrawlRetryService.backoffMinutesForNextAttempt(2));
        assertEquals(10, TemuCrawlRetryService.backoffMinutesForNextAttempt(3));
        assertEquals(15, TemuCrawlRetryService.backoffMinutesForNextAttempt(4));
        assertEquals(20, TemuCrawlRetryService.backoffMinutesForNextAttempt(5));
        assertEquals(30, TemuCrawlRetryService.backoffMinutesForNextAttempt(6));
        assertEquals(30, TemuCrawlRetryService.backoffMinutesForNextAttempt(7));
        assertEquals(30, TemuCrawlRetryService.backoffMinutesForNextAttempt(99));
    }

    @Test
    void humanChallengeIsNotAutoRetried() {
        assertFalse(TemuCrawlRetryService.isAutoRetryable("CRAWL_HUMAN_CHALLENGE"));
        assertTrue(TemuCrawlRetryService.isAutoRetryable(AppErrorCode.TEMU_AGENT_OFFLINE.getCode()));
        assertFalse(TemuCrawlRetryService.isAutoRetryable(AppErrorCode.CRAWL_NOT_LOGGED_IN.getCode()));
        assertFalse(TemuCrawlRetryService.isAutoRetryable("TEMU_REGION_NO_PERMISSION"));
    }

    @Test
    void resumeJobDefersWhenTenantHelperOffline() {
        TemuCrawlJob job = new TemuCrawlJob();
        job.setId("job-user-1");
        job.setTenantId(5L);
        job.setTriggeredBy(42L);
        job.setStatus("retry_wait");
        job.setRetryCount(1);
        job.setMaxRetryCount(8);
        job.setNextRetryAt("2020-01-01 00:00:00");

        when(agentPresenceService.isAgentOnlineForTenant(5L)).thenReturn(false);

        service.resumeJob(job);

        assertEquals("retry_wait", job.getStatus());
        assertEquals(AppErrorCode.TEMU_USER_HELPER_OFFLINE.getCode(), job.getErrorCode());
        assertEquals(AppErrorCode.TEMU_USER_HELPER_OFFLINE.getUserMessage(), job.getErrorMessage());
        assertFalse(job.getNextRetryAt().isBlank());
        verify(temuAgentService, never()).enqueueCrawlJob(any());
        verify(temuAgentService, never()).enqueueCrawlJob(any(), any());
        verify(agentPresenceService).isAgentOnlineForTenant(5L);
    }
}
