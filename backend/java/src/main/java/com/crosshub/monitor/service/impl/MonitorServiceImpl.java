package com.crosshub.monitor.service.impl;

import com.crosshub.common.AppErrorCode;
import com.crosshub.common.TenantCrawlCooldownService;
import com.crosshub.config.CrawlerProperties;
import com.crosshub.monitor.service.MonitorJobConflictException;
import com.crosshub.monitor.service.MonitorService;
import com.crosshub.monitor.util.Alibaba1688MonitorUrlValidator;
import com.crosshub.monitor.util.TemuMonitorUrlValidator;
import com.crosshub.security.AuthContext;
import com.crosshub.tenant.service.DataScopeService;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.*;

@Service
public class MonitorServiceImpl implements MonitorService {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final Set<String> ACTIVE_JOB_STATUSES = Set.of("pending", "running");
    private static final long RUNNING_TTL_SECONDS = 20 * 60;
    private static final long PENDING_TTL_SECONDS = 5 * 60;

    private final JdbcTemplate jdbc;
    private final DataScopeService dataScopeService;
    private final AuthContext authContext;
    private final CrawlerProperties crawlerProperties;
    private final TenantCrawlCooldownService crawlCooldownService;

    public MonitorServiceImpl(
            JdbcTemplate jdbc,
            DataScopeService dataScopeService,
            AuthContext authContext,
            CrawlerProperties crawlerProperties,
            TenantCrawlCooldownService crawlCooldownService
    ) {
        this.jdbc = jdbc;
        this.dataScopeService = dataScopeService;
        this.authContext = authContext;
        this.crawlerProperties = crawlerProperties;
        this.crawlCooldownService = crawlCooldownService;
    }

    @Override
    public List<Map<String, Object>> listTargets(String platform) {
        Long tenantId = dataScopeService.requireTenantId();
        String sql = """
                SELECT * FROM monitor_target
                WHERE tenant_id = ?
                """;
        List<Object> args = new ArrayList<>();
        args.add(tenantId);
        if (platform != null && !platform.isBlank()) {
            sql += " AND platform = ?";
            args.add(platform.trim());
        }
        sql += " ORDER BY updated_at DESC";
        return jdbc.query(sql, (rs, rn) -> toTargetDto(rsToMap(rs)), args.toArray());
    }

    @Override
    @Transactional
    public Map<String, Object> createTarget(Map<String, Object> payload) {
        Long tenantId = dataScopeService.requireTenantId();
        String now = now();
        String id = "mt_" + UUID.randomUUID().toString().replace("-", "");
        String platform = text(payload, "platform", "temu");
        String targetType = text(payload, "target_type", text(payload, "targetType", "shop"));
        String label = text(payload, "label", "");
        String targetUrl = text(payload, "target_url", text(payload, "targetUrl", ""));
        if (label.isBlank() || targetUrl.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, AppErrorCode.BAD_REQUEST.getUserMessage());
        }
        String status = text(payload, "status", "active");
        String crawlStrategy = text(payload, "crawl_strategy", text(payload, "crawlStrategy", "store_listing"));
        targetUrl = validateAndMaybeCanonicalizeTemuShopUrl(platform, targetType, crawlStrategy, targetUrl);
        String host = text(payload, "host", parseHost(targetUrl));
        int freshnessMinutes = intValue(payload.get("freshness_minutes"), intValue(payload.get("freshnessMinutes"), 1440));

        jdbc.update("""
                INSERT INTO monitor_target (
                  id, tenant_id, platform, target_type, label, target_url, host, status,
                  crawl_strategy, freshness_minutes, latest_snapshot_id, latest_snapshot_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                """, id, tenantId, platform, targetType, label, targetUrl, host, status, crawlStrategy, freshnessMinutes, now, now);

        String scheduleId = "msch_" + UUID.randomUUID().toString().replace("-", "");
        jdbc.update("""
                INSERT INTO monitor_schedule (
                  id, tenant_id, target_id, enabled, schedule_type, cron_expr, interval_minutes,
                  next_run_at, last_run_at, max_products, retry_limit, created_at, updated_at
                ) VALUES (?, ?, ?, 1, 'interval', '', 1440, NULL, NULL, 100, 1, ?, ?)
                """, scheduleId, tenantId, id, now, now);

        return requireTarget(id, tenantId);
    }

    @Override
    @Transactional
    public Map<String, Object> updateTarget(String id, Map<String, Object> payload) {
        Long tenantId = dataScopeService.requireTenantId();
        Map<String, Object> existing = requireTargetRow(id, tenantId);
        String platform = text(payload, "platform", String.valueOf(existing.get("platform")));
        String targetType = text(payload, "target_type", text(payload, "targetType", String.valueOf(existing.get("target_type"))));
        String label = text(payload, "label", String.valueOf(existing.get("label")));
        String targetUrl = text(payload, "target_url", text(payload, "targetUrl", String.valueOf(existing.get("target_url"))));
        String status = text(payload, "status", String.valueOf(existing.get("status")));
        String crawlStrategy = text(payload, "crawl_strategy", text(payload, "crawlStrategy", String.valueOf(existing.get("crawl_strategy"))));
        targetUrl = validateAndMaybeCanonicalizeTemuShopUrl(platform, targetType, crawlStrategy, targetUrl);
        String host = text(payload, "host", parseHost(targetUrl));
        int freshnessMinutes = intValue(payload.get("freshness_minutes"), intValue(payload.get("freshnessMinutes"), intValue(existing.get("freshness_minutes"), 1440)));

        jdbc.update("""
                UPDATE monitor_target
                SET label = ?, target_url = ?, host = ?, status = ?, crawl_strategy = ?, freshness_minutes = ?, updated_at = ?
                WHERE tenant_id = ? AND id = ?
                """, label, targetUrl, host, status, crawlStrategy, freshnessMinutes, now(), tenantId, id);
        return requireTarget(id, tenantId);
    }

    @Override
    @Transactional
    public void deleteTarget(String id) {
        Long tenantId = dataScopeService.requireTenantId();
        requireTargetRow(id, tenantId);
        jdbc.update("DELETE FROM monitor_schedule WHERE tenant_id = ? AND target_id = ?", tenantId, id);
        jdbc.update("DELETE FROM monitor_target WHERE tenant_id = ? AND id = ?", tenantId, id);
    }

    @Override
    @Transactional
    public Map<String, Object> updateSchedule(String targetId, Map<String, Object> payload) {
        Long tenantId = dataScopeService.requireTenantId();
        requireTargetRow(targetId, tenantId);
        int enabled = boolValue(payload.get("enabled")) ? 1 : 0;
        String scheduleType = text(payload, "schedule_type", text(payload, "scheduleType", "interval"));
        String cronExpr = text(payload, "cron_expr", text(payload, "cronExpr", ""));
        int intervalMinutes = intValue(payload.get("interval_minutes"), intValue(payload.get("intervalMinutes"), 1440));
        int maxProducts = intValue(payload.get("max_products"), intValue(payload.get("maxProducts"), 100));
        int retryLimit = intValue(payload.get("retry_limit"), intValue(payload.get("retryLimit"), 1));
        String now = now();

        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM monitor_schedule WHERE tenant_id = ? AND target_id = ?",
                Integer.class,
                tenantId, targetId
        );
        if (count == null || count == 0) {
            jdbc.update("""
                    INSERT INTO monitor_schedule (
                      id, tenant_id, target_id, enabled, schedule_type, cron_expr, interval_minutes,
                      next_run_at, last_run_at, max_products, retry_limit, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
                    """,
                    "msch_" + UUID.randomUUID().toString().replace("-", ""),
                    tenantId, targetId, enabled, scheduleType, cronExpr, intervalMinutes, maxProducts, retryLimit, now, now
            );
        } else {
            jdbc.update("""
                    UPDATE monitor_schedule
                    SET enabled = ?, schedule_type = ?, cron_expr = ?, interval_minutes = ?,
                        max_products = ?, retry_limit = ?, updated_at = ?
                    WHERE tenant_id = ? AND target_id = ?
                    """, enabled, scheduleType, cronExpr, intervalMinutes, maxProducts, retryLimit, now, tenantId, targetId);
        }
        return requireTarget(targetId, tenantId);
    }

    @Override
    @Transactional
    public Map<String, Object> trigger(String targetId, Map<String, Object> payload) {
        Long tenantId = dataScopeService.requireTenantId();
        Map<String, Object> target = requireTargetRow(targetId, tenantId);
        reconcileStaleJobs(tenantId, targetId);

        List<Map<String, Object>> active = jdbc.query(
                """
                SELECT id, status, queued_at, started_at
                FROM monitor_job
                WHERE tenant_id = ? AND target_id = ? AND status IN ('pending', 'running')
                ORDER BY queued_at DESC
                LIMIT 1
                """,
                (rs, rn) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", rs.getString("id"));
                    row.put("status", rs.getString("status"));
                    row.put("queued_at", rs.getString("queued_at"));
                    row.put("started_at", rs.getString("started_at"));
                    return row;
                },
                tenantId, targetId
        );
        if (!active.isEmpty()) {
            Map<String, Object> job = active.get(0);
            throw new MonitorJobConflictException(toJobDto(job));
        }

        boolean force = boolValue(payload == null ? null : payload.get("force"));
        boolean bypassCooldown = boolValue(payload == null ? null : payload.get("bypass_cooldown"));
        // force / bypass_cooldown 任一即可跳过该竞店 monitor scope 冷却（30min；与平台 3h 解耦）
        crawlCooldownService.assertAllowed(
                tenantId,
                TenantCrawlCooldownService.monitorScope(targetId),
                force || bypassCooldown
        );
        String reason = text(payload, "reason", "manual refresh");
        String jobId = "mj_" + UUID.randomUUID().toString().replace("-", "");
        String now = now();
        Long userId = authContext.userId();

        jdbc.update("""
                INSERT INTO monitor_job (
                  id, tenant_id, target_id, schedule_id, platform, trigger_type, force, status,
                  attempt_no, queued_at, started_at, finished_at, worker_id, error_code, error_message,
                  error_detail, snapshot_id, created_by, reason
                ) VALUES (?, ?, ?, NULL, ?, 'manual', ?, 'pending', 1, ?, NULL, NULL, '', NULL, NULL, NULL, NULL, ?, ?)
                """,
                jobId,
                tenantId,
                targetId,
                String.valueOf(target.get("platform")),
                force ? 1 : 0,
                now,
                userId,
                reason
        );
        return toJobDto(Map.of("id", jobId, "status", "pending"));
    }

    @Override
    public Map<String, Object> getJob(String jobId) {
        Long tenantId = dataScopeService.requireTenantId();
        List<Map<String, Object>> rows = jdbc.query(
                "SELECT * FROM monitor_job WHERE tenant_id = ? AND id = ? LIMIT 1",
                (rs, rn) -> rsToMap(rs),
                tenantId, jobId
        );
        if (rows.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, AppErrorCode.MONITOR_JOB_NOT_FOUND.getUserMessage());
        }
        Map<String, Object> job = rows.get(0);
        reconcileStaleJob(job);
        rows = jdbc.query(
                "SELECT * FROM monitor_job WHERE tenant_id = ? AND id = ? LIMIT 1",
                (rs, rn) -> rsToMap(rs),
                tenantId, jobId
        );
        return toJobDto(rows.get(0));
    }

    @Override
    public Map<String, Object> getLatest(String targetId) {
        Long tenantId = dataScopeService.requireTenantId();
        Map<String, Object> target = requireTargetRow(targetId, tenantId);
        reconcileStaleJobs(tenantId, targetId);

        boolean hasFreshData = false;
        String latestSnapshotId = text(target, "latest_snapshot_id", "");
        String latestSnapshotAt = text(target, "latest_snapshot_at", "");
        int freshnessMinutes = intValue(target.get("freshness_minutes"), 1440);
        if (!latestSnapshotAt.isBlank()) {
            LocalDateTime snapshotAt = parseTime(latestSnapshotAt);
            if (snapshotAt != null) {
                long ageMinutes = ChronoUnit.MINUTES.between(snapshotAt, LocalDateTime.now());
                hasFreshData = ageMinutes <= freshnessMinutes;
            }
        }

        Map<String, Object> latestJob = findLatestJob(tenantId, targetId);
        String latestJobStatus = latestJob == null ? "" : text(latestJob, "status", "");
        boolean activeJob = ACTIVE_JOB_STATUSES.contains(latestJobStatus);
        boolean canTriggerNow = !activeJob;

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("target_id", targetId);
        out.put("has_fresh_data", hasFreshData);
        out.put("latest_snapshot_id", latestSnapshotId.isBlank() ? null : latestSnapshotId);
        out.put("latest_snapshot_at", latestSnapshotAt.isBlank() ? null : latestSnapshotAt);
        out.put("latest_job_status", latestJobStatus.isBlank() ? null : latestJobStatus);
        out.put("can_trigger_now", canTriggerNow);
        out.put("reason", activeJob ? "monitor job in progress" : (hasFreshData ? "fresh snapshot available" : "stale or missing snapshot"));

        Map<String, Object> summary = new LinkedHashMap<>();
        Map<String, Object> artifacts = new LinkedHashMap<>();
        List<Map<String, Object>> recentLaunches = List.of();
        List<Map<String, Object>> salesOutliers = List.of();

        if (!latestSnapshotId.isBlank()) {
            List<Map<String, Object>> snapshots = jdbc.query(
                    "SELECT * FROM monitor_snapshot WHERE tenant_id = ? AND id = ? LIMIT 1",
                    (rs, rn) -> rsToMap(rs),
                    tenantId, latestSnapshotId
            );
            if (!snapshots.isEmpty()) {
                Map<String, Object> snap = snapshots.get(0);
                summary.put("product_count", intValue(snap.get("product_count"), 0));
                summary.put("new_launch_count", intValue(snap.get("recent_launch_count"), 0));
                summary.put("sales_outlier_count", intValue(snap.get("sales_outlier_count"), 0));
                artifacts.put("report_md_path", text(snap, "report_md_path", ""));
                artifacts.put("report_xlsx_path", text(snap, "report_xlsx_path", ""));
            }
            recentLaunches = loadSignalProducts(tenantId, latestSnapshotId, "recent_launch");
            salesOutliers = loadSignalProducts(tenantId, latestSnapshotId, "sales_outlier");
        } else {
            summary.put("product_count", 0);
            summary.put("new_launch_count", 0);
            summary.put("sales_outlier_count", 0);
        }

        out.put("summary", summary);
        out.put("artifacts", artifacts);
        out.put("recent_launches", recentLaunches);
        out.put("sales_outliers", salesOutliers);
        List<Map<String, Object>> products = List.of();
        if (!latestSnapshotId.isBlank()) {
            products = jdbc.query("""
                    SELECT product_id, product_name, category, price, daily_sales, total_sales,
                           listed_at, url, image_url, shop_name, shop_url, rank, price_range, sale_text,
                           moq, good_rate, delivery_48h_rate,
                           dropship_7d, dropship_30d, dropship_heat, rebuy_rate, shop_return_rate,
                           quality_rate, shop_fans, is_pinned, suspicious
                    FROM monitor_product_snapshot
                    WHERE tenant_id = ? AND snapshot_id = ?
                    ORDER BY rank ASC, product_id ASC
                    LIMIT 200
                    """, (rs, rn) -> {
                        Map<String, Object> row = new LinkedHashMap<>();
                        row.put("product_id", rs.getString("product_id"));
                        row.put("product_name", rs.getString("product_name"));
                        row.put("category", rs.getString("category"));
                        row.put("price", rs.getDouble("price"));
                        row.put("daily_sales", rs.getInt("daily_sales"));
                        row.put("total_sales", rs.getInt("total_sales"));
                        row.put("listed_at", rs.getString("listed_at"));
                        row.put("url", rs.getString("url"));
                        row.put("image_url", rs.getString("image_url"));
                        row.put("shop_name", rs.getString("shop_name"));
                        row.put("shop_url", rs.getString("shop_url"));
                        row.put("rank", rs.getInt("rank"));
                        row.put("price_range", rs.getString("price_range"));
                        row.put("moq", rs.getString("moq"));
                        row.put("good_rate", rs.getString("good_rate"));
                        row.put("delivery_48h_rate", rs.getString("delivery_48h_rate"));
                        row.put("sale_text", rs.getString("sale_text"));
                        row.put("dropship_7d", rs.getString("dropship_7d"));
                        row.put("dropship_30d", rs.getString("dropship_30d"));
                        row.put("dropship_heat", rs.getInt("dropship_heat"));
                        row.put("rebuy_rate", rs.getString("rebuy_rate"));
                        row.put("shop_return_rate", rs.getString("shop_return_rate"));
                        row.put("quality_rate", rs.getString("quality_rate"));
                        row.put("shop_fans", rs.getInt("shop_fans"));
                        row.put("is_pinned", rs.getInt("is_pinned"));
                        row.put("suspicious", rs.getInt("suspicious"));
                        return row;
                    }, tenantId, latestSnapshotId);
        }
        out.put("products", products);
        return out;
    }

    @Override
    public Map<String, Object> getHistory(String targetId) {
        Long tenantId = dataScopeService.requireTenantId();
        requireTargetRow(targetId, tenantId);
        List<Map<String, Object>> snapshots = jdbc.query(
                """
                SELECT id AS snapshot_id, snapshot_at, product_count, recent_launch_count, sales_outlier_count
                FROM monitor_snapshot
                WHERE tenant_id = ? AND target_id = ?
                ORDER BY snapshot_at DESC
                LIMIT 20
                """,
                (rs, rn) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("snapshot_id", rs.getString("snapshot_id"));
                    row.put("snapshot_at", rs.getString("snapshot_at"));
                    row.put("product_count", rs.getInt("product_count"));
                    row.put("new_launch_count", rs.getInt("recent_launch_count"));
                    row.put("sales_outlier_count", rs.getInt("sales_outlier_count"));
                    return row;
                },
                tenantId, targetId
        );
        List<Map<String, Object>> jobs = jdbc.query(
                """
                SELECT id, status, trigger_type, queued_at, started_at, finished_at, error_code, error_message, reason
                FROM monitor_job
                WHERE tenant_id = ? AND target_id = ?
                ORDER BY queued_at DESC
                LIMIT 20
                """,
                (rs, rn) -> toJobDto(rsToMap(rs)),
                tenantId, targetId
        );
        return Map.of("snapshots", snapshots, "jobs", jobs);
    }

    @Override
    public Path resolveReportXlsx(String targetId) {
        Long tenantId = dataScopeService.requireTenantId();
        Map<String, Object> target = requireTargetRow(targetId, tenantId);
        String snapshotId = text(target, "latest_snapshot_id", "");
        if (snapshotId.isBlank()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, AppErrorCode.MONITOR_TARGET_NOT_FOUND.getUserMessage());
        }
        String reportPath = jdbc.query(
                "SELECT report_xlsx_path FROM monitor_snapshot WHERE tenant_id = ? AND id = ? LIMIT 1",
                rs -> rs.next() ? rs.getString(1) : "",
                tenantId, snapshotId
        );
        if (reportPath == null || reportPath.isBlank()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, AppErrorCode.NOT_FOUND.getUserMessage());
        }
        Path file = Path.of(crawlerProperties.getScriptDir()).toAbsolutePath().normalize().resolve(reportPath.replace("/", "\\"));
        if (!Files.isRegularFile(file)) {
            file = Path.of(crawlerProperties.getScriptDir()).toAbsolutePath().normalize().resolve(reportPath);
        }
        if (!Files.isRegularFile(file)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, AppErrorCode.NOT_FOUND.getUserMessage());
        }
        return file;
    }

    @Override
    public List<Map<String, Object>> getTrend(String targetId, int days, String productId) {
        Long tenantId = dataScopeService.requireTenantId();
        requireTargetRow(targetId, tenantId);
        int safeDays = Math.max(1, Math.min(days, 90));
        String since = LocalDateTime.now().minusDays(safeDays).format(TS);
        StringBuilder sql = new StringBuilder("""
                SELECT p.product_id, p.product_name, s.snapshot_at, p.price, p.total_sales,
                       p.daily_sales, p.rank, p.sale_text, p.is_pinned
                FROM monitor_product_snapshot p
                JOIN monitor_snapshot s ON s.id = p.snapshot_id
                WHERE p.tenant_id = ? AND p.target_id = ? AND s.snapshot_at >= ?
                """);
        List<Object> args = new ArrayList<>(List.of(tenantId, targetId, since));
        if (productId != null && !productId.isBlank()) {
            sql.append(" AND p.product_id = ?");
            args.add(productId.trim());
        }
        sql.append(" ORDER BY s.snapshot_at ASC, p.rank ASC");
        return jdbc.query(sql.toString(), (rs, rn) -> {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("product_id", rs.getString("product_id"));
            row.put("product_name", rs.getString("product_name"));
            row.put("snapshot_at", rs.getString("snapshot_at"));
            row.put("price", rs.getDouble("price"));
            row.put("total_sales", rs.getInt("total_sales"));
            row.put("daily_sales", rs.getInt("daily_sales"));
            row.put("rank", rs.getInt("rank"));
            row.put("sale_text", rs.getString("sale_text"));
            row.put("is_pinned", rs.getInt("is_pinned"));
            return row;
        }, args.toArray());
    }

    @Override
    public List<Map<String, Object>> getSignals(String targetId, int limit) {
        Long tenantId = dataScopeService.requireTenantId();
        requireTargetRow(targetId, tenantId);
        int safeLimit = Math.max(1, Math.min(limit, 200));
        return jdbc.query("""
                SELECT s.signal_type, s.signal_score, s.signal_value, s.created_at,
                       p.product_id, p.product_name, p.price, p.total_sales, p.daily_sales, p.url
                FROM monitor_signal s
                LEFT JOIN monitor_product_snapshot p
                  ON p.tenant_id = s.tenant_id AND p.snapshot_id = s.snapshot_id AND p.product_id = s.product_id
                WHERE s.tenant_id = ? AND s.target_id = ?
                ORDER BY s.created_at DESC
                LIMIT ?
                """, (rs, rn) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("signal_type", rs.getString("signal_type"));
                    row.put("signal_score", rs.getDouble("signal_score"));
                    row.put("signal_value", rs.getString("signal_value"));
                    row.put("created_at", rs.getString("created_at"));
                    row.put("product_id", rs.getString("product_id"));
                    row.put("product_name", rs.getString("product_name"));
                    row.put("price", rs.getDouble("price"));
                    row.put("total_sales", rs.getInt("total_sales"));
                    row.put("daily_sales", rs.getInt("daily_sales"));
                    row.put("url", rs.getString("url"));
                    return row;
                }, tenantId, targetId, safeLimit);
    }

    private List<Map<String, Object>> loadSignalProducts(Long tenantId, String snapshotId, String signalType) {
        return jdbc.query(
                """
                SELECT p.product_id, p.product_name, p.category, p.price, p.daily_sales, p.total_sales, p.listed_at, p.url, s.signal_value
                FROM monitor_signal s
                JOIN monitor_product_snapshot p
                  ON p.tenant_id = s.tenant_id AND p.snapshot_id = s.snapshot_id AND p.product_id = s.product_id
                WHERE s.tenant_id = ? AND s.snapshot_id = ? AND s.signal_type = ?
                ORDER BY p.daily_sales DESC
                """,
                (rs, rn) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("product_id", rs.getString("product_id"));
                    row.put("product_name", rs.getString("product_name"));
                    row.put("category", rs.getString("category"));
                    row.put("price", rs.getDouble("price"));
                    row.put("daily_sales", rs.getInt("daily_sales"));
                    row.put("total_sales", rs.getInt("total_sales"));
                    row.put("listed_at", rs.getString("listed_at"));
                    row.put("url", rs.getString("url"));
                    row.put("signal_value", rs.getString("signal_value"));
                    return row;
                },
                tenantId, snapshotId, signalType
        );
    }

    private Map<String, Object> findLatestJob(Long tenantId, String targetId) {
        List<Map<String, Object>> rows = jdbc.query(
                """
                SELECT * FROM monitor_job
                WHERE tenant_id = ? AND target_id = ?
                ORDER BY queued_at DESC
                LIMIT 1
                """,
                (rs, rn) -> rsToMap(rs),
                tenantId, targetId
        );
        return rows.isEmpty() ? null : rows.get(0);
    }

    private void reconcileStaleJobs(Long tenantId, String targetId) {
        List<Map<String, Object>> rows = jdbc.query(
                """
                SELECT * FROM monitor_job
                WHERE tenant_id = ? AND target_id = ? AND status IN ('pending', 'running')
                """,
                (rs, rn) -> rsToMap(rs),
                tenantId, targetId
        );
        for (Map<String, Object> job : rows) {
            reconcileStaleJob(job);
        }
    }

    private void reconcileStaleJob(Map<String, Object> job) {
        String status = text(job, "status", "");
        if (!ACTIVE_JOB_STATUSES.contains(status)) {
            return;
        }
        LocalDateTime base = parseTime("running".equals(status) ? text(job, "started_at", "") : text(job, "queued_at", ""));
        if (base == null) {
            markStaleJobFailed(String.valueOf(job.get("id")));
            return;
        }
        long ttl = "running".equals(status) ? RUNNING_TTL_SECONDS : PENDING_TTL_SECONDS;
        if (base.plusSeconds(ttl).isBefore(LocalDateTime.now())) {
            markStaleJobFailed(String.valueOf(job.get("id")));
        }
    }

    private void markStaleJobFailed(String jobId) {
        jdbc.update(
                """
                UPDATE monitor_job
                SET status = 'failed', finished_at = ?, error_code = ?, error_message = ?
                WHERE id = ? AND status IN ('pending', 'running')
                """,
                now(),
                AppErrorCode.CRAWL_INTERRUPTED.getCode(),
                AppErrorCode.CRAWL_INTERRUPTED.getUserMessage(),
                jobId
        );
    }

    private String validateAndMaybeCanonicalizeTemuShopUrl(
            String platform,
            String targetType,
            String crawlStrategy,
            String targetUrl
    ) {
        if ("1688".equalsIgnoreCase(platform) && "shop".equalsIgnoreCase(targetType)) {
            Alibaba1688MonitorUrlValidator.requireValidForCreate(targetUrl, crawlStrategy);
            return Alibaba1688MonitorUrlValidator.canonicalize(targetUrl);
        }
        boolean temuShopListing = "temu".equalsIgnoreCase(platform)
                && "shop".equalsIgnoreCase(targetType)
                && "store_listing".equalsIgnoreCase(crawlStrategy);
        if (!temuShopListing) {
            return targetUrl;
        }
        TemuMonitorUrlValidator.requireValidForCreate(targetUrl);
        return TemuMonitorUrlValidator.canonicalize(targetUrl);
    }

    private Map<String, Object> requireTarget(String id, Long tenantId) {
        return toTargetDto(requireTargetRow(id, tenantId));
    }

    private Map<String, Object> requireTargetRow(String id, Long tenantId) {
        List<Map<String, Object>> rows = jdbc.query(
                "SELECT * FROM monitor_target WHERE tenant_id = ? AND id = ? LIMIT 1",
                (rs, rn) -> rsToMap(rs),
                tenantId, id
        );
        if (rows.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, AppErrorCode.MONITOR_TARGET_NOT_FOUND.getUserMessage());
        }
        return rows.get(0);
    }

    private Map<String, Object> toTargetDto(Map<String, Object> row) {
        Map<String, Object> dto = new LinkedHashMap<>();
        dto.put("id", row.get("id"));
        dto.put("platform", row.get("platform"));
        dto.put("target_type", row.get("target_type"));
        dto.put("label", row.get("label"));
        dto.put("target_url", row.get("target_url"));
        dto.put("host", row.get("host"));
        dto.put("status", row.get("status"));
        dto.put("crawl_strategy", row.get("crawl_strategy"));
        dto.put("freshness_minutes", intValue(row.get("freshness_minutes"), 1440));
        dto.put("latest_snapshot_id", row.get("latest_snapshot_id"));
        dto.put("latest_snapshot_at", row.get("latest_snapshot_at"));
        dto.put("created_at", row.get("created_at"));
        dto.put("updated_at", row.get("updated_at"));
        return dto;
    }

    private Map<String, Object> toJobDto(Map<String, Object> row) {
        Map<String, Object> dto = new LinkedHashMap<>();
        dto.put("job_id", row.get("id"));
        dto.put("target_id", row.get("target_id"));
        dto.put("status", row.get("status"));
        dto.put("trigger_type", row.get("trigger_type"));
        dto.put("queued_at", row.get("queued_at"));
        dto.put("started_at", row.get("started_at"));
        dto.put("finished_at", row.get("finished_at"));
        dto.put("error_code", row.get("error_code"));
        dto.put("error_message", row.get("error_message"));
        dto.put("reason", row.get("reason"));
        dto.put("snapshot_id", row.get("snapshot_id"));
        return dto;
    }

    private Map<String, Object> rsToMap(java.sql.ResultSet rs) throws java.sql.SQLException {
        Map<String, Object> row = new LinkedHashMap<>();
        var meta = rs.getMetaData();
        for (int i = 1; i <= meta.getColumnCount(); i++) {
            row.put(meta.getColumnLabel(i), rs.getObject(i));
        }
        return row;
    }

    private String parseHost(String url) {
        try {
            String host = URI.create(url).getHost();
            if (host == null) {
                return "";
            }
            return host.startsWith("www.") ? host.substring(4) : host;
        } catch (Exception ex) {
            return "";
        }
    }

    private String text(Map<String, Object> map, String key, String fallback) {
        if (map == null) {
            return fallback;
        }
        Object value = map.get(key);
        if (value == null) {
            return fallback;
        }
        String text = String.valueOf(value).trim();
        return text.isEmpty() ? fallback : text;
    }

    private int intValue(Object value, int fallback) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        if (value == null) {
            return fallback;
        }
        try {
            return Integer.parseInt(String.valueOf(value).trim());
        } catch (Exception ex) {
            return fallback;
        }
    }

    private boolean boolValue(Object value) {
        if (value instanceof Boolean bool) {
            return bool;
        }
        if (value instanceof Number number) {
            return number.intValue() != 0;
        }
        if (value == null) {
            return false;
        }
        String text = String.valueOf(value).trim().toLowerCase(Locale.ROOT);
        return text.equals("1") || text.equals("true") || text.equals("yes");
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

    private String now() {
        return LocalDateTime.now().format(TS);
    }
}
