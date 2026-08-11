package com.crosshub.temu.service;

import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.common.AppErrorCode;
import com.crosshub.temu.entity.TemuCrawlJob;
import com.crosshub.temu.repository.TemuCrawlJobRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Lazy;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Temu 日批/爬取失败后的当天有限次自动重试（最多 8 次含首次）。
 */
@Service
public class TemuCrawlRetryService {
    private static final Logger log = LoggerFactory.getLogger(TemuCrawlRetryService.class);
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    public static final int MAX_ATTEMPTS = 8;
    /** 第 2..8 次启动前的等待（分钟），对应失败后的 retry_count 1..7 */
    private static final int[] BACKOFF_MINUTES = {2, 5, 10, 15, 20, 30, 30};
    private static final Set<String> NO_AUTO_RETRY = Set.of(
            "CRAWL_HUMAN_CHALLENGE",
            AppErrorCode.CRAWL_NOT_LOGGED_IN.getCode(),
            "TEMU_REGION_NO_PERMISSION"
    );

    private final TemuCrawlJobRepository jobRepository;
    private final TemuAgentService temuAgentService;
    private final AgentPresenceService agentPresenceService;

    public TemuCrawlRetryService(
            TemuCrawlJobRepository jobRepository,
            @Lazy TemuAgentService temuAgentService,
            AgentPresenceService agentPresenceService
    ) {
        this.jobRepository = jobRepository;
        this.temuAgentService = temuAgentService;
        this.agentPresenceService = agentPresenceService;
    }

    public static int backoffMinutesForNextAttempt(int nextRetryCount) {
        // nextRetryCount is 1..7 when scheduling after attempt 1..7 failed
        int idx = Math.max(0, Math.min(BACKOFF_MINUTES.length - 1, nextRetryCount - 1));
        return BACKOFF_MINUTES[idx];
    }

    public static boolean isAutoRetryable(String errorCode) {
        String code = errorCode == null ? "" : errorCode.trim().toUpperCase(Locale.ROOT);
        if (code.isBlank()) {
            return true;
        }
        return !NO_AUTO_RETRY.contains(code);
    }

    /**
     * After a crawl attempt fails: either schedule retry_wait or mark exhausted.
     * {@code attemptIndex} is 0-based completed attempts before this failure (job.retryCount before bump).
     */
    @Transactional
    public void onCrawlAttemptFailed(TemuCrawlJob job, String errorCode, String errorMessage) {
        if (job == null) {
            return;
        }
        int attemptIndex = job.getRetryCount();
        int maxAttempts = job.getMaxRetryCount() <= 0 ? MAX_ATTEMPTS : job.getMaxRetryCount();
        String code = errorCode == null ? "" : errorCode.trim();
        String message = errorMessage == null ? "" : errorMessage.trim();
        job.setErrorCode(code);
        job.setErrorMessage(message);
        job.setFinishedAt(now());
        job.setMaxRetryCount(maxAttempts);

        boolean canRetry = isAutoRetryable(code) && (attemptIndex + 1) < maxAttempts;
        if (!canRetry) {
            job.setStatus("failed");
            job.setRetryExhausted(true);
            job.setNextRetryAt("");
            jobRepository.save(job);
            log.info(
                    "Temu crawl job {} exhausted retries attempt={}/{} code={}",
                    job.getId(),
                    attemptIndex + 1,
                    maxAttempts,
                    code
            );
            return;
        }

        int nextRetryCount = attemptIndex + 1;
        int delayMin = backoffMinutesForNextAttempt(nextRetryCount);
        job.setRetryCount(nextRetryCount);
        job.setStatus("retry_wait");
        job.setRetryExhausted(false);
        job.setNextRetryAt(LocalDateTime.now().plusMinutes(delayMin).format(TS));
        job.setAgentTaskId("");
        jobRepository.save(job);
        log.info(
                "Temu crawl job {} scheduled retry #{}/{} in {}m at {} code={}",
                job.getId(),
                nextRetryCount + 1,
                maxAttempts,
                delayMin,
                job.getNextRetryAt(),
                code
        );
    }

    /** Park job for later resume (e.g. agent offline at enqueue time). */
    @Transactional
    public TemuCrawlJob parkForRetry(TemuCrawlJob job, String errorCode, String errorMessage) {
        job.setStatus("retry_wait");
        job.setErrorCode(errorCode == null ? "" : errorCode);
        job.setErrorMessage(errorMessage == null ? "" : errorMessage);
        job.setFinishedAt(now());
        job.setRetryExhausted(false);
        if (job.getMaxRetryCount() == null || job.getMaxRetryCount() <= 0) {
            job.setMaxRetryCount(MAX_ATTEMPTS);
        }
        if (job.getRetryCount() == null) {
            job.setRetryCount(0);
        }
        int delayMin = backoffMinutesForNextAttempt(Math.max(1, job.getRetryCount() + 1));
        job.setNextRetryAt(LocalDateTime.now().plusMinutes(delayMin).format(TS));
        job.setAgentTaskId("");
        return jobRepository.save(job);
    }

    @Scheduled(fixedDelayString = "${crosshub.crawler.daily-sync.retry-scan-ms:60000}")
    @Transactional
    public void processDueRetries() {
        String now = now();
        List<TemuCrawlJob> due = jobRepository
                .findByStatusAndNextRetryAtLessThanEqualOrderByNextRetryAtAsc("retry_wait", now);
        if (due.isEmpty()) {
            return;
        }
        for (TemuCrawlJob job : due) {
            try {
                resumeJob(job);
            } catch (Exception ex) {
                log.warn("Temu crawl retry resume failed job={}: {}", job.getId(), ex.getMessage());
            }
        }
    }

    @Transactional
    public void resumeJob(TemuCrawlJob job) {
        if (job == null || !"retry_wait".equalsIgnoreCase(job.getStatus())) {
            return;
        }
        Long tenantId = job.getTenantId();
        Long triggeredBy = job.getTriggeredBy();
        boolean userScoped = triggeredBy != null && triggeredBy > 0;
        boolean online = userScoped
                ? agentPresenceService.isAgentOnlineForUser(triggeredBy)
                : agentPresenceService.isAgentOnline(tenantId);
        AppErrorCode offlineCode = userScoped
                ? AppErrorCode.TEMU_USER_HELPER_OFFLINE
                : AppErrorCode.TEMU_AGENT_OFFLINE;

        if (!online && offlineCode.getCode().equalsIgnoreCase(job.getErrorCode())) {
            // Keep waiting: push next_retry_at a bit further
            job.setNextRetryAt(LocalDateTime.now().plusMinutes(2).format(TS));
            jobRepository.save(job);
            log.info("Temu crawl job {} still offline, defer +2m", job.getId());
            return;
        }
        if (!online) {
            job.setNextRetryAt(LocalDateTime.now().plusMinutes(2).format(TS));
            job.setErrorCode(offlineCode.getCode());
            job.setErrorMessage(offlineCode.getUserMessage());
            jobRepository.save(job);
            return;
        }

        job.setStatus("pending");
        job.setStartedAt(null);
        job.setFinishedAt(null);
        job.setNextRetryAt("");
        job.setErrorCode("");
        // keep last error_message briefly? clear for clean run
        job.setErrorMessage("");
        jobRepository.save(job);
        temuAgentService.enqueueCrawlJob(job);
        log.info(
                "Temu crawl job {} resumed as attempt {}/{}",
                job.getId(),
                job.getRetryCount() + 1,
                job.getMaxRetryCount()
        );
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }
}
