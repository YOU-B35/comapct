package com.crosshub.temu.service.impl;

import com.crosshub.common.AppErrorCode;
import com.crosshub.common.SqliteRetry;
import com.crosshub.platform.service.PlatformAccountService;
import com.crosshub.temu.service.TemuCrawlService;
import com.crosshub.common.TenantCrawlCooldownService;
import com.crosshub.temu.service.TemuCrawlAuthService;
import com.crosshub.temu.service.TemuAgentService;
import com.crosshub.temu.service.TemuSessionService;
import com.crosshub.temu.service.CrawlConflictException;

import com.crosshub.config.CrawlerProperties;
import com.crosshub.temu.entity.TemuCrawlJob;
import com.crosshub.temu.repository.TemuCrawlJobRepository;
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
import java.util.Map;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

@Service
public class TemuCrawlServiceImpl implements TemuCrawlService {
    private static final Logger log = LoggerFactory.getLogger(TemuCrawlServiceImpl.class);
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final List<String> ACTIVE_STATUSES = List.of("pending", "running");
    private static final Set<String> ACTIVE_STATUS_SET = Set.of("pending", "running");
    private static final long PENDING_TTL_SECONDS = 5 * 60;

    private final TemuCrawlJobRepository jobRepository;
    private final TemuCrawlAuthService crawlAuthService;
    private final DataScopeService dataScopeService;
    private final AuthContext authContext;
    private final CrawlerProperties crawlerProperties;
    private final ObjectMapper objectMapper;
    private final Executor crawlJobExecutor;
    private final Executor crawlExecutor;
    private final PlatformAccountService platformAccountService;
    private final TemuSessionService temuSessionService;
    private final TenantCrawlCooldownService crawlCooldownService;
    private final TemuAgentService temuAgentService;

    public TemuCrawlServiceImpl(
            TemuCrawlJobRepository jobRepository,
            TemuCrawlAuthService crawlAuthService,
            DataScopeService dataScopeService,
            AuthContext authContext,
            CrawlerProperties crawlerProperties,
            ObjectMapper objectMapper,
            @Qualifier("crawlJobExecutor") Executor crawlJobExecutor,
            @Qualifier("crawlExecutor") Executor crawlExecutor,
            PlatformAccountService platformAccountService,
            TemuSessionService temuSessionService,
            TenantCrawlCooldownService crawlCooldownService,
            TemuAgentService temuAgentService
    ) {
        this.jobRepository = jobRepository;
        this.crawlAuthService = crawlAuthService;
        this.dataScopeService = dataScopeService;
        this.authContext = authContext;
        this.crawlerProperties = crawlerProperties;
        this.objectMapper = objectMapper;
        this.crawlJobExecutor = crawlJobExecutor;
        this.crawlExecutor = crawlExecutor;
        this.platformAccountService = platformAccountService;
        this.temuSessionService = temuSessionService;
        this.crawlCooldownService = crawlCooldownService;
        this.temuAgentService = temuAgentService;
    }

    @Transactional
    public TemuCrawlJob triggerCrawl(String reportTime, boolean seed) {
        return triggerCrawl(reportTime, seed, false);
    }

    @Transactional
    public TemuCrawlJob triggerCrawl(String reportTime, boolean seed, boolean force) {
        return triggerCrawl(reportTime, seed, force, true);
    }

    @Transactional
    public TemuCrawlJob triggerCrawl(String reportTime, boolean seed, boolean force, boolean recordCooldown) {
        crawlAuthService.assertCanTriggerCrawl();
        Long tenantId = dataScopeService.requireTenantId();
        crawlCooldownService.assertAllowed(tenantId, force);
        Long userId = authContext.userId();
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, AppErrorCode.AUTH_MISSING_USER.getUserMessage());
        }
        if (seed && !crawlerProperties.isAllowSeed()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.CRAWL_SEED_DISABLED.getUserMessage());
        }

        assertProfileAvailable(tenantId);
        temuAgentService.assertAgentOnlineForUser(userId);
        assertSessionReady();

        Optional<TemuCrawlJob> active = jobRepository.findFirstByTenantIdAndStatusInOrderByCreatedAtDesc(
                tenantId, ACTIVE_STATUSES
        );
        if (active.isPresent()) {
            TemuCrawlJob existing = reconcileStaleJob(active.get());
            if (ACTIVE_STATUS_SET.contains(existing.getStatus())) {
                throw new CrawlConflictException(existing);
            }
        }

        return createAndEnqueueJob(tenantId, userId, reportTime, seed, recordCooldown);
    }

    @Transactional
    public TemuCrawlJob enqueueUserSync(String reportTime, boolean seed, boolean force, boolean recordCooldown) {
        crawlAuthService.assertCanTriggerCrawl();
        Long tenantId = dataScopeService.requireTenantId();
        crawlCooldownService.assertAllowed(tenantId, force);
        Long userId = authContext.userId();
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, AppErrorCode.AUTH_MISSING_USER.getUserMessage());
        }
        if (seed && !crawlerProperties.isAllowSeed()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.CRAWL_SEED_DISABLED.getUserMessage());
        }

        assertProfileAvailable(tenantId);
        temuAgentService.assertAgentOnlineForUser(userId);
        assertSessionReady();

        return createAndEnqueueJob(tenantId, userId, reportTime, seed, recordCooldown);
    }

    private TemuCrawlJob createAndEnqueueJob(
            Long tenantId,
            Long userId,
            String reportTime,
            boolean seed,
            boolean recordCooldown
    ) {
        TemuCrawlJob job = new TemuCrawlJob();
        job.setId(UUID.randomUUID().toString());
        job.setTenantId(tenantId);
        job.setTriggeredBy(userId);
        job.setStatus("pending");
        job.setMode(seed ? "seed" : "live");
        job.setReportTime(reportTime);
        job.setCreatedAt(now());
        jobRepository.save(job);
        crawlCooldownService.registerJobRecordPolicy(job.getId(), recordCooldown);

        String jobId = job.getId();
        if (temuAgentService.useAgentMode()) {
            temuAgentService.enqueueCrawlJob(job);
        } else {
            scheduleAfterCommit(() -> crawlJobExecutor.execute(() -> executeJob(jobId)));
        }
        return job;
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

    public TemuCrawlJob getJob(String jobId) {
        Long tenantId = dataScopeService.requireTenantId();
        TemuCrawlJob job = jobRepository.findByIdAndTenantId(jobId, tenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, AppErrorCode.CRAWL_JOB_NOT_FOUND.getUserMessage()));
        job = reconcileStaleJob(job);
        Long userId = authContext.userId();
        if (userId != null
                && job.getTriggeredBy() != null
                && job.getTriggeredBy() > 0
                && !job.getTriggeredBy().equals(userId)
                && !authContext.isBossPortal()
                && !authContext.isAdmin()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, AppErrorCode.CRAWL_JOB_NOT_FOUND.getUserMessage());
        }
        return job;
    }

    void executeJob(String jobId) {
        TemuCrawlJob job = null;
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
            log.error("Temu crawl job {} failed", jobId, ex);
            if (job != null) {
                AppErrorCode code = SqliteRetry.isLockConflict(ex)
                        ? AppErrorCode.CRAWL_DB_BUSY
                        : AppErrorCode.classifyCrawlRaw(ex.getMessage());
                String raw = ex.getMessage() == null ? "爬取进程异常" : ex.getMessage();
                failJob(job, code, raw);
            }
        }
    }

    private void runCrawlProcess(TemuCrawlJob job) throws Exception {
        String jobId = job.getId();
        Path scriptDir = Path.of(crawlerProperties.getScriptDir()).toAbsolutePath().normalize();
        if (!Files.isDirectory(scriptDir)) {
            failJob(job, AppErrorCode.CRAWL_SCRIPT_MISSING, "Python 脚本目录不存在: " + scriptDir);
            return;
        }

        List<String> command = new ArrayList<>();
        command.add(crawlerProperties.getPythonExecutable());
        command.add("crawl.py");
        command.add("--tenant-id");
        command.add(String.valueOf(job.getTenantId()));
        command.add("--json");
        if ("seed".equals(job.getMode())) {
            command.add("--seed");
        }
        if (job.getReportTime() != null && !job.getReportTime().isBlank()) {
            command.add("--date");
            command.add(job.getReportTime());
        }

        ProcessBuilder builder = new ProcessBuilder(command);
        builder.directory(scriptDir.toFile());
        builder.environment().put("TENANT_ID", String.valueOf(job.getTenantId()));
        // Windows 控制台默认 GBK；强制 Python 用 UTF-8，便于错误分类（未登录等）
        builder.environment().put("PYTHONIOENCODING", "utf-8");
        builder.environment().put("PYTHONUTF8", "1");
        builder.redirectErrorStream(false);

        long started = System.currentTimeMillis();
        log.info("Starting temu crawl job {} tenant={} mode={}", jobId, job.getTenantId(), job.getMode());
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
        try { stdout = stdoutFuture.get(3, TimeUnit.SECONDS); } catch (TimeoutException ignored) { stdoutFuture.cancel(true); }
        try { stderr = stderrFuture.get(3, TimeUnit.SECONDS); } catch (TimeoutException ignored) { stderrFuture.cancel(true); }

        int exitCode = process.exitValue();
        long elapsed = System.currentTimeMillis() - started;
        log.info("Temu crawl job {} finished exit={} elapsed={}ms", jobId, exitCode, elapsed);

        if (exitCode != 0) {
            String raw = combineOutput(stderr, stdout);
            AppErrorCode code = AppErrorCode.classifyCrawlRaw(raw);
            failJob(job, code, raw);
            return;
        }

        JsonNode json = parseJsonLine(stdout);
        if (json != null) {
            if (json.has("report_time")) {
                job.setReportTime(json.get("report_time").asText());
            }
            if (json.has("shops")) {
                job.setShopsCount(json.get("shops").asInt());
            }
            if (json.has("rows")) {
                job.setRowsCount(json.get("rows").asInt());
            }
        }

        job.setStatus("success");
        job.setFinishedAt(now());
        job.setErrorCode("");
        job.setErrorMessage("");
        persistJob(job);
        crawlCooldownService.onJobSuccess(job.getId(), job.getTenantId());

        try {
            int linked = platformAccountService.autoLinkTemuShops(job.getTenantId());
            if (linked > 0) {
                log.info("Auto-linked {} temu account(s) for tenant {}", linked, job.getTenantId());
            }
        } catch (Exception linkEx) {
            log.warn("Auto-link temu accounts failed for tenant {}", job.getTenantId(), linkEx);
        }
    }

    private void assertProfileAvailable(Long tenantId) {
        try {
            java.util.Map<String, Object> session = temuSessionService.getSessionStatus();
            if (!Boolean.TRUE.equals(session.get("profile_busy"))) {
                return;
            }
            Optional<TemuCrawlJob> active = jobRepository.findFirstByTenantIdAndStatusInOrderByCreatedAtDesc(
                    tenantId, ACTIVE_STATUSES
            );
            if (active.isPresent()) {
                TemuCrawlJob existing = reconcileStaleJob(active.get());
                if (ACTIVE_STATUS_SET.contains(existing.getStatus())) {
                    throw new CrawlConflictException(existing);
                }
            }
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    "Temu 登录窗口仍占用浏览器，请关闭 CrossHub 弹出的登录浏览器后重试"
            );
        } catch (CrawlConflictException ex) {
            throw ex;
        } catch (ResponseStatusException ex) {
            throw ex;
        } catch (Exception ex) {
            log.debug("Temu session pre-check skipped: {}", ex.getMessage());
        }
    }

    private void assertSessionReady() {
        try {
            Map<String, Object> session = temuSessionService.getSessionStatus();
            if (Boolean.TRUE.equals(session.get("ready"))) {
                return;
            }
            // AliExpress-style: refuse crawl until seller session cookies are ready.
            // Password auto-login is interactive-only (login_open), not part of crawl.
            String hint = stringValue(session.get("error_hint"));
            AppErrorCode code = AppErrorCode.fromCode(hint);
            if (code == AppErrorCode.UNKNOWN) {
                boolean loggedIn = Boolean.TRUE.equals(session.get("logged_in"));
                code = loggedIn
                        ? AppErrorCode.CRAWL_MALL_NOT_SELECTED
                        : AppErrorCode.CRAWL_NOT_LOGGED_IN;
            }
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, code.getUserMessage());
        } catch (ResponseStatusException ex) {
            throw ex;
        } catch (Exception ex) {
            log.debug("Temu session ready pre-check skipped: {}", ex.getMessage());
        }
    }

    private String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private TemuCrawlJob reconcileStaleJob(TemuCrawlJob job) {
        if (job == null || !ACTIVE_STATUS_SET.contains(job.getStatus())) {
            return job;
        }
        if (!isStale(job)) {
            return job;
        }
        markStaleJobFailed(job);
        return job;
    }

    private boolean isStale(TemuCrawlJob job) {
        LocalDateTime base = parseTime("running".equals(job.getStatus()) ? job.getStartedAt() : job.getCreatedAt());
        if (base == null) {
            return true;
        }
        long ttl = "running".equals(job.getStatus())
                ? crawlerProperties.getTimeoutSeconds() + 60L
                : PENDING_TTL_SECONDS;
        return base.plusSeconds(ttl).isBefore(LocalDateTime.now());
    }

    private void markStaleJobFailed(TemuCrawlJob job) {
        job.setStatus("failed");
        job.setFinishedAt(now());
        job.setErrorCode(AppErrorCode.CRAWL_INTERRUPTED.getCode());
        job.setErrorMessage(AppErrorCode.CRAWL_INTERRUPTED.getUserMessage());
        persistJobQuietly(job);
        log.warn("Temu crawl job {} marked stale -> failed", job.getId());
    }

    private void persistJob(TemuCrawlJob job) {
        SqliteRetry.runWithRetry(() -> jobRepository.save(job));
    }

    private void persistJobQuietly(TemuCrawlJob job) {
        try {
            persistJob(job);
        } catch (Exception ex) {
            log.error("Temu crawl job {} persist failed", job.getId(), ex);
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

    private String safeReadStream(java.io.InputStream stream) {
        try {
            return readStream(stream);
        } catch (Exception ex) {
            return "";
        }
    }

    private void failJob(TemuCrawlJob job, AppErrorCode code, String internalDetail) {
        if (hasPersistedPayload(job)) {
            partialJob(job, code, internalDetail);
            return;
        }
        log.warn("Temu crawl job {} failed [{}]: {}", job.getId(), code.getCode(), trimMessage(internalDetail));
        job.setStatus("failed");
        job.setFinishedAt(now());
        job.setErrorCode(code.getCode());
        job.setErrorMessage(code.getUserMessage());
        persistJobQuietly(job);
    }

    private void partialJob(TemuCrawlJob job, AppErrorCode code, String internalDetail) {
        log.warn("Temu crawl job {} partial [{}]: {}", job.getId(), code.getCode(), trimMessage(internalDetail));
        job.setStatus("partial");
        job.setFinishedAt(now());
        job.setErrorCode(code.getCode());
        job.setErrorMessage("爬取已完成，但任务收尾异常，页面数据可能已更新");
        persistJobQuietly(job);
    }

    private boolean hasPersistedPayload(TemuCrawlJob job) {
        return job.getRowsCount() != null && job.getRowsCount() > 0;
    }

    private String combineOutput(String stderr, String stdout) {
        if (stderr != null && !stderr.isBlank()) {
            return stderr;
        }
        return stdout == null ? "" : stdout;
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
                // try next line
            }
        }
        return null;
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

    private String trimMessage(String message) {
        if (message == null) {
            return "";
        }
        String trimmed = message.trim();
        int max = 2000;
        if (trimmed.length() <= max) {
            return trimmed;
        }
        return trimmed.substring(trimmed.length() - max);
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }
}
