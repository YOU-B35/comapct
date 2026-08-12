package com.crosshub.aliexpress.service.impl;

import com.crosshub.aliexpress.dto.AliExpressCrawlRequest;
import com.crosshub.aliexpress.entity.AliExpressCrawlJob;
import com.crosshub.aliexpress.repository.AliExpressCrawlJobRepository;
import com.crosshub.aliexpress.service.AliExpressCrawlConflictException;
import com.crosshub.aliexpress.service.AliExpressCrawlService;
import com.crosshub.common.AppErrorCode;
import com.crosshub.common.JobListLimits;
import com.crosshub.common.SqliteRetry;
import com.crosshub.config.CrawlerProperties;
import com.crosshub.security.AuthContext;
import com.crosshub.common.TenantCrawlCooldownService;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.web.server.ResponseStatusException;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

@Service
public class AliExpressCrawlServiceImpl implements AliExpressCrawlService {
    private static final Logger log = LoggerFactory.getLogger(AliExpressCrawlServiceImpl.class);
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final Set<String> ACTIVE_STATUSES = Set.of("pending", "running");
    private static final long PENDING_TTL_SECONDS = 5 * 60;

    private final AliExpressCrawlJobRepository jobRepository;
    private final DataScopeService dataScopeService;
    private final AuthContext authContext;
    private final CrawlerProperties crawlerProperties;
    private final ObjectMapper objectMapper;
    private final Executor crawlJobExecutor;
    private final Executor crawlExecutor;
    private final TenantCrawlCooldownService crawlCooldownService;

    public AliExpressCrawlServiceImpl(
            AliExpressCrawlJobRepository jobRepository,
            DataScopeService dataScopeService,
            AuthContext authContext,
            CrawlerProperties crawlerProperties,
            ObjectMapper objectMapper,
            @Qualifier("crawlJobExecutor") Executor crawlJobExecutor,
            @Qualifier("crawlExecutor") Executor crawlExecutor,
            TenantCrawlCooldownService crawlCooldownService
    ) {
        this.jobRepository = jobRepository;
        this.dataScopeService = dataScopeService;
        this.authContext = authContext;
        this.crawlerProperties = crawlerProperties;
        this.objectMapper = objectMapper;
        this.crawlJobExecutor = crawlJobExecutor;
        this.crawlExecutor = crawlExecutor;
        this.crawlCooldownService = crawlCooldownService;
    }

    @Override
    @Transactional
    public AliExpressCrawlJob triggerCrawl(AliExpressCrawlRequest request) {
        String scope = request == null ? "all" : request.resolvedScope();
        String reportTime = request == null ? null : request.reportTime();
        boolean force = request != null && request.resolvedForce();
        boolean recordCooldown = request == null || request.resolvedRecordCooldown();
        return createJob(reportTime, scope, force, recordCooldown);
    }

    @Override
    @Transactional
    public AliExpressCrawlJob triggerViolationSync() {
        return triggerViolationSync(false);
    }

    @Override
    @Transactional
    public AliExpressCrawlJob triggerViolationSync(boolean force) {
        return triggerViolationSync(force, true);
    }

    @Override
    @Transactional
    public AliExpressCrawlJob triggerViolationSync(boolean force, boolean recordCooldown) {
        return createJob(null, "violations", force, recordCooldown);
    }

    @Override
    public AliExpressCrawlJob getJob(String jobId) {
        Long tenantId = dataScopeService.requireTenantId();
        AliExpressCrawlJob job = jobRepository.findByIdAndTenantId(jobId, tenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, AppErrorCode.CRAWL_JOB_NOT_FOUND.getUserMessage()));
        return reconcileStaleJob(job);
    }

    public static int clampJobListLimit(Integer limit) {
        return JobListLimits.clamp(limit);
    }

    @Override
    public List<AliExpressCrawlJob> listRecentJobs(int limit) {
        Long tenantId = dataScopeService.requireTenantId();
        int n = clampJobListLimit(limit);
        List<AliExpressCrawlJob> all = jobRepository.findTop60ByTenantIdOrderByCreatedAtDesc(tenantId);
        if (all.size() <= n) {
            return all;
        }
        return all.subList(0, n);
    }

    private AliExpressCrawlJob createJob(String reportTime, String scope, boolean force, boolean recordCooldown) {
        Long tenantId = dataScopeService.requireTenantId();
        crawlCooldownService.assertAllowed(tenantId, force);
        Long userId = authContext.userId();
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, AppErrorCode.AUTH_MISSING_USER.getUserMessage());
        }
        return createJobForTenant(tenantId, userId, reportTime, scope, force, recordCooldown);
    }

    /**
     * 全平台日批：不依赖 JWT。force=true 跳过冷却；triggeredBy=0 表示系统触发。
     */
    @Override
    @Transactional
    public Map<String, Object> enqueueDailyCrawl(Long tenantId) {
        return enqueueDailyCrawl(tenantId, false);
    }

    @Override
    @Transactional
    public Map<String, Object> enqueueDailyCrawl(Long tenantId, boolean force) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("platform", "aliexpress");
        out.put("tenant_id", tenantId);
        out.put("force", force);
        if (tenantId == null) {
            out.put("action", "skipped_invalid_tenant");
            return out;
        }
        String today = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd"));
        if (!force) {
            Optional<AliExpressCrawlJob> latest = jobRepository.findFirstByTenantIdOrderByCreatedAtDesc(tenantId);
            if (latest.isPresent()) {
                AliExpressCrawlJob job = latest.get();
                String created = job.getCreatedAt() == null ? "" : job.getCreatedAt();
                if (created.startsWith(today)) {
                    out.put("action", "skipped_already_ran");
                    out.put("job", toStatusJobMap(job));
                    return out;
                }
            }
        }
        Optional<AliExpressCrawlJob> active = jobRepository.findFirstByTenantIdAndStatusInOrderByCreatedAtDesc(
                tenantId, ACTIVE_STATUSES
        );
        if (active.isPresent()) {
            AliExpressCrawlJob existing = reconcileStaleJob(active.get());
            if (ACTIVE_STATUSES.contains(existing.getStatus())) {
                out.put("action", "skipped_active");
                out.put("job", toStatusJobMap(existing));
                return out;
            }
        }
        AliExpressCrawlJob job = createJobForTenant(tenantId, 0L, today, "all", true, false);
        out.put("action", "enqueued");
        out.put("job", toStatusJobMap(job));
        return out;
    }

    @Override
    public Map<String, Object> buildSyncStatus(Long tenantId) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("platform", "aliexpress");
        Optional<AliExpressCrawlJob> latest = jobRepository.findFirstByTenantIdOrderByCreatedAtDesc(tenantId);
        if (latest.isEmpty()) {
            out.put("last_job", null);
            out.put("has_error", false);
            out.put("error_code", "");
            out.put("error_message", "");
            return out;
        }
        AliExpressCrawlJob job = latest.get();
        Map<String, Object> jobMap = toStatusJobMap(job);
        jobMap.put("trigger", job.getTriggeredBy() != null && job.getTriggeredBy() == 0L
                ? "daily_schedule"
                : "manual");
        out.put("last_job", jobMap);
        boolean failed = "failed".equalsIgnoreCase(job.getStatus());
        out.put("has_error", failed);
        out.put("error_code", failed ? nullToEmpty(job.getErrorCode()) : "");
        out.put("error_message", failed ? nullToEmpty(job.getErrorMessage()) : "");
        return out;
    }

    private AliExpressCrawlJob createJobForTenant(
            Long tenantId,
            Long triggeredBy,
            String reportTime,
            String scope,
            boolean force,
            boolean recordCooldown
    ) {
        crawlCooldownService.assertAllowed(tenantId, force);
        Optional<AliExpressCrawlJob> active = jobRepository.findFirstByTenantIdAndStatusInOrderByCreatedAtDesc(
                tenantId, ACTIVE_STATUSES
        );
        if (active.isPresent()) {
            AliExpressCrawlJob existing = reconcileStaleJob(active.get());
            if (ACTIVE_STATUSES.contains(existing.getStatus())) {
                throw new AliExpressCrawlConflictException(existing);
            }
        }

        AliExpressCrawlJob job = new AliExpressCrawlJob();
        job.setId(UUID.randomUUID().toString());
        job.setTenantId(tenantId);
        job.setTriggeredBy(triggeredBy == null ? 0L : triggeredBy);
        job.setStatus("pending");
        job.setMode("live");
        job.setScope(scope);
        job.setReportTime(reportTime);
        job.setCreatedAt(now());
        jobRepository.save(job);
        crawlCooldownService.registerJobRecordPolicy(job.getId(), recordCooldown);

        String jobId = job.getId();
        scheduleAfterCommit(() -> crawlJobExecutor.execute(() -> executeJob(jobId)));
        return job;
    }

    private Map<String, Object> toStatusJobMap(AliExpressCrawlJob job) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("id", job.getId());
        map.put("status", job.getStatus());
        map.put("mode", job.getMode());
        map.put("scope", job.getScope());
        map.put("report_time", job.getReportTime());
        map.put("error_code", job.getErrorCode());
        map.put("error_message", job.getErrorMessage());
        map.put("created_at", job.getCreatedAt());
        map.put("started_at", job.getStartedAt());
        map.put("finished_at", job.getFinishedAt());
        map.put("rows_count", job.getRowsCount());
        map.put("shops_count", job.getShopsCount());
        map.put("orders_count", job.getOrdersCount());
        map.put("products_count", job.getProductsCount());
        map.put("violations_count", job.getViolationsCount());
        map.put("triggered_by", job.getTriggeredBy());
        return map;
    }

    private static String nullToEmpty(String value) {
        return value == null ? "" : value;
    }

    private void scheduleAfterCommit(Runnable task) {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    task.run();
                }
            });
            return;
        }
        task.run();
    }

    void executeJob(String jobId) {
        AliExpressCrawlJob job = null;
        try {
            job = jobRepository.findById(jobId).orElse(null);
            if (job == null) {
                return;
            }

            job.setStatus("running");
            job.setStartedAt(now());
            persistJob(job);

            runCrawlProcess(job);
        } catch (Exception ex) {
            log.error("AliExpress crawl job {} failed", jobId, ex);
            if (job != null) {
                AppErrorCode code = SqliteRetry.isLockConflict(ex)
                        ? AppErrorCode.CRAWL_DB_BUSY
                        : AppErrorCode.classifyCrawlRaw(ex.getMessage());
                String raw = ex.getMessage() == null ? "爬取进程异常" : ex.getMessage();
                failJob(job, code, raw);
            }
        }
    }

    private void runCrawlProcess(AliExpressCrawlJob job) throws Exception {
        String jobId = job.getId();
        Path scriptDir = Path.of(crawlerProperties.getScriptDir()).toAbsolutePath().normalize();
        if (!Files.isDirectory(scriptDir)) {
            failJob(job, AppErrorCode.CRAWL_SCRIPT_MISSING, "Python 脚本目录不存在: " + scriptDir);
            return;
        }

        List<String> command = new ArrayList<>();
        command.add(crawlerProperties.getPythonExecutable());
        command.add("operational_crawl.py");
        command.add("--platform");
        command.add("aliexpress");
        command.add("--tenant-id");
        command.add(String.valueOf(job.getTenantId()));
        command.add("--scope");
        command.add(normalizeScope(job.getScope()));
        command.add("--json");
        if (job.getReportTime() != null && !job.getReportTime().isBlank()) {
            command.add("--date");
            command.add(job.getReportTime());
        }

        ProcessBuilder builder = new ProcessBuilder(command);
        builder.directory(scriptDir.toFile());
        builder.environment().put("TENANT_ID", String.valueOf(job.getTenantId()));
        builder.environment().put("PYTHONIOENCODING", "utf-8");
        builder.environment().put("PYTHONUTF8", "1");
        builder.redirectErrorStream(false);

        Process process = builder.start();
        CompletableFuture<String> stdoutFuture = CompletableFuture.supplyAsync(
                () -> safeReadStream(process.getInputStream()),
                crawlExecutor
        );
        CompletableFuture<String> stderrFuture = CompletableFuture.supplyAsync(
                () -> safeReadStream(process.getErrorStream()),
                crawlExecutor
        );
        boolean finished = process.waitFor(crawlerProperties.getTimeoutSeconds(), TimeUnit.SECONDS);
        if (!finished) {
            process.destroyForcibly();
            stdoutFuture.cancel(true);
            stderrFuture.cancel(true);
            failJob(job, AppErrorCode.CRAWL_TIMEOUT, "爬取超时（" + crawlerProperties.getTimeoutSeconds() + "s）");
            return;
        }
        String stdout = "";
        String stderr = "";
        try {
            stdout = stdoutFuture.get(3, TimeUnit.SECONDS);
        } catch (TimeoutException ignored) {
            stdoutFuture.cancel(true);
        }
        try {
            stderr = stderrFuture.get(3, TimeUnit.SECONDS);
        } catch (TimeoutException ignored) {
            stderrFuture.cancel(true);
        }
        if (process.exitValue() != 0) {
            String raw = combineOutput(stderr, stdout);
            failJob(job, AppErrorCode.classifyCrawlRaw(raw), raw);
            return;
        }

        JsonNode json = parseJsonLine(stdout);
        if (json != null) {
            if (json.has("report_time")) {
                job.setReportTime(json.get("report_time").asText(""));
            }
            if (json.has("shops")) {
                job.setShopsCount(json.get("shops").asInt(0));
            }
            if (json.has("rows")) {
                job.setRowsCount(json.get("rows").asInt(0));
            }
            if (json.has("orders")) {
                job.setOrdersCount(json.get("orders").asInt(0));
            }
            if (json.has("violations")) {
                job.setViolationsCount(json.get("violations").asInt(0));
            }
            if (json.has("products")) {
                job.setProductsCount(json.get("products").asInt(0));
            }
        }

        job.setStatus("success");
        job.setFinishedAt(now());
        job.setErrorCode("");
        job.setErrorMessage("");
        persistJob(job);
        crawlCooldownService.onJobSuccess(job.getId(), job.getTenantId());
    }

    private AliExpressCrawlJob reconcileStaleJob(AliExpressCrawlJob job) {
        if (job == null || !ACTIVE_STATUSES.contains(job.getStatus())) {
            return job;
        }
        if (!isStale(job)) {
            return job;
        }
        markStaleJobFailed(job);
        return job;
    }

    private boolean isStale(AliExpressCrawlJob job) {
        LocalDateTime base = parseTime("running".equals(job.getStatus()) ? job.getStartedAt() : job.getCreatedAt());
        if (base == null) {
            return true;
        }
        long ttl = "running".equals(job.getStatus())
                ? crawlerProperties.getTimeoutSeconds() + 60L
                : PENDING_TTL_SECONDS;
        return base.plusSeconds(ttl).isBefore(LocalDateTime.now());
    }

    private void markStaleJobFailed(AliExpressCrawlJob job) {
        job.setStatus("failed");
        job.setFinishedAt(now());
        job.setErrorCode(AppErrorCode.CRAWL_INTERRUPTED.getCode());
        job.setErrorMessage(AppErrorCode.CRAWL_INTERRUPTED.getUserMessage());
        persistJobQuietly(job);
        log.warn("AliExpress crawl job {} marked stale -> failed", job.getId());
    }

    private void persistJob(AliExpressCrawlJob job) {
        SqliteRetry.runWithRetry(() -> jobRepository.save(job));
    }

    private void persistJobQuietly(AliExpressCrawlJob job) {
        try {
            persistJob(job);
        } catch (Exception ex) {
            log.error("AliExpress crawl job {} persist failed", job.getId(), ex);
        }
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

    private String normalizeScope(String scope) {
        String value = scope == null || scope.isBlank() ? "all" : scope.trim().toLowerCase(Locale.ROOT);
        return switch (value) {
            case "all", "orders", "violations", "operational" -> value;
            default -> "all";
        };
    }

    private void failJob(AliExpressCrawlJob job, AppErrorCode code, String raw) {
        if (hasPersistedPayload(job)) {
            partialJob(job, code, raw);
            return;
        }
        job.setStatus("failed");
        job.setFinishedAt(now());
        job.setErrorCode(code.getCode());
        job.setErrorMessage(code.getUserMessage());
        persistJobQuietly(job);
        log.warn("AliExpress crawl job {} failed [{}]: {}", job.getId(), code.getCode(), trimMessage(raw));
    }

    private void partialJob(AliExpressCrawlJob job, AppErrorCode code, String raw) {
        job.setStatus("partial");
        job.setFinishedAt(now());
        job.setErrorCode(code.getCode());
        job.setErrorMessage("爬取已完成，但任务收尾异常，页面数据可能已更新");
        persistJobQuietly(job);
        log.warn("AliExpress crawl job {} partial [{}]: {}", job.getId(), code.getCode(), trimMessage(raw));
    }

    private boolean hasPersistedPayload(AliExpressCrawlJob job) {
        if (job.getRowsCount() != null && job.getRowsCount() > 0) {
            return true;
        }
        if (job.getOrdersCount() != null && job.getOrdersCount() > 0) {
            return true;
        }
        if (job.getViolationsCount() != null && job.getViolationsCount() > 0) {
            return true;
        }
        return job.getProductsCount() != null && job.getProductsCount() > 0;
    }

    private JsonNode parseJsonLine(String stdout) {
        if (stdout == null || stdout.isBlank()) {
            return null;
        }
        for (String line : stdout.split("\\R")) {
            String trimmed = line.trim();
            if (!trimmed.startsWith("{")) {
                continue;
            }
            try {
                return objectMapper.readTree(trimmed);
            } catch (Exception ignored) {
                // continue
            }
        }
        return null;
    }

    private String combineOutput(String stderr, String stdout) {
        if (stderr != null && !stderr.isBlank()) {
            return stderr;
        }
        return stdout == null ? "" : stdout;
    }

    private String readStream(java.io.InputStream stream) throws Exception {
        byte[] bytes = stream.readAllBytes();
        if (bytes.length == 0) {
            return "";
        }
        String utf8 = new String(bytes, StandardCharsets.UTF_8);
        if (!utf8.contains("\uFFFD")) {
            return utf8;
        }
        return new String(bytes, java.nio.charset.Charset.forName("GBK"));
    }

    private String safeReadStream(java.io.InputStream stream) {
        try {
            return readStream(stream);
        } catch (Exception ex) {
            return "";
        }
    }

    private String trimMessage(String message) {
        if (message == null) {
            return "";
        }
        String trimmed = message.trim();
        return trimmed.length() <= 2000 ? trimmed : trimmed.substring(trimmed.length() - 2000);
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }
}

