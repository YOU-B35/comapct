package com.crosshub.temu.service;

import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.auth.entity.AppUser;
import com.crosshub.auth.repository.AppUserRepository;
import com.crosshub.config.CrawlerProperties;
import com.crosshub.temu.entity.TemuCrawlJob;
import com.crosshub.temu.repository.TemuCrawlJobRepository;
import com.crosshub.temu.repository.TemuSaleRepository;
import com.crosshub.tenant.service.DataScopeService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * Temu 日批切片：由 {@link com.crosshub.platform.service.PlatformDailySyncService} 在每天 09:30 全平台编排时调用。
 * 每个有在线绑定助手的用户各入队一次（店铺 scope）；无在线助手的用户跳过，不写失败任务刷屏。
 * 调度入队不走 {@link TemuSyncLimitService} 的每用户 3 次/分钟限流。
 */
@Service
public class TemuDailySyncService {
    private static final Logger log = LoggerFactory.getLogger(TemuDailySyncService.class);
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final long SYSTEM_TRIGGERED_BY = 0L;
    private static final List<String> ACTIVE = List.of("pending", "running", "retry_wait");

    private final CrawlerProperties crawlerProperties;
    private final AgentPresenceService agentPresenceService;
    private final TemuAgentService temuAgentService;
    private final TemuCrawlJobRepository jobRepository;
    private final TemuSaleRepository saleRepository;
    private final AppUserRepository userRepository;
    private final DataScopeService dataScopeService;

    public TemuDailySyncService(
            CrawlerProperties crawlerProperties,
            AgentPresenceService agentPresenceService,
            TemuAgentService temuAgentService,
            TemuCrawlJobRepository jobRepository,
            TemuSaleRepository saleRepository,
            AppUserRepository userRepository,
            DataScopeService dataScopeService
    ) {
        this.crawlerProperties = crawlerProperties;
        this.agentPresenceService = agentPresenceService;
        this.temuAgentService = temuAgentService;
        this.jobRepository = jobRepository;
        this.saleRepository = saleRepository;
        this.userRepository = userRepository;
        this.dataScopeService = dataScopeService;
    }

    public void runDailySyncForAllRegisteredTenants() {
        if (!crawlerProperties.getDailySync().isEnabled()) {
            log.info("Temu daily sync skipped: disabled");
            return;
        }
        if (!temuAgentService.useAgentMode()) {
            log.info("Temu daily sync skipped: agent mode off");
            return;
        }
        List<Long> tenants = agentPresenceService.listRegisteredTenantIds();
        if (tenants.isEmpty()) {
            log.info("Temu daily sync: no registered agents");
            return;
        }
        log.info("Temu daily sync start for {} tenant(s)", tenants.size());
        for (Long tenantId : tenants) {
            try {
                Map<String, Object> result = enqueueDailyCrawl(tenantId);
                log.info(
                        "Temu daily sync tenant {}: {} enqueued={} skipped_offline={}",
                        tenantId,
                        result.get("action"),
                        result.get("enqueued_count"),
                        result.get("skipped_offline")
                );
            } catch (Exception ex) {
                log.warn("Temu daily sync failed for tenant {}: {}", tenantId, ex.getMessage());
            }
        }
    }

    @Transactional
    public Map<String, Object> enqueueDailyCrawl(Long tenantId) {
        return enqueueDailyCrawl(tenantId, false);
    }

    @Transactional
    public Map<String, Object> enqueueDailyCrawl(Long tenantId, boolean force) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("tenant_id", tenantId);
        out.put("force", force);
        String today = LocalDate.now(zoneId()).toString();
        out.put("report_time", today);

        List<AppUser> candidates = listDailySyncUsers(tenantId);
        int skippedOffline = 0;
        int skippedAlready = 0;
        int skippedActive = 0;
        int skippedNoScope = 0;
        int enqueuedCount = 0;
        List<Map<String, Object>> jobs = new ArrayList<>();

        boolean tenantHelperOnline = agentPresenceService.isAgentOnlineForTenant(tenantId);
        if (!tenantHelperOnline) {
            out.put("skipped_offline", candidates.size());
            out.put("skipped_already_ran", 0);
            out.put("skipped_active", 0);
            out.put("skipped_no_scope", 0);
            out.put("enqueued_count", 0);
            out.put("jobs", jobs);
            out.put("action", candidates.isEmpty() ? "skipped_no_users" : "skipped_all_offline");
            log.info("Temu daily sync tenant {}: helper offline, skipped {} user(s)", tenantId, candidates.size());
            return out;
        }

        for (AppUser user : candidates) {
            Long userId = user.getId();
            if (userId == null) {
                continue;
            }

            if (!force) {
                Optional<TemuCrawlJob> existingToday = findTodayJobForUser(tenantId, userId, today);
                if (existingToday.isPresent()) {
                    TemuCrawlJob job = existingToday.get();
                    String st = nullToEmpty(job.getStatus()).toLowerCase();
                    if ("pending".equals(st) || "running".equals(st) || "retry_wait".equals(st)) {
                        skippedActive++;
                        jobs.add(toJobMap(job));
                        continue;
                    }
                    skippedAlready++;
                    jobs.add(toJobMap(job));
                    continue;
                }
            }

            Optional<TemuCrawlJob> active = jobRepository
                    .findFirstByTenantIdAndTriggeredByAndStatusInOrderByCreatedAtDesc(tenantId, userId, ACTIVE);
            if (active.isPresent()) {
                skippedActive++;
                jobs.add(toJobMap(active.get()));
                continue;
            }

            boolean bossPortal = user.isAdmin();
            List<String> shopIds = dataScopeService.resolveScopeForLogin(tenantId, userId, bossPortal);
            if (!bossPortal && (shopIds == null || shopIds.isEmpty())) {
                skippedNoScope++;
                log.info("Temu daily sync skip user {} tenant {}: empty shop scope", userId, tenantId);
                continue;
            }

            TemuCrawlJob job = new TemuCrawlJob();
            job.setId(UUID.randomUUID().toString());
            job.setTenantId(tenantId);
            job.setTriggeredBy(userId);
            job.setStatus("pending");
            job.setMode("live");
            job.setReportTime(today);
            job.setCreatedAt(now());
            job.setAgentTaskId("");
            jobRepository.save(job);
            // Daily scheduler path: bypass TemuSyncLimitService 3/min per-user UI quota.
            temuAgentService.enqueueCrawlJob(job, shopIds == null ? List.of() : shopIds);
            jobs.add(toJobMap(job));
            enqueuedCount++;
        }

        out.put("skipped_offline", skippedOffline);
        out.put("skipped_already_ran", skippedAlready);
        out.put("skipped_active", skippedActive);
        out.put("skipped_no_scope", skippedNoScope);
        out.put("enqueued_count", enqueuedCount);
        out.put("jobs", jobs);

        if (candidates.isEmpty()) {
            out.put("action", "skipped_no_users");
            return out;
        }
        if (enqueuedCount == 0 && skippedOffline == candidates.size()) {
            out.put("action", "skipped_all_offline");
            log.info("Temu daily sync tenant {}: skipped {} offline user(s), no jobs created", tenantId, skippedOffline);
            return out;
        }
        out.put("action", enqueuedCount > 0 ? "enqueued_users" : "skipped_users");
        if (skippedOffline > 0) {
            log.info("Temu daily sync tenant {}: skipped_offline={}", tenantId, skippedOffline);
        }
        return out;
    }

    private List<AppUser> listDailySyncUsers(Long tenantId) {
        List<AppUser> all = userRepository.findByTenantIdOrderByIdAsc(tenantId);
        List<AppUser> out = new ArrayList<>();
        for (AppUser user : all) {
            if (user == null || !user.isActive()) {
                continue;
            }
            if (user.isWarehouse()) {
                continue;
            }
            out.add(user);
        }
        return out;
    }

    private Optional<TemuCrawlJob> findTodayJobForUser(Long tenantId, Long userId, String today) {
        Optional<TemuCrawlJob> latest = jobRepository.findFirstByTenantIdAndTriggeredByOrderByCreatedAtDesc(tenantId, userId);
        if (latest.isEmpty()) {
            return Optional.empty();
        }
        TemuCrawlJob job = latest.get();
        String created = nullToEmpty(job.getCreatedAt());
        String report = nullToEmpty(job.getReportTime());
        if (created.startsWith(today) || today.equals(report)) {
            return Optional.of(job);
        }
        return Optional.empty();
    }

    public Map<String, Object> buildSyncStatus(Long tenantId) {
        Map<String, Object> out = new LinkedHashMap<>();
        CrawlerProperties.DailySync cfg = crawlerProperties.getDailySync();
        Map<String, Object> schedule = new LinkedHashMap<>();
        schedule.put("enabled", cfg.isEnabled() && temuAgentService.useAgentMode());
        schedule.put("cron", cfg.getCron());
        schedule.put("zone", cfg.getZone());
        schedule.put("time_label", "每天 09:30");
        schedule.put("next_run_hint", nextRunHint());
        out.put("schedule", schedule);

        boolean agentOnline = agentPresenceService.isAgentOnline(tenantId);
        out.put("agent_online", agentOnline);
        out.putAll(agentPresenceService.integrationStatus(tenantId));

        Optional<TemuCrawlJob> latest = jobRepository.findFirstByTenantIdOrderByCreatedAtDesc(tenantId);
        if (latest.isPresent()) {
            TemuCrawlJob job = latest.get();
            Map<String, Object> jobMap = toJobMap(job);
            Long triggeredBy = job.getTriggeredBy();
            jobMap.put("trigger", triggeredBy != null && triggeredBy > 0
                    ? "daily_or_user"
                    : (triggeredBy != null && triggeredBy == SYSTEM_TRIGGERED_BY ? "daily_schedule" : "manual"));
            out.put("last_job", jobMap);
            boolean failed = "failed".equalsIgnoreCase(job.getStatus());
            out.put("has_error", failed);
            out.put("error_code", failed ? nullToEmpty(job.getErrorCode()) : "");
            out.put("error_message", failed ? nullToEmpty(job.getErrorMessage()) : "");
        } else {
            out.put("last_job", null);
            out.put("has_error", false);
            out.put("error_code", "");
            out.put("error_message", "");
        }

        String dataReportTime = "";
        try {
            String latestReport = saleRepository.findLatestReportTimeByTenantId(tenantId);
            dataReportTime = latestReport == null ? "" : latestReport;
        } catch (Exception ignored) {
            dataReportTime = "";
        }
        out.put("data_report_time", dataReportTime);
        return out;
    }

    private Map<String, Object> toJobMap(TemuCrawlJob job) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("id", job.getId());
        map.put("status", job.getStatus());
        map.put("mode", job.getMode());
        map.put("report_time", job.getReportTime());
        map.put("error_code", job.getErrorCode());
        map.put("error_message", job.getErrorMessage());
        map.put("created_at", job.getCreatedAt());
        map.put("started_at", job.getStartedAt());
        map.put("finished_at", job.getFinishedAt());
        map.put("rows_count", job.getRowsCount());
        map.put("shops_count", job.getShopsCount());
        map.put("triggered_by", job.getTriggeredBy());
        return map;
    }

    private String nextRunHint() {
        ZoneId zone = zoneId();
        ZonedDateTime now = ZonedDateTime.now(zone);
        ZonedDateTime next = now.withHour(9).withMinute(30).withSecond(0).withNano(0);
        if (!next.isAfter(now)) {
            next = next.plusDays(1);
        }
        return next.format(DateTimeFormatter.ofPattern("MM-dd HH:mm"));
    }

    private ZoneId zoneId() {
        try {
            return ZoneId.of(crawlerProperties.getDailySync().getZone());
        } catch (Exception ex) {
            return ZoneId.of("Asia/Shanghai");
        }
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }

    private static String nullToEmpty(String value) {
        return value == null ? "" : value;
    }
}
