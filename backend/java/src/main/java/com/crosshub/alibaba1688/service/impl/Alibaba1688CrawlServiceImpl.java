package com.crosshub.alibaba1688.service.impl;

import com.crosshub.alibaba1688.dto.Alibaba1688CrawlRequest;
import com.crosshub.alibaba1688.entity.Alibaba1688CrawlJob;
import com.crosshub.alibaba1688.repository.Alibaba1688CrawlJobRepository;
import com.crosshub.alibaba1688.service.Alibaba1688CrawlConflictException;
import com.crosshub.alibaba1688.service.Alibaba1688CrawlService;
import com.crosshub.alibaba1688.service.Alibaba1688OperationalService;
import com.crosshub.common.AppErrorCode;
import com.crosshub.common.JobListLimits;
import com.crosshub.common.SqliteRetry;
import com.crosshub.common.TenantCrawlCooldownService;
import com.crosshub.config.CrawlerProperties;
import com.crosshub.security.AuthContext;
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
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

@Service
public class Alibaba1688CrawlServiceImpl implements Alibaba1688CrawlService {
    private static final Logger log = LoggerFactory.getLogger(Alibaba1688CrawlServiceImpl.class);
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final Set<String> ACTIVE_STATUSES = Set.of("pending", "running");
    private static final long PENDING_TTL_SECONDS = 5 * 60;

    private final Alibaba1688CrawlJobRepository jobRepository;
    private final Alibaba1688OperationalService operationalService;
    private final DataScopeService dataScopeService;
    private final AuthContext authContext;
    private final CrawlerProperties crawlerProperties;
    private final ObjectMapper objectMapper;
    private final Executor crawlJobExecutor;
    private final Executor crawlExecutor;
    private final TenantCrawlCooldownService crawlCooldownService;

    public Alibaba1688CrawlServiceImpl(
            Alibaba1688CrawlJobRepository jobRepository,
            Alibaba1688OperationalService operationalService,
            DataScopeService dataScopeService,
            AuthContext authContext,
            CrawlerProperties crawlerProperties,
            ObjectMapper objectMapper,
            @Qualifier("crawlJobExecutor") Executor crawlJobExecutor,
            @Qualifier("crawlExecutor") Executor crawlExecutor,
            TenantCrawlCooldownService crawlCooldownService
    ) {
        this.jobRepository = jobRepository;
        this.operationalService = operationalService;
        this.dataScopeService = dataScopeService;
        this.authContext = authContext;
        this.crawlerProperties = crawlerProperties;
        this.objectMapper = objectMapper;
        this.crawlJobExecutor = crawlJobExecutor;
        this.crawlExecutor = crawlExecutor;
        this.crawlCooldownService = crawlCooldownService;
    }

    public static int clampJobListLimit(Integer limit) {
        return JobListLimits.clamp(limit);
    }

    /** Spawn `--scope`: login_probe stays; crawl/sync (and anything else) → sync. */
    public static String mapSpawnScope(String jobType) {
        return "login_probe".equals(jobType) ? "login_probe" : "sync";
    }

    @Override
    @Transactional
    public Alibaba1688CrawlJob triggerCrawl(Alibaba1688CrawlRequest request) {
        Long tenantId = dataScopeService.requireTenantId();
        Long userId = authContext.userId();
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, AppErrorCode.AUTH_MISSING_USER.getUserMessage());
        }
        Alibaba1688CrawlRequest body = request == null ? new Alibaba1688CrawlRequest() : request;
        String jobType = body.resolvedJobType();
        boolean force = body.resolvedForce();
        crawlCooldownService.assertAllowed(tenantId, force);

        Optional<Alibaba1688CrawlJob> active = jobRepository
                .findFirstByTenantIdAndJobTypeAndStatusInOrderByCreatedAtDesc(tenantId, jobType, ACTIVE_STATUSES);
        if (active.isPresent()) {
            Alibaba1688CrawlJob existing = reconcileStaleJob(active.get());
            if (ACTIVE_STATUSES.contains(existing.getStatus())) {
                throw new Alibaba1688CrawlConflictException(existing);
            }
        }

        Alibaba1688CrawlJob job = new Alibaba1688CrawlJob();
        job.setId(UUID.randomUUID().toString().replace("-", ""));
        job.setTenantId(tenantId);
        job.setStoreId(blankToNull(body.getStoreId()));
        job.setTriggeredBy(userId);
        job.setStatus("pending");
        job.setJobType(jobType);
        job.setProgress(0);
        job.setCreatedAt(now());
        jobRepository.save(job);
        crawlCooldownService.registerJobRecordPolicy(job.getId(), body.resolvedRecordCooldown());

        String jobId = job.getId();
        scheduleAfterCommit(() -> crawlJobExecutor.execute(() -> executeJob(jobId)));
        return job;
    }

    @Override
    public Alibaba1688CrawlJob getJob(String jobId) {
        Long tenantId = dataScopeService.requireTenantId();
        Alibaba1688CrawlJob job = jobRepository.findByIdAndTenantId(jobId, tenantId)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.NOT_FOUND, AppErrorCode.CRAWL_JOB_NOT_FOUND.getUserMessage()));
        return reconcileStaleJob(job);
    }

    @Override
    public List<Alibaba1688CrawlJob> listRecentJobs(int limit) {
        Long tenantId = dataScopeService.requireTenantId();
        int n = clampJobListLimit(limit);
        List<Alibaba1688CrawlJob> all = jobRepository.findTop60ByTenantIdOrderByCreatedAtDesc(tenantId);
        if (all.size() <= n) return all;
        return all.subList(0, n);
    }

    private void executeJob(String jobId) {
        Alibaba1688CrawlJob job = null;
        try {
            job = jobRepository.findById(jobId).orElse(null);
            if (job == null) return;
            job.setStatus("running");
            job.setStartedAt(now());
            job.setProgress(5);
            persistJob(job);
            runCrawlProcess(job);
        } catch (Exception ex) {
            log.error("1688 crawl job {} failed", jobId, ex);
            if (job != null) {
                AppErrorCode code = SqliteRetry.isLockConflict(ex)
                        ? AppErrorCode.CRAWL_DB_BUSY
                        : AppErrorCode.classifyCrawlRaw(ex.getMessage());
                failJob(job, code, ex.getMessage() == null ? "爬取进程异常" : ex.getMessage());
            }
        }
    }

    private void runCrawlProcess(Alibaba1688CrawlJob job) throws Exception {
        Path scriptDir = Path.of(crawlerProperties.getScriptDir()).toAbsolutePath().normalize();
        if (!Files.isDirectory(scriptDir)) {
            failJob(job, AppErrorCode.CRAWL_SCRIPT_MISSING, "Python 脚本目录不存在: " + scriptDir);
            return;
        }

        List<String> command = new ArrayList<>();
        command.add(crawlerProperties.getPythonExecutable());
        command.add("operational_crawl.py");
        command.add("--platform");
        command.add("1688");
        command.add("--tenant-id");
        command.add(String.valueOf(job.getTenantId()));
        command.add("--scope");
        command.add(mapSpawnScope(job.getJobType()));
        command.add("--json");

        ProcessBuilder builder = new ProcessBuilder(command);
        builder.directory(scriptDir.toFile());
        builder.environment().put("TENANT_ID", String.valueOf(job.getTenantId()));
        builder.environment().put("PYTHONIOENCODING", "utf-8");
        builder.environment().put("PYTHONUTF8", "1");
        builder.redirectErrorStream(false);

        Process process = builder.start();
        CompletableFuture<String> stdoutFuture = CompletableFuture.supplyAsync(
                () -> safeReadStream(process.getInputStream()), crawlExecutor);
        CompletableFuture<String> stderrFuture = CompletableFuture.supplyAsync(
                () -> safeReadStream(process.getErrorStream()), crawlExecutor);
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
        try { stdout = stdoutFuture.get(3, TimeUnit.SECONDS); } catch (TimeoutException ignored) { stdoutFuture.cancel(true); }
        try { stderr = stderrFuture.get(3, TimeUnit.SECONDS); } catch (TimeoutException ignored) { stderrFuture.cancel(true); }

        JsonNode json = parseJsonLine(stdout);
        String status = json != null && json.has("status") ? json.get("status").asText("") : "";
        if ("need_login".equalsIgnoreCase(status)) {
            job.setStatus("need_login");
            job.setFinishedAt(now());
            job.setProgress(100);
            job.setErrorCode(AppErrorCode.CRAWL_1688_NOT_LOGGED_IN.getCode());
            job.setErrorMessage(AppErrorCode.CRAWL_1688_NOT_LOGGED_IN.getUserMessage());
            job.setMessage(json.has("message") ? json.get("message").asText("") : "需要登录");
            persistJob(job);
            return;
        }

        if (process.exitValue() != 0) {
            String raw = combineOutput(stderr, stdout);
            failJob(job, AppErrorCode.classifyCrawlRaw(raw), raw);
            return;
        }

        if (json != null && json.has("rows")) {
            job.setRowsCount(json.get("rows").asInt(0));
        }
        if (json != null && json.has("message")) {
            job.setMessage(json.get("message").asText(""));
        }

        boolean partial = "partial".equalsIgnoreCase(status);
        job.setStatus(partial ? "partial" : "success");
        job.setFinishedAt(now());
        job.setProgress(100);
        job.setErrorCode("");
        job.setErrorMessage("");
        persistJob(job);
        crawlCooldownService.onJobSuccess(job.getId(), job.getTenantId());

        try {
            operationalService.rebuildAlertsAndStats(job.getTenantId());
        } catch (Exception ex) {
            log.warn("1688 rebuildAlertsAndStats after job {} failed: {}", job.getId(), ex.toString());
        }
    }

    private Alibaba1688CrawlJob reconcileStaleJob(Alibaba1688CrawlJob job) {
        if (job == null || !ACTIVE_STATUSES.contains(job.getStatus())) return job;
        LocalDateTime base = parseTime("running".equals(job.getStatus()) ? job.getStartedAt() : job.getCreatedAt());
        long ttl = "running".equals(job.getStatus())
                ? crawlerProperties.getTimeoutSeconds() + 60L
                : PENDING_TTL_SECONDS;
        if (base == null || base.plusSeconds(ttl).isBefore(LocalDateTime.now())) {
            job.setStatus("failed");
            job.setFinishedAt(now());
            job.setErrorCode(AppErrorCode.CRAWL_INTERRUPTED.getCode());
            job.setErrorMessage(AppErrorCode.CRAWL_INTERRUPTED.getUserMessage());
            persistJobQuietly(job);
        }
        return job;
    }

    private void failJob(Alibaba1688CrawlJob job, AppErrorCode code, String raw) {
        job.setStatus("failed");
        job.setFinishedAt(now());
        job.setProgress(100);
        job.setErrorCode(code.getCode());
        job.setErrorMessage(code.getUserMessage());
        job.setMessage(raw == null ? "" : raw.substring(0, Math.min(raw.length(), 500)));
        persistJobQuietly(job);
    }

    private void persistJob(Alibaba1688CrawlJob job) {
        SqliteRetry.runWithRetry(() -> jobRepository.save(job));
    }

    private void persistJobQuietly(Alibaba1688CrawlJob job) {
        try { persistJob(job); } catch (Exception ex) {
            log.error("1688 crawl job {} persist failed", job.getId(), ex);
        }
    }

    private void scheduleAfterCommit(Runnable action) {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() { action.run(); }
            });
        } else {
            action.run();
        }
    }

    private JsonNode parseJsonLine(String stdout) {
        if (stdout == null || stdout.isBlank()) return null;
        String[] lines = stdout.split("\\R");
        for (int i = lines.length - 1; i >= 0; i--) {
            String line = lines[i].trim();
            if (line.startsWith("{") && line.endsWith("}")) {
                try { return objectMapper.readTree(line); } catch (Exception ignored) { }
            }
        }
        return null;
    }

    private static String safeReadStream(java.io.InputStream in) {
        try {
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        } catch (Exception ex) {
            return "";
        }
    }

    private static String combineOutput(String stderr, String stdout) {
        String a = stderr == null ? "" : stderr.trim();
        String b = stdout == null ? "" : stdout.trim();
        if (a.isEmpty()) return b;
        if (b.isEmpty()) return a;
        return a + "\n" + b;
    }

    private static String now() {
        return LocalDateTime.now().format(TS);
    }

    private static LocalDateTime parseTime(String text) {
        if (text == null || text.isBlank()) return null;
        try { return LocalDateTime.parse(text.trim(), TS); } catch (Exception ex) { return null; }
    }

    private static String blankToNull(String s) {
        return s == null || s.isBlank() ? null : s.trim();
    }
}
