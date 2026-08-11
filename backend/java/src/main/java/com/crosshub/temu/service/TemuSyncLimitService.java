package com.crosshub.temu.service;

import com.crosshub.config.CrawlerProperties;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Rate / concurrency limits for public Temu sync &amp; login enqueue APIs.
 */
@Service
public class TemuSyncLimitService {
    public static final String MSG_USER_IN_FLIGHT = "您已有进行中的 Temu 同步任务，请稍后再试";
    public static final String MSG_ENQUEUE_RATE = "操作过于频繁，每分钟最多提交 3 次，请稍后再试";
    public static final String MSG_GLOBAL_BUSY = "系统同步任务繁忙，请稍后再试";

    private static final long RATE_WINDOW_MS = 60_000L;

    private final JdbcTemplate jdbc;
    private final CrawlerProperties crawlerProperties;
    private final Map<Long, Deque<Long>> enqueueTimestamps = new ConcurrentHashMap<>();

    public TemuSyncLimitService(JdbcTemplate jdbc, CrawlerProperties crawlerProperties) {
        this.jdbc = jdbc;
        this.crawlerProperties = crawlerProperties;
    }

    /**
     * Throws HTTP 429 with Chinese {@code msg} when limits are exceeded.
     * Successful calls consume one slot in the per-user enqueue/min window.
     */
    public void checkCanEnqueue(Long tenantId, Long userId) {
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "请先登录");
        }
        assertUserInFlight(userId);
        assertGlobalRunning();
        assertAndRecordEnqueueRate(userId);
    }

    private void assertUserInFlight(Long userId) {
        int max = Math.max(1, crawlerProperties.getSyncLimit().getMaxPerUserInFlight());
        Long count = jdbc.queryForObject(
                """
                SELECT COUNT(*) FROM temu_crawl_job
                WHERE triggered_by = ?
                  AND status IN ('pending', 'running')
                """,
                Long.class,
                userId
        );
        if (count != null && count >= max) {
            throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, MSG_USER_IN_FLIGHT);
        }
    }

    private void assertGlobalRunning() {
        int max = Math.max(1, crawlerProperties.getSyncLimit().getMaxGlobalRunning());
        Long count = jdbc.queryForObject(
                """
                SELECT COUNT(*) FROM temu_crawl_job
                WHERE status IN ('pending', 'running')
                """,
                Long.class
        );
        if (count != null && count >= max) {
            throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, MSG_GLOBAL_BUSY);
        }
    }

    private void assertAndRecordEnqueueRate(Long userId) {
        int max = Math.max(1, crawlerProperties.getSyncLimit().getMaxEnqueuePerMinute());
        long now = System.currentTimeMillis();
        Deque<Long> window = enqueueTimestamps.computeIfAbsent(userId, id -> new ArrayDeque<>());
        synchronized (window) {
            while (!window.isEmpty() && now - window.peekFirst() >= RATE_WINDOW_MS) {
                window.pollFirst();
            }
            if (window.size() >= max) {
                throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, MSG_ENQUEUE_RATE);
            }
            window.addLast(now);
        }
    }
}
