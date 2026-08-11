package com.crosshub.temu.service;

import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.auth.entity.AppUser;
import com.crosshub.auth.repository.AppUserRepository;
import com.crosshub.config.CrawlerProperties;
import com.crosshub.temu.entity.TemuCrawlJob;
import com.crosshub.temu.repository.TemuCrawlJobRepository;
import com.crosshub.temu.repository.TemuSaleRepository;
import com.crosshub.tenant.service.DataScopeService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Daily 09:30 enqueues one crawl per user with an online bound helper (scoped shops);
 * users without an online helper are skipped — no failed-job spam.
 */
class TemuDailySyncEnqueueTest {
    private CrawlerProperties crawlerProperties;
    private AgentPresenceService agentPresenceService;
    private TemuAgentService temuAgentService;
    private TemuCrawlJobRepository jobRepository;
    private TemuSaleRepository saleRepository;
    private AppUserRepository userRepository;
    private DataScopeService dataScopeService;
    private TemuDailySyncService service;

    @BeforeEach
    void setUp() {
        crawlerProperties = new CrawlerProperties();
        crawlerProperties.getDailySync().setEnabled(true);
        crawlerProperties.getDailySync().setZone("Asia/Shanghai");
        agentPresenceService = mock(AgentPresenceService.class);
        temuAgentService = mock(TemuAgentService.class);
        jobRepository = mock(TemuCrawlJobRepository.class);
        saleRepository = mock(TemuSaleRepository.class);
        userRepository = mock(AppUserRepository.class);
        dataScopeService = mock(DataScopeService.class);
        service = new TemuDailySyncService(
                crawlerProperties,
                agentPresenceService,
                temuAgentService,
                jobRepository,
                saleRepository,
                userRepository,
                dataScopeService
        );
        when(jobRepository.findFirstByTenantIdAndTriggeredByOrderByCreatedAtDesc(anyLong(), anyLong()))
                .thenReturn(Optional.empty());
        when(jobRepository.findFirstByTenantIdAndTriggeredByAndStatusInOrderByCreatedAtDesc(
                anyLong(), anyLong(), any())).thenReturn(Optional.empty());
        when(jobRepository.save(any(TemuCrawlJob.class))).thenAnswer(inv -> inv.getArgument(0));
    }

    @Test
    void enqueuesOnlyForUsersWithOnlineHelper() {
        AppUser online = user(101L, 5L, "admin");
        AppUser offline = user(102L, 5L, "user");
        when(userRepository.findByTenantIdOrderByIdAsc(5L)).thenReturn(List.of(online, offline));
        when(agentPresenceService.isAgentOnlineForUser(101L)).thenReturn(true);
        when(agentPresenceService.isAgentOnlineForUser(102L)).thenReturn(false);
        when(dataScopeService.resolveScopeForLogin(eq(5L), eq(101L), eq(true))).thenReturn(List.of());
        when(dataScopeService.resolveScopeForLogin(eq(5L), eq(102L), eq(false)))
                .thenReturn(List.of("shop-a"));

        Map<String, Object> out = service.enqueueDailyCrawl(5L, true);

        assertEquals("enqueued_users", out.get("action"));
        assertEquals(1, out.get("enqueued_count"));
        assertEquals(1, out.get("skipped_offline"));

        ArgumentCaptor<TemuCrawlJob> jobCaptor = ArgumentCaptor.forClass(TemuCrawlJob.class);
        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<String>> shopsCaptor = ArgumentCaptor.forClass(List.class);
        verify(temuAgentService, times(1)).enqueueCrawlJob(jobCaptor.capture(), shopsCaptor.capture());
        assertEquals(101L, jobCaptor.getValue().getTriggeredBy());
        assertEquals("pending", jobCaptor.getValue().getStatus());
        assertTrue(jobCaptor.getValue().getId() != null && !jobCaptor.getValue().getId().isBlank());

        verify(jobRepository, times(1)).save(any(TemuCrawlJob.class));
        verify(agentPresenceService, never()).isAgentOnline(anyLong());
    }

    @Test
    void skipsAllOfflineUsersWithoutCreatingJobs() {
        AppUser a = user(201L, 5L, "user");
        AppUser b = user(202L, 5L, "user");
        when(userRepository.findByTenantIdOrderByIdAsc(5L)).thenReturn(List.of(a, b));
        when(agentPresenceService.isAgentOnlineForUser(anyLong())).thenReturn(false);

        Map<String, Object> out = service.enqueueDailyCrawl(5L, true);

        assertEquals("skipped_all_offline", out.get("action"));
        assertEquals(2, out.get("skipped_offline"));
        assertEquals(0, out.get("enqueued_count"));
        verify(temuAgentService, never()).enqueueCrawlJob(any(), any());
        verify(jobRepository, never()).save(any());
    }

    private static AppUser user(Long id, Long tenantId, String role) {
        AppUser u = new AppUser();
        u.setTenantId(tenantId);
        u.setUsername("u" + id);
        u.setRole(role);
        u.setStatus("active");
        try {
            var field = AppUser.class.getDeclaredField("id");
            field.setAccessible(true);
            field.set(u, id);
        } catch (ReflectiveOperationException ex) {
            throw new IllegalStateException(ex);
        }
        return u;
    }
}
