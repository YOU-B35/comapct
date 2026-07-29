package com.crosshub.temu.service;

import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.common.AppErrorCode;
import com.crosshub.config.CrawlerProperties;
import com.crosshub.temu.entity.TemuCrawlJob;
import com.crosshub.temu.repository.TemuCrawlJobRepository;
import com.crosshub.temu.repository.TemuSaleRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * Temu 日批切片：由 {@link com.crosshub.platform.service.PlatformDailySyncService} 在每天 09:30 全平台编排时调用。
 */
@Service
public class TemuDailySyncService {
    private static final Logger log = LoggerFactory.getLogger(TemuDailySyncService.class);
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final long SYSTEM_TRIGGERED_BY = 0L;
    private static final List<String> ACTIVE = List.of("pending", "running");

    private final CrawlerProperties crawlerProperties;
    private final AgentPresenceService agentPresenceService;
    private final TemuAgentService temuAgentService;
    private final TemuCrawlJobRepository jobRepository;
    private final TemuSaleRepository saleRepository;

    public TemuDailySyncService(
            CrawlerProperties crawlerProperties,
            AgentPresenceService agentPresenceService,
            TemuAgentService temuAgentService,
            TemuCrawlJobRepository jobRepository,
            TemuSaleRepository saleRepository
    ) {
        this.crawlerProperties = crawlerProperties;
        this.agentPresenceService = agentPresenceService;
        this.temuAgentService = temuAgentService;
        this.jobRepository = jobRepository;
        this.saleRepository = saleRepository;
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
                log.info("Temu daily sync tenant {}: {}", tenantId, result.get("action"));
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

        if (!force) {
            Optional<TemuCrawlJob> existingToday = findTodayJob(tenantId, today);
            if (existingToday.isPresent()) {
                TemuCrawlJob job = existingToday.get();
                out.put("action", "skipped_already_ran");
                out.put("job", toJobMap(job));
                return out;
            }
        }

        Optional<TemuCrawlJob> active = jobRepository.findFirstByTenantIdAndStatusInOrderByCreatedAtDesc(tenantId, ACTIVE);
        if (active.isPresent()) {
            out.put("action", "skipped_active");
            out.put("job", toJobMap(active.get()));
            return out;
        }

        if (!agentPresenceService.isAgentOnline(tenantId)) {
            TemuCrawlJob failed = createTerminalJob(
                    tenantId,
                    today,
                    "failed",
                    AppErrorCode.TEMU_AGENT_OFFLINE.getCode(),
                    AppErrorCode.TEMU_AGENT_OFFLINE.getUserMessage()
            );
            out.put("action", "failed_agent_offline");
            out.put("job", toJobMap(failed));
            return out;
        }

        Map<String, Object> session = temuAgentService.readSessionSnapshot(tenantId);
        boolean ready = Boolean.TRUE.equals(session.get("ready"));
        if (!ready) {
            String hint = stringValue(session.get("error_hint"));
            AppErrorCode code = AppErrorCode.fromCode(hint);
            if (code == null || code == AppErrorCode.UNKNOWN) {
                code = AppErrorCode.CRAWL_NOT_LOGGED_IN;
            }
            String message = stringValue(session.get("message"));
            if (message.isBlank()) {
                message = code.getUserMessage();
            }
            TemuCrawlJob failed = createTerminalJob(tenantId, today, "failed", code.getCode(), message);
            out.put("action", "failed_session_not_ready");
            out.put("job", toJobMap(failed));
            return out;
        }

        TemuCrawlJob job = new TemuCrawlJob();
        job.setId(UUID.randomUUID().toString());
        job.setTenantId(tenantId);
        job.setTriggeredBy(SYSTEM_TRIGGERED_BY);
        job.setStatus("pending");
        job.setMode("live");
        job.setReportTime(today);
        job.setCreatedAt(now());
        job.setAgentTaskId("");
        jobRepository.save(job);
        temuAgentService.enqueueCrawlJob(job);

        out.put("action", "enqueued");
        out.put("job", toJobMap(job));
        return out;
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
            jobMap.put("trigger", job.getTriggeredBy() != null && job.getTriggeredBy() == SYSTEM_TRIGGERED_BY
                    ? "daily_schedule"
                    : "manual");
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

    private Optional<TemuCrawlJob> findTodayJob(Long tenantId, String today) {
        Optional<TemuCrawlJob> latest = jobRepository.findFirstByTenantIdOrderByCreatedAtDesc(tenantId);
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

    private TemuCrawlJob createTerminalJob(
            Long tenantId,
            String reportTime,
            String status,
            String errorCode,
            String errorMessage
    ) {
        String now = now();
        TemuCrawlJob job = new TemuCrawlJob();
        job.setId(UUID.randomUUID().toString());
        job.setTenantId(tenantId);
        job.setTriggeredBy(SYSTEM_TRIGGERED_BY);
        job.setStatus(status);
        job.setMode("live");
        job.setReportTime(reportTime);
        job.setErrorCode(errorCode == null ? "" : errorCode);
        job.setErrorMessage(errorMessage == null ? "" : errorMessage);
        job.setCreatedAt(now);
        job.setStartedAt(now);
        job.setFinishedAt(now);
        job.setAgentTaskId("");
        return jobRepository.save(job);
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

    private static String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static String nullToEmpty(String value) {
        return value == null ? "" : value;
    }
}
