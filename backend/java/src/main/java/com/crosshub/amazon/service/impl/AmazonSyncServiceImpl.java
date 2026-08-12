package com.crosshub.amazon.service.impl;

import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.amazon.dto.AmazonSyncRequest;
import com.crosshub.amazon.entity.AmazonSyncJob;
import com.crosshub.amazon.repository.AmazonSyncJobRepository;
import com.crosshub.amazon.service.AmazonOperationalPersistenceService;
import com.crosshub.amazon.service.AmazonSyncConflictException;
import com.crosshub.amazon.service.AmazonSyncService;
import com.crosshub.common.AppErrorCode;
import com.crosshub.common.JobListLimits;
import com.crosshub.platform.entity.PlatformAccount;
import com.crosshub.platform.repository.PlatformAccountRepository;
import com.crosshub.common.TenantCrawlCooldownService;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

@Service
public class AmazonSyncServiceImpl implements AmazonSyncService {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final Set<String> ACTIVE = Set.of("pending", "running");
    private static final Set<String> NEEDS_PRODUCT_ROWS = Set.of("daily", "insights", "reports");
    private static final long RUNNING_TTL_SECONDS = 6 * 60;
    private static final long PENDING_TTL_SECONDS = 3 * 60;
    private static final int MAX_AUTO_RETRY_COUNT = 2;

    private final AmazonSyncJobRepository syncJobRepository;
    private final PlatformAccountRepository platformAccountRepository;
    private final DataScopeService dataScopeService;
    private final ObjectMapper objectMapper;
    private final JdbcTemplate jdbc;
    private final AmazonOperationalPersistenceService persistenceService;
    private final TenantCrawlCooldownService crawlCooldownService;
    private final AgentPresenceService agentPresenceService;

    public AmazonSyncServiceImpl(
            AmazonSyncJobRepository syncJobRepository,
            PlatformAccountRepository platformAccountRepository,
            DataScopeService dataScopeService,
            ObjectMapper objectMapper,
            JdbcTemplate jdbc,
            AmazonOperationalPersistenceService persistenceService,
            TenantCrawlCooldownService crawlCooldownService,
            AgentPresenceService agentPresenceService
    ) {
        this.syncJobRepository = syncJobRepository;
        this.platformAccountRepository = platformAccountRepository;
        this.dataScopeService = dataScopeService;
        this.objectMapper = objectMapper;
        this.jdbc = jdbc;
        this.persistenceService = persistenceService;
        this.crawlCooldownService = crawlCooldownService;
        this.agentPresenceService = agentPresenceService;
    }

    @Transactional
    public Map<String, Object> triggerSync(AmazonSyncRequest request) {
        Long tenantId = dataScopeService.requireTenantId();
        return triggerSyncInternal(tenantId, request);
    }

    @Override
    @Transactional
    public Map<String, Object> triggerSyncForTenant(Long tenantId, AmazonSyncRequest request) {
        if (tenantId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "缺少租户上下文");
        }
        return triggerSyncInternal(tenantId, request);
    }

    private Map<String, Object> triggerSyncInternal(Long tenantId, AmazonSyncRequest request) {
        boolean force = request != null && request.resolvedForce();
        boolean recordCooldown = request == null || request.resolvedRecordCooldown();
        crawlCooldownService.assertAllowed(tenantId, force);
        String scope = normalizeScope(request == null ? null : request.scope());
        List<PlatformAccount> targets = resolveTargets(tenantId, request == null ? null : request.platformAccountId());
        if (targets.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.ACCOUNT_NOT_FOUND.getUserMessage());
        }

        List<Map<String, Object>> jobs = new ArrayList<>();
        for (PlatformAccount account : targets) {
            Optional<AmazonSyncJob> active = syncJobRepository
                    .findFirstByTenantIdAndPlatformAccountIdAndScopeAndStatusInOrderByCreatedAtDesc(
                            tenantId, account.getId(), scope, ACTIVE
                    );
            if (active.isPresent()) {
                AmazonSyncJob existing = reconcileJob(active.get());
                if (ACTIVE.contains(existing.getStatus()) && !isStale(existing)) {
                    throw new AmazonSyncConflictException(existing);
                }
                if (ACTIVE.contains(existing.getStatus())) {
                    markStaleJobFailed(existing);
                }
            }

            AmazonSyncJob job = createPendingJob(tenantId, account, scope, 0, "manual");
            crawlCooldownService.registerJobRecordPolicy(job.getId(), recordCooldown);
            jobs.add(jobDto(job));
        }

        return Map.of("jobs", jobs);
    }

    @Override
    @Transactional
    public Map<String, Object> enqueueDailySync(Long tenantId) {
        return enqueueDailySync(tenantId, false);
    }

    @Override
    @Transactional
    public Map<String, Object> enqueueDailySync(Long tenantId, boolean force) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("platform", "amazon");
        out.put("tenant_id", tenantId);
        out.put("force", force);
        if (tenantId == null) {
            out.put("action", "skipped_invalid_tenant");
            return out;
        }

        String today = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd"));
        if (!force) {
            Optional<AmazonSyncJob> latest = syncJobRepository.findFirstByTenantIdOrderByCreatedAtDesc(tenantId);
            if (latest.isPresent()) {
                AmazonSyncJob job = latest.get();
                String created = job.getCreatedAt() == null ? "" : job.getCreatedAt();
                if (created.startsWith(today)) {
                    out.put("action", "skipped_already_ran");
                    out.put("job", statusJobMap(job));
                    return out;
                }
            }
        }

        List<PlatformAccount> targets = resolveTargets(tenantId, null);
        if (targets.isEmpty()) {
            out.put("action", "skipped_no_accounts");
            return out;
        }

        if (!agentPresenceService.isAgentOnline(tenantId)) {
            List<Map<String, Object>> failedJobs = new ArrayList<>();
            for (PlatformAccount account : targets) {
                AmazonSyncJob failed = createTerminalDailyJob(
                        tenantId,
                        account.getId(),
                        AppErrorCode.TEMU_AGENT_OFFLINE.getCode(),
                        AppErrorCode.TEMU_AGENT_OFFLINE.getUserMessage()
                );
                failedJobs.add(statusJobMap(failed));
            }
            out.put("action", "failed_agent_offline");
            out.put("jobs", failedJobs);
            return out;
        }

        String scope = "account_health";
        List<Map<String, Object>> jobs = new ArrayList<>();
        for (PlatformAccount account : targets) {
            Optional<AmazonSyncJob> active = syncJobRepository
                    .findFirstByTenantIdAndPlatformAccountIdAndScopeAndStatusInOrderByCreatedAtDesc(
                            tenantId, account.getId(), scope, ACTIVE
                    );
            if (active.isPresent()) {
                AmazonSyncJob existing = reconcileJob(active.get());
                if (ACTIVE.contains(existing.getStatus()) && !isStale(existing)) {
                    jobs.add(statusJobMap(existing));
                    continue;
                }
                if (ACTIVE.contains(existing.getStatus())) {
                    markStaleJobFailed(existing);
                }
            }

            AmazonSyncJob job = createPendingJob(tenantId, account, scope, 0, "daily_schedule");
            crawlCooldownService.registerJobRecordPolicy(job.getId(), false);
            jobs.add(statusJobMap(job));
        }
        out.put("action", jobs.isEmpty() ? "skipped_active" : "enqueued");
        out.put("jobs", jobs);
        return out;
    }

    @Override
    public Map<String, Object> buildSyncStatus(Long tenantId) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("platform", "amazon");
        Optional<AmazonSyncJob> latest = syncJobRepository.findFirstByTenantIdOrderByCreatedAtDesc(tenantId);
        if (latest.isEmpty()) {
            out.put("last_job", null);
            out.put("has_error", false);
            out.put("error_code", "");
            out.put("error_message", "");
            return out;
        }
        AmazonSyncJob job = reconcileJob(latest.get());
        Map<String, Object> jobMap = statusJobMap(job);
        String summary = job.getResultSummary() == null ? "" : job.getResultSummary();
        jobMap.put("trigger", summary.contains("daily_schedule") ? "daily_schedule" : "manual");
        out.put("last_job", jobMap);
        boolean failed = "failed".equalsIgnoreCase(job.getStatus());
        out.put("has_error", failed);
        out.put("error_code", failed ? defaultText(job.getErrorCode(), "") : "");
        out.put("error_message", failed ? defaultText(job.getErrorMessage(), "") : "");
        return out;
    }

    @Override
    public Map<String, Object> listRecentJobsForTenant(Long tenantId, Integer limit) {
        int n = JobListLimits.clamp(limit);
        List<AmazonSyncJob> jobs = syncJobRepository.findTop60ByTenantIdOrderByCreatedAtDesc(tenantId);
        List<Map<String, Object>> items = new ArrayList<>();
        int unread = 0;
        for (AmazonSyncJob raw : jobs) {
            AmazonSyncJob job = reconcileJob(raw);
            Map<String, Object> summary = readMap(job.getResultSummary());
            PlatformAccount account = platformAccountRepository.findByIdAndTenantId(job.getPlatformAccountId(), tenantId).orElse(null);
            int retryCount = readInt(summary.get("retry_count"), 0);
            int maxRetryCount = readInt(summary.get("max_retry_count"), MAX_AUTO_RETRY_COUNT);
            boolean retryExhausted = Boolean.TRUE.equals(summary.get("retry_exhausted"));
            if ("failed".equalsIgnoreCase(job.getStatus()) && retryExhausted) {
                unread++;
            }
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("job_id", job.getId());
            item.put("platform_account_id", job.getPlatformAccountId());
            item.put("agent_task_id", job.getAgentTaskId());
            item.put("scope", job.getScope());
            item.put("status", job.getStatus());
            item.put("store_name", account == null ? "" : defaultText(account.getStoreName(), ""));
            item.put("account", account == null ? "" : defaultText(account.getAccount(), ""));
            item.put("created_at", defaultText(job.getCreatedAt(), ""));
            item.put("started_at", defaultText(job.getStartedAt(), ""));
            item.put("finished_at", defaultText(job.getFinishedAt(), ""));
            item.put("retry_count", retryCount);
            item.put("max_retry_count", maxRetryCount);
            item.put("retry_exhausted", retryExhausted);
            item.put("failed_at", defaultText(String.valueOf(summary.getOrDefault("last_failed_at", "")), defaultText(job.getFinishedAt(), "")));
            item.put("failure_code", defaultText(String.valueOf(summary.getOrDefault("last_error_code", "")), defaultText(job.getErrorCode(), "")));
            item.put("failure_reason", defaultText(String.valueOf(summary.getOrDefault("last_error_message", "")), defaultText(job.getErrorMessage(), "")));
            if (summary.containsKey("products_count") || summary.containsKey("product_count")) {
                item.put("products_count", readInt(summary.getOrDefault("products_count", summary.get("product_count")), 0));
            }
            if (summary.containsKey("item_count") || summary.containsKey("items_count")) {
                item.put("item_count", readInt(summary.getOrDefault("item_count", summary.get("items_count")), 0));
            }
            if (summary.containsKey("metric_count")) {
                item.put("metric_count", readInt(summary.get("metric_count"), 0));
            }
            if (summary.containsKey("trigger")) {
                item.put("trigger", String.valueOf(summary.get("trigger")));
            }
            items.add(item);
        }
        items = items.subList(0, Math.min(n, items.size()));
        return Map.of("items", items, "unread", unread);
    }

    private AmazonSyncJob createTerminalDailyJob(Long tenantId, String accountId, String errorCode, String errorMessage) {
        String now = now();
        AmazonSyncJob job = new AmazonSyncJob();
        job.setId("amz_sync_" + UUID.randomUUID());
        job.setTenantId(tenantId);
        job.setPlatformAccountId(accountId);
        job.setAgentTaskId("");
        job.setAgentId("");
        job.setScope("account_health");
        job.setStatus("failed");
        job.setMode("ziniao_webdriver");
        job.setErrorCode(errorCode == null ? "" : errorCode);
        job.setErrorMessage(errorMessage == null ? "" : errorMessage);
        job.setResultSummary("{\"trigger\":\"daily_schedule\"}");
        job.setCreatedAt(now);
        job.setStartedAt(now);
        job.setFinishedAt(now);
        return syncJobRepository.save(job);
    }

    private Map<String, Object> statusJobMap(AmazonSyncJob job) {
        Map<String, Object> map = jobDto(job);
        map.put("platform_account_id", job.getPlatformAccountId());
        return map;
    }

    @Override
    public AmazonSyncJob getJob(String jobId) {
        Long tenantId = dataScopeService.requireTenantId();
        AmazonSyncJob job = syncJobRepository.findByIdAndTenantId(jobId, tenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, AppErrorCode.AMAZON_SYNC_JOB_NOT_FOUND.getUserMessage()));
        return reconcileJob(job);
    }

    @Override
    @Transactional
    public void onAgentTaskStarted(String taskId) {
        AmazonSyncJob job = findJobByAgentTaskId(taskId);
        if (job == null || !ACTIVE.contains(job.getStatus())) {
            return;
        }
        if (!"running".equals(job.getStatus())) {
            job.setStatus("running");
        }
        if (job.getStartedAt() == null || job.getStartedAt().isBlank()) {
            job.setStartedAt(now());
        }
        syncJobRepository.save(job);
    }

    @Override
    @Transactional
    public void onAgentTaskCompleted(String taskId, String status, Map<String, Object> result, String errorCode, String errorMessage) {
        if (taskId == null || taskId.isBlank()) {
            return;
        }
        AmazonSyncJob job = findJobByAgentTaskId(taskId);
        if (job == null) {
            return;
        }
        if (!ACTIVE.contains(job.getStatus())) {
            return;
        }

        if (!"running".equals(job.getStatus())) {
            job.setStatus("running");
            if (job.getStartedAt() == null || job.getStartedAt().isBlank()) {
                job.setStartedAt(now());
            }
        }

        if (!"success".equalsIgnoreCase(status)) {
            Map<String, Object> previousSummary = readMap(job.getResultSummary());
            int retryCount = readInt(previousSummary.get("retry_count"), 0);
            String trigger = defaultText(String.valueOf(previousSummary.getOrDefault("trigger", "")), "manual");
            job.setStatus("failed");
            String finalErrorCode = defaultText(errorCode, AppErrorCode.AMAZON_SYNC_FAILED.getCode());
            String finalErrorMessage = defaultText(errorMessage, AppErrorCode.AMAZON_SYNC_FAILED.getUserMessage());
            job.setErrorCode(finalErrorCode);
            job.setErrorMessage(finalErrorMessage);
            job.setFinishedAt(now());
            boolean retryScheduled = false;
            String retryTaskId = "";
            if (retryCount < MAX_AUTO_RETRY_COUNT) {
                PlatformAccount account = platformAccountRepository.findByIdAndTenantId(job.getPlatformAccountId(), job.getTenantId()).orElse(null);
                if (account != null) {
                    AmazonSyncJob retryJob = createPendingJob(
                            job.getTenantId(),
                            account,
                            job.getScope(),
                            retryCount + 1,
                            trigger
                    );
                    crawlCooldownService.registerJobRecordPolicy(retryJob.getId(), false);
                    retryTaskId = retryJob.getAgentTaskId();
                    retryScheduled = true;
                }
            }
            Map<String, Object> summary = new LinkedHashMap<>();
            summary.put("trigger", trigger);
            summary.put("retry_count", retryCount);
            summary.put("max_retry_count", MAX_AUTO_RETRY_COUNT);
            summary.put("retry_scheduled", retryScheduled);
            summary.put("retry_exhausted", !retryScheduled && retryCount >= MAX_AUTO_RETRY_COUNT);
            summary.put("last_error_code", finalErrorCode);
            summary.put("last_error_message", finalErrorMessage);
            summary.put("last_failed_at", job.getFinishedAt());
            if (!retryTaskId.isBlank()) {
                summary.put("next_task_id", retryTaskId);
            }
            job.setResultSummary(writeJson(summary));
            syncJobRepository.save(job);
            return;
        }

        Map<String, Object> safe = result == null ? Map.of() : result;
        Map<String, Object> previousSummary = readMap(job.getResultSummary());
        persistenceService.persistSyncResult(job, safe);

        Map<String, Object> summary = readMap(safe.get("summary"));
        if (summary.isEmpty()) {
            summary = readMap(safe.get("result_summary"));
        }
        if (summary.isEmpty()) {
            summary = Map.of("products_count", sizeOf(safe.get("products")));
        }

        boolean noProducts = NEEDS_PRODUCT_ROWS.contains(job.getScope()) && extractProductsCount(summary) <= 0;
        boolean partialSources = hasPartialSourceWarnings(job.getScope(), summary);
        boolean partial = noProducts || partialSources;
        job.setStatus(partial ? "partial" : "success");
        if (noProducts) {
            job.setErrorCode(AppErrorCode.AMAZON_NO_PRODUCT_ROWS.getCode());
            job.setErrorMessage(AppErrorCode.AMAZON_NO_PRODUCT_ROWS.getUserMessage());
        } else if (partialSources) {
            job.setErrorCode(AppErrorCode.AMAZON_SYNC_PARTIAL.getCode());
            job.setErrorMessage(partialSourceMessage(summary));
        } else {
            job.setErrorCode("");
            job.setErrorMessage("");
        }
        summary = new LinkedHashMap<>(summary);
        summary.put("trigger", defaultText(String.valueOf(previousSummary.getOrDefault("trigger", "")), "manual"));
        summary.put("retry_count", readInt(previousSummary.get("retry_count"), 0));
        summary.put("max_retry_count", MAX_AUTO_RETRY_COUNT);
        summary.put("retry_exhausted", false);
        job.setResultSummary(writeJson(summary));
        job.setFinishedAt(now());
        persistenceService.finalizeSyncVersion(job.getId(), job.getStatus(), job.getResultSummary());
        syncJobRepository.save(job);
        if ("success".equals(job.getStatus()) || "partial".equals(job.getStatus())) {
            crawlCooldownService.onJobSuccess(job.getId(), job.getTenantId());
        }
    }

    private List<PlatformAccount> resolveTargets(Long tenantId, String platformAccountId) {
        List<PlatformAccount> source;
        if (platformAccountId != null && !platformAccountId.isBlank()) {
            PlatformAccount one = platformAccountRepository.findByIdAndTenantId(platformAccountId, tenantId)
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, AppErrorCode.ACCOUNT_NOT_FOUND.getUserMessage()));
            source = List.of(one);
        } else {
            source = platformAccountRepository.findByTenantIdAndPlatformOrderByBoundAtDesc(tenantId, "amazon");
        }

        Map<String, PlatformAccount> deduped = new LinkedHashMap<>();
        for (PlatformAccount account : source) {
            if (!"amazon".equalsIgnoreCase(account.getPlatform())) {
                continue;
            }
            String external = account.getExternalShopId() == null ? "" : account.getExternalShopId().trim();
            String key = external.isBlank() ? account.getId() : external;
            deduped.putIfAbsent(key, account);
        }
        return new ArrayList<>(deduped.values());
    }

    private AmazonSyncJob createPendingJob(Long tenantId, PlatformAccount account, String scope, int retryCount, String trigger) {
        String taskId = "agt_" + UUID.randomUUID();
        AmazonSyncJob job = new AmazonSyncJob();
        job.setId("amz_sync_" + UUID.randomUUID());
        job.setTenantId(tenantId);
        job.setPlatformAccountId(account.getId());
        job.setAgentTaskId(taskId);
        job.setAgentId("");
        job.setScope(scope);
        job.setStatus("pending");
        job.setMode("ziniao_webdriver");
        job.setCreatedAt(now());
        job.setResultSummary(writeJson(new LinkedHashMap<>(Map.of(
                "trigger", trigger == null || trigger.isBlank() ? "manual" : trigger,
                "retry_count", Math.max(0, retryCount),
                "max_retry_count", MAX_AUTO_RETRY_COUNT,
                "retry_exhausted", false
        ))));
        syncJobRepository.save(job);
        enqueueAgentTask(tenantId, taskId, scope, account, retryCount);
        return job;
    }

    private void enqueueAgentTask(Long tenantId, String taskId, String scope, PlatformAccount account) {
        enqueueAgentTask(tenantId, taskId, scope, account, 0);
    }

    private void enqueueAgentTask(Long tenantId, String taskId, String scope, PlatformAccount account, int retryCount) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("scope", scope);
        payload.put("platform", "amazon");
        payload.put("platform_account_id", account.getId());
        payload.put("external_shop_id", defaultText(account.getExternalShopId(), ""));
        payload.put("browser_id", defaultText(account.getExternalShopId(), ""));
        payload.put("browser_oauth", defaultText(account.getZiniaoBrowserOauth(), ""));
        payload.put("store_name", defaultText(account.getStoreName(), ""));
        payload.put("merchant_id", defaultText(account.getAmazonMerchantId(), ""));
        payload.put("retry_count", Math.max(0, retryCount));

        jdbc.update(
                """
                INSERT INTO agent_task (
                  id, tenant_id, agent_id, task_type, status, payload_json, result_json,
                  error_code, error_message, created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                taskId, tenantId, "", "amazon_sync", "pending",
                writeJson(payload), "{}", "", "", now(), "", ""
        );
    }

    private String normalizeScope(String scope) {
        String s = scope == null || scope.isBlank() ? "account_health" : scope.trim().toLowerCase(Locale.ROOT);
        return switch (s) {
            case "account_health", "daily", "insights", "reports", "full" -> s;
            default -> throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.BAD_REQUEST.getUserMessage());
        };
    }

    private AmazonSyncJob reconcileJob(AmazonSyncJob job) {
        if (job == null) {
            return null;
        }
        syncJobStatusFromAgentTask(job);
        if (ACTIVE.contains(job.getStatus()) && isStale(job)) {
            markStaleJobFailed(job);
        }
        return job;
    }

    private void syncJobStatusFromAgentTask(AmazonSyncJob job) {
        String agentTaskId = job.getAgentTaskId();
        if (agentTaskId == null || agentTaskId.isBlank()) {
            return;
        }
        List<Map<String, Object>> rows = jdbc.query(
                """
                SELECT status, started_at, error_code, error_message
                FROM agent_task
                WHERE id = ? AND tenant_id = ?
                LIMIT 1
                """,
                (rs, rowNum) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("status", rs.getString("status"));
                    row.put("started_at", rs.getString("started_at"));
                    row.put("error_code", rs.getString("error_code"));
                    row.put("error_message", rs.getString("error_message"));
                    return row;
                },
                agentTaskId,
                job.getTenantId()
        );
        if (rows.isEmpty() || !ACTIVE.contains(job.getStatus())) {
            return;
        }

        String agentStatus = String.valueOf(rows.get(0).get("status"));
        String agentStartedAt = String.valueOf(rows.get(0).getOrDefault("started_at", ""));
        if ("running".equals(agentStatus)) {
            job.setStatus("running");
            if (!agentStartedAt.isBlank()) {
                job.setStartedAt(agentStartedAt);
            } else if (job.getStartedAt() == null || job.getStartedAt().isBlank()) {
                job.setStartedAt(now());
            }
            syncJobRepository.save(job);
            return;
        }
        if ("failed".equals(agentStatus)) {
            job.setStatus("failed");
            job.setStartedAt(agentStartedAt.isBlank() ? defaultText(job.getStartedAt(), now()) : agentStartedAt);
            job.setFinishedAt(now());
            job.setErrorCode(defaultText(String.valueOf(rows.get(0).get("error_code")), AppErrorCode.AMAZON_SYNC_FAILED.getCode()));
            job.setErrorMessage(defaultText(String.valueOf(rows.get(0).get("error_message")), AppErrorCode.AMAZON_SYNC_FAILED.getUserMessage()));
            syncJobRepository.save(job);
        }
    }

    private AmazonSyncJob findJobByAgentTaskId(String taskId) {
        return syncJobRepository.findFirstByAgentTaskId(taskId).orElse(null);
    }

    private boolean isStale(AmazonSyncJob job) {
        LocalDateTime base = parseTime("running".equals(job.getStatus()) ? job.getStartedAt() : job.getCreatedAt());
        if (base == null) {
            return true;
        }
        long ttl = "running".equals(job.getStatus()) ? RUNNING_TTL_SECONDS : PENDING_TTL_SECONDS;
        return base.plusSeconds(ttl).isBefore(LocalDateTime.now());
    }

    private void markStaleJobFailed(AmazonSyncJob job) {
        job.setStatus("failed");
        job.setErrorCode(AppErrorCode.CRAWL_INTERRUPTED.getCode());
        job.setErrorMessage(AppErrorCode.CRAWL_INTERRUPTED.getUserMessage());
        job.setFinishedAt(now());
        syncJobRepository.save(job);
    }

    private LocalDateTime parseTime(String text) {
        if (text == null || text.isBlank()) {
            return null;
        }
        try {
            return LocalDateTime.parse(text, TS);
        } catch (Exception ex) {
            return null;
        }
    }

    private Map<String, Object> jobDto(AmazonSyncJob job) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("job_id", job.getId());
        out.put("platform_account_id", job.getPlatformAccountId());
        out.put("agent_task_id", job.getAgentTaskId());
        out.put("scope", job.getScope());
        out.put("status", job.getStatus());
        out.put("mode", job.getMode());
        return out;
    }

    private Map<String, Object> readMap(Object value) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> out = new LinkedHashMap<>();
            for (Map.Entry<?, ?> e : map.entrySet()) {
                out.put(String.valueOf(e.getKey()), e.getValue());
            }
            return out;
        }
        if (value instanceof String text && !text.isBlank()) {
            try {
                return objectMapper.readValue(text, new TypeReference<>() {});
            } catch (Exception ignored) {
                return Map.of();
            }
        }
        return Map.of();
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception ex) {
            return "{}";
        }
    }

    private int extractProductsCount(Map<String, Object> summary) {
        Object val = summary.get("products_count");
        if (val == null) {
            val = summary.get("productsCount");
        }
        if (val instanceof Number n) {
            return n.intValue();
        }
        if (val instanceof String text) {
            try {
                return Integer.parseInt(text.trim());
            } catch (Exception ignored) {
                return 0;
            }
        }
        return 0;
    }

    private int readInt(Object val, int fallback) {
        if (val instanceof Number n) {
            return n.intValue();
        }
        if (val instanceof String text) {
            try {
                return Integer.parseInt(text.trim());
            } catch (Exception ignored) {
                return fallback;
            }
        }
        return fallback;
    }

    private int sizeOf(Object value) {
        return value instanceof Collection<?> c ? c.size() : 0;
    }

    private boolean hasPartialSourceWarnings(String scope, Map<String, Object> summary) {
        if (scope == null || (!"reports".equals(scope) && !"insights".equals(scope))) {
            return false;
        }
        if (extractProductsCount(summary) <= 0) {
            return false;
        }
        Map<String, Object> quality = readMap(summary.get("data_quality"));
        for (String warning : readStringList(quality.get("warnings"))) {
            if ("ADS_CSV_EMPTY".equals(warning) || "INV_CSV_EMPTY".equals(warning)) {
                return true;
            }
        }
        return false;
    }

    private String partialSourceMessage(Map<String, Object> summary) {
        Map<String, Object> quality = readMap(summary.get("data_quality"));
        List<String> parts = new ArrayList<>();
        for (String warning : readStringList(quality.get("warnings"))) {
            if ("ADS_CSV_EMPTY".equals(warning)) {
                parts.add("广告 ASIN 报表");
            } else if ("INV_CSV_EMPTY".equals(warning)) {
                parts.add("库存导出");
            }
        }
        if (parts.isEmpty()) {
            return AppErrorCode.AMAZON_SYNC_PARTIAL.getUserMessage();
        }
        return "产品数据已同步，但以下数据源未采集完整：" + String.join("、", parts);
    }

    private List<String> readStringList(Object value) {
        if (value instanceof Collection<?> collection) {
            List<String> out = new ArrayList<>();
            for (Object item : collection) {
                if (item != null) {
                    String text = String.valueOf(item).trim();
                    if (!text.isBlank()) {
                        out.add(text);
                    }
                }
            }
            return out;
        }
        return List.of();
    }

    private String defaultText(String text, String fallback) {
        return text == null || text.isBlank() ? fallback : text;
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }
}
