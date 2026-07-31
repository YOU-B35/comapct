package com.crosshub.common;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class TenantCrawlCooldownService {
    public static final String SCOPE_PLATFORM = "platform";
    public static final long COOLDOWN_MS = 3L * 60 * 60 * 1000;
    public static final long MONITOR_TARGET_COOLDOWN_MS = 30L * 60 * 1000;
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final JdbcTemplate jdbc;
    private final ConcurrentHashMap<String, Boolean> pendingJobRecordFlags = new ConcurrentHashMap<>();

    public TenantCrawlCooldownService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public static String monitorScope(String targetId) {
        return "monitor:" + targetId;
    }

    public static long cooldownMsForScope(String scope) {
        if (scope != null && scope.startsWith("monitor:")) {
            return MONITOR_TARGET_COOLDOWN_MS;
        }
        return COOLDOWN_MS;
    }

    public void registerJobRecordPolicy(String jobId, boolean recordCooldown) {
        if (jobId == null || jobId.isBlank()) {
            return;
        }
        pendingJobRecordFlags.put(jobId, recordCooldown);
    }

    public void onJobSuccess(String jobId, Long tenantId) {
        if (tenantId == null || tenantId <= 0) {
            return;
        }
        Boolean record = jobId == null ? Boolean.TRUE : pendingJobRecordFlags.remove(jobId);
        if (record == null || record) {
            recordSuccess(tenantId, SCOPE_PLATFORM);
        }
    }

    public void assertAllowed(Long tenantId, boolean force) {
        assertAllowed(tenantId, SCOPE_PLATFORM, force);
    }

    public void assertAllowed(Long tenantId, String scope, boolean force) {
        if (force || tenantId == null || tenantId <= 0) {
            return;
        }
        String resolvedScope = resolveScope(scope);
        long remaining = remainingMs(tenantId, resolvedScope);
        if (remaining > 0) {
            throw new CrawlCooldownException(remaining, resolvedScope, messageFor(resolvedScope, remaining));
        }
    }

    public long remainingMs(Long tenantId) {
        return remainingMs(tenantId, SCOPE_PLATFORM);
    }

    public long remainingMs(Long tenantId, String scope) {
        LocalDateTime last = loadLastSuccessAt(tenantId, resolveScope(scope));
        if (last == null) {
            return 0;
        }
        long elapsed = ChronoUnit.MILLIS.between(last, LocalDateTime.now());
        long remaining = cooldownMsForScope(scope) - elapsed;
        return remaining > 0 ? remaining : 0;
    }

    public void recordSuccess(Long tenantId) {
        recordSuccess(tenantId, SCOPE_PLATFORM);
    }

    public void recordSuccess(Long tenantId, String scope) {
        if (tenantId == null || tenantId <= 0) {
            return;
        }
        String resolvedScope = resolveScope(scope);
        String now = now();
        jdbc.update("""
                INSERT INTO tenant_crawl_cooldown (tenant_id, scope, last_success_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(tenant_id, scope) DO UPDATE SET
                  last_success_at = excluded.last_success_at,
                  updated_at = excluded.updated_at
                """, tenantId, resolvedScope, now, now);
    }

    private LocalDateTime loadLastSuccessAt(Long tenantId, String scope) {
        if (tenantId == null || tenantId <= 0) {
            return null;
        }
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT last_success_at FROM tenant_crawl_cooldown WHERE tenant_id = ? AND scope = ? LIMIT 1",
                tenantId,
                resolveScope(scope)
        );
        if (rows.isEmpty()) {
            return null;
        }
        Object raw = rows.get(0).get("last_success_at");
        return parseTime(raw == null ? "" : String.valueOf(raw));
    }

    static String messageFor(String scope, long remainingMs) {
        if (scope != null && scope.startsWith("monitor:")) {
            long minutes = Math.max(1, (remainingMs + 59_999) / 60_000);
            return "该竞店冷却中，请稍后再试或强制刷新（约剩余 " + minutes + " 分钟）";
        }
        return AppErrorCode.CRAWL_COOLDOWN.getUserMessage();
    }

    private static String resolveScope(String scope) {
        return scope == null || scope.isBlank() ? SCOPE_PLATFORM : scope;
    }

    private LocalDateTime parseTime(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return LocalDateTime.parse(value.trim(), TS);
        } catch (Exception ignored) {
            return null;
        }
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }
}
