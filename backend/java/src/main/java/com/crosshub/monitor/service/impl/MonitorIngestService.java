package com.crosshub.monitor.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 1688 竞店监控快照入库：本机助手爬取后 POST 回线上后端，落库并计算日增量与信号。
 * 数据按 tenant_id + target_id 存储，同租户所有账号共享最新快照。
 */
@Service
public class MonitorIngestService {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final long SUSPICIOUS_DELTA_CAP = 200000L;
    private static final int MAX_PRODUCTS = 200;
    private static final int MAX_RAW_JSON_LENGTH = 4000;

    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;

    public MonitorIngestService(JdbcTemplate jdbc, ObjectMapper objectMapper) {
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public Map<String, Object> ingestSnapshot(Long tenantId, Map<String, Object> body) {
        if (tenantId == null || body == null || body.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "缺少入库数据");
        }
        String targetId = text(body, "target_id", text(body, "targetId", ""));
        if (targetId.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "缺少 target_id");
        }
        List<Map<String, Object>> targets = jdbc.queryForList(
                "SELECT id, platform FROM monitor_target WHERE tenant_id = ? AND id = ? LIMIT 1",
                tenantId, targetId
        );
        if (targets.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "监控目标不存在");
        }
        String jobId = text(body, "job_id", text(body, "jobId", ""));
        String snapshotAt = text(body, "snapshot_at", "");
        if (snapshotAt.isBlank()) {
            snapshotAt = now();
        }
        List<Map<String, Object>> products = parseList(body.get("products"));
        if (products.size() > MAX_PRODUCTS) {
            products = products.subList(0, MAX_PRODUCTS);
        }
        if (!jobId.isBlank()) {
            String existingSnapshot = jdbc.query(
                    "SELECT snapshot_id FROM monitor_job WHERE id = ? AND tenant_id = ? LIMIT 1",
                    rs -> rs.next() ? rs.getString(1) : "",
                    jobId, tenantId
            );
            if (existingSnapshot != null && !existingSnapshot.isBlank()) {
                Map<String, Object> out = new LinkedHashMap<>();
                out.put("snapshot_id", existingSnapshot);
                out.put("product_count", 0);
                out.put("signal_count", 0);
                out.put("skipped_duplicate", true);
                return out;
            }
        }

        Map<String, Prior> prior = loadPrior(tenantId, targetId);
        String snapshotId = "ms_" + UUID.randomUUID().toString().replace("-", "");
        String createdAt = now();

        jdbc.update(
                """
                INSERT INTO monitor_snapshot (
                  id, tenant_id, target_id, platform, snapshot_at, product_count,
                  recent_launch_count, sales_outlier_count, report_md_path, report_xlsx_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, '', '', ?)
                """,
                snapshotId, tenantId, targetId, targets.get(0).get("platform"), snapshotAt,
                products.size(), createdAt
        );

        Set<String> currentIds = new LinkedHashSet<>();
        List<Map<String, Object>> signals = new ArrayList<>();
        int inserted = 0;
        for (Map<String, Object> p : products) {
            String pid = text(p, "product_id", "");
            if (pid.isBlank()) {
                continue;
            }
            currentIds.add(pid);
            long total = longVal(p.get("total_sales"));
            double price = doubleVal(p.get("price"));
            long daily = longVal(p.get("daily_sales"));
            int suspicious = 0;
            Prior pr = prior.get(pid);
            if (pr != null && daily == 0) {
                long delta = total - pr.totalSales;
                if (delta >= 0 && delta <= SUSPICIOUS_DELTA_CAP) {
                    daily = delta;
                } else {
                    suspicious = 1;
                }
            }
            if (pr == null) {
                int rank = intVal(p.get("rank"));
                if (rank > 0) {
                    signals.add(signal(tenantId, targetId, snapshotId, pid,
                            "bestseller_new_entry", 1.0, json(Map.of("rank", rank))));
                }
            } else {
                if (pr.price > 0 && price > 0 && Math.abs(pr.price - price) > 0.001) {
                    signals.add(signal(tenantId, targetId, snapshotId, pid,
                            "price_change", 1.0, json(Map.of("old", pr.price, "new", price))));
                }
                if (pr.expired == 1 && intVal(p.get("expired")) == 0) {
                    signals.add(signal(tenantId, targetId, snapshotId, pid,
                            "delist_or_relist", 1.0, json(Map.of("status", "relisted"))));
                }
            }
            jdbc.update(
                    """
                    INSERT INTO monitor_product_snapshot (
                      id, tenant_id, snapshot_id, target_id, product_id, product_name,
                      category, price, daily_sales, total_sales, listed_at, url, image_url,
                      shop_name, shop_url, rank, price_range, moq, good_rate, delivery_48h_rate, sale_text,
                      dropship_7d, dropship_30d, dropship_heat, rebuy_rate, shop_return_rate,
                      quality_rate, shop_fans, attrs_json, is_pinned, status, expired,
                      suspicious, raw_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    "mps_" + snapshotId + "_" + pid,
                    tenantId,
                    snapshotId,
                    targetId,
                    pid,
                    text(p, "product_name", ""),
                    text(p, "category", ""),
                    price,
                    daily,
                    total,
                    text(p, "listed_at", ""),
                    text(p, "url", ""),
                    text(p, "image_url", ""),
                    text(p, "shop_name", ""),
                    text(p, "shop_url", ""),
                    intVal(p.get("rank")),
                    text(p, "price_range", ""),
                    text(p, "moq", ""),
                    text(p, "good_rate", ""),
                    text(p, "delivery_48h_rate", ""),
                    text(p, "sale_text", ""),
                    text(p, "dropship_7d", ""),
                    text(p, "dropship_30d", ""),
                    intVal(p.get("dropship_heat")),
                    text(p, "rebuy_rate", ""),
                    text(p, "shop_return_rate", ""),
                    text(p, "quality_rate", ""),
                    intVal(p.get("shop_fans")),
                    text(p, "attrs_json", ""),
                    intVal(p.get("is_pinned")),
                    text(p, "status", ""),
                    intVal(p.get("expired")),
                    suspicious,
                    truncate(text(p, "raw_json", "")),
                    createdAt
            );
            inserted++;
        }
        for (Map.Entry<String, Prior> entry : prior.entrySet()) {
            if (!currentIds.contains(entry.getKey()) && !entry.getValue().status.isBlank()) {
                signals.add(signal(tenantId, targetId, snapshotId, entry.getKey(),
                        "delist_or_relist", 1.0, json(Map.of("status", "delisted"))));
            }
        }
        for (Map<String, Object> sig : signals) {
            jdbc.update(
                    """
                    INSERT INTO monitor_signal (
                      id, tenant_id, snapshot_id, target_id, product_id, signal_type,
                      signal_score, signal_value, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    sig.get("id"), tenantId, snapshotId, targetId, sig.get("product_id"),
                    sig.get("signal_type"), sig.get("signal_score"), sig.get("signal_value"), createdAt
            );
        }
        jdbc.update(
                """
                UPDATE monitor_target
                SET latest_snapshot_id = ?, latest_snapshot_at = ?, updated_at = ?
                WHERE tenant_id = ? AND id = ?
                """,
                snapshotId, snapshotAt, createdAt, tenantId, targetId
        );
        if (!jobId.isBlank()) {
            jdbc.update(
                    """
                    UPDATE monitor_job
                    SET status = 'success', finished_at = ?, snapshot_id = ?,
                        error_code = NULL, error_message = NULL, error_detail = NULL
                    WHERE id = ? AND tenant_id = ? AND status IN ('pending', 'running')
                    """,
                    createdAt, snapshotId, jobId, tenantId
            );
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("snapshot_id", snapshotId);
        out.put("target_id", targetId);
        out.put("product_count", inserted);
        out.put("signal_count", signals.size());
        out.put("snapshot_at", snapshotAt);
        return out;
    }

    private Map<String, Prior> loadPrior(Long tenantId, String targetId) {
        Map<String, Prior> prior = new LinkedHashMap<>();
        jdbc.query(
                """
                SELECT p.product_id, p.total_sales, p.price, p.status, p.expired, s.snapshot_at
                FROM monitor_product_snapshot p
                JOIN monitor_snapshot s ON s.id = p.snapshot_id
                WHERE p.tenant_id = ? AND p.target_id = ?
                ORDER BY s.snapshot_at DESC
                """,
                (rs) -> {
                    String pid = rs.getString("product_id");
                    if (pid != null && !prior.containsKey(pid)) {
                        prior.put(pid, new Prior(
                                rs.getLong("total_sales"),
                                rs.getDouble("price"),
                                rs.getString("status") == null ? "" : rs.getString("status"),
                                rs.getInt("expired")
                        ));
                    }
                },
                tenantId, targetId
        );
        return prior;
    }

    private Map<String, Object> signal(
            Long tenantId, String targetId, String snapshotId, String productId,
            String type, double score, String value
    ) {
        Map<String, Object> sig = new LinkedHashMap<>();
        sig.put("id", "sig_" + UUID.randomUUID().toString().replace("-", ""));
        sig.put("tenant_id", tenantId);
        sig.put("target_id", targetId);
        sig.put("snapshot_id", snapshotId);
        sig.put("product_id", productId);
        sig.put("signal_type", type);
        sig.put("signal_score", score);
        sig.put("signal_value", value);
        return sig;
    }

    private List<Map<String, Object>> parseList(Object raw) {
        List<Map<String, Object>> out = new ArrayList<>();
        if (raw instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map<?, ?> map) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    for (Map.Entry<?, ?> entry : map.entrySet()) {
                        row.put(String.valueOf(entry.getKey()), entry.getValue());
                    }
                    out.add(row);
                }
            }
        }
        return out;
    }

    private String json(Map<String, Object> value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception ex) {
            return "{}";
        }
    }

    private String truncate(String value) {
        if (value == null || value.length() <= MAX_RAW_JSON_LENGTH) {
            return value == null ? "" : value;
        }
        return value.substring(0, MAX_RAW_JSON_LENGTH);
    }

    private String text(Map<String, Object> map, String key, String fallback) {
        Object value = map.get(key);
        return value == null ? fallback : String.valueOf(value);
    }

    private long longVal(Object value) {
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (Exception ex) {
            return 0L;
        }
    }

    private int intVal(Object value) {
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (Exception ex) {
            return 0;
        }
    }

    private double doubleVal(Object value) {
        try {
            return Double.parseDouble(String.valueOf(value));
        } catch (Exception ex) {
            return 0.0;
        }
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }

    private static final class Prior {
        final long totalSales;
        final double price;
        final String status;
        final int expired;

        Prior(long totalSales, double price, String status, int expired) {
            this.totalSales = totalSales;
            this.price = price;
            this.status = status;
            this.expired = expired;
        }
    }
}
