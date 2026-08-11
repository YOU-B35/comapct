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
import java.util.function.Supplier;

/**
 * Rate / concurrency limits for public Temu sync &amp; login enqueue APIs.
 *
 * <p>TOCTOU soft mitigation: {@link #runWithEnqueueGate} serializes check+enqueue
 * per {@code tenantId:userId} on this JVM so concurrent double-submit cannot both
 * pass the in-flight count before insert. Not a DB unique constraint — multi-instance
 * deploys would still need a shared lock or conditional insert.
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
    private final ConcurrentHashMap<String, Object> userGates = new ConcurrentHashMap<>();

    public TemuSyncLimitService(JdbcTemplate jdbc, CrawlerProperties crawlerProperties) {
        this.jdbc = jdbc;
        this.crawlerProperties = crawlerProperties;
    }

    /**
     * Throws HTTP 429 with Chinese {@code msg} when limits are exceeded.
     * Does <strong>not</strong> consume the per-minute enqueue slot — call
     * {@link #recordEnqueue(Long)} only after a successful enqueue, or use
     * {@link #runWithEnqueueGate}.
     */
    public void checkCanEnqueue(Long tenantId, Long userId) {
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "请先登录");
        }
        assertUserInFlight(tenantId, userId);
        assertGlobalRunning();
        assertEnqueueRate(userId);
    }

    /**
     * Consume one per-user enqueue/min slot. Call only after enqueue succeeds.
     */
    public void recordEnqueue(Long userId) {
        if (userId == null) {
            return;
        }
        long now = System.currentTimeMillis();
        Deque<Long> window = enqueueTimestamps.computeIfAbsent(userId, id -> new ArrayDeque<>());
        synchronized (window) {
            while (!window.isEmpty() && now - window.peekFirst() >= RATE_WINDOW_MS) {
                window.pollFirst();
            }
            window.addLast(now);
        }
    }

    /**
     * Per-user gate: check limits → run action → record rate only on success.
     * Serializes concurrent enqueues for the same tenant+user on this JVM (TOCTOU soft fix).
     */
    public <T> T runWithEnqueueGate(Long tenantId, Long userId, Supplier<T> action) {
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "请先登录");
        }
        String key = gateKey(tenantId, userId);
        Object gate = userGates.computeIfAbsent(key, k -> new Object());
        synchronized (gate) {
            checkCanEnqueue(tenantId, userId);
            T result = action.get();
            recordEnqueue(userId);
            return result;
        }
    }

    private static String gateKey(Long tenantId, Long userId) {
        return String.valueOf(tenantId) + ":" + userId;
    }

    private void assertUserInFlight(Long tenantId, Long userId) {
        int max = Math.max(1, crawlerProperties.getSyncLimit().getMaxPerUserInFlight());
        Long count = jdbc.queryForObject(
                """
                SELECT COUNT(*) FROM temu_crawl_job
                WHERE tenant_id = ?
                  AND triggered_by = ?
                  AND status IN ('pending', 'running')
                """,
                Long.class,
                tenantId,
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

    private void assertEnqueueRate(Long userId) {
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
        }
    }
}
