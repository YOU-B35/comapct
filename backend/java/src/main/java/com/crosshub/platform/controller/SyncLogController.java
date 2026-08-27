package com.crosshub.platform.controller;

import com.crosshub.common.ApiResult;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 全平台统一「最近同步日志」：读取 agent_task（本机助手执行的所有平台任务），
 * 供各模块页面实时展示同步状态与耗时。
 */
@RestController
@RequestMapping("/api/sync-logs")
public class SyncLogController {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final JdbcTemplate jdbc;
    private final DataScopeService dataScopeService;
    private final ObjectMapper objectMapper;

    public SyncLogController(JdbcTemplate jdbc, DataScopeService dataScopeService, ObjectMapper objectMapper) {
        this.jdbc = jdbc;
        this.dataScopeService = dataScopeService;
        this.objectMapper = objectMapper;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(value = "platform", required = false) String platform,
            @RequestParam(value = "limit", required = false) Integer limit
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        int n = limit == null ? 30 : Math.max(1, Math.min(200, limit));

        StringBuilder sql = new StringBuilder(
                "SELECT task_type, status, created_at, started_at, finished_at, error_code, error_message, result_json "
                        + "FROM agent_task WHERE tenant_id = ? "
                        + "AND status IN ('pending','running','success','failed','partial') "
        );
        List<Object> args = new ArrayList<>();
        args.add(tenantId);
        String p = platform == null ? "" : platform.trim().toLowerCase();
        if (!p.isEmpty()) {
            sql.append("AND (task_type LIKE ? OR task_type LIKE ?) ");
            args.add(p + "%");
            args.add("%_" + p + "%");
        }
        sql.append("ORDER BY created_at DESC LIMIT ?");
        args.add(n);

        List<Map<String, Object>> items = new ArrayList<>();
        jdbc.query(sql.toString(), rs -> {
            String taskType = rs.getString("task_type");
            String status = normalizeStatus(rs.getString("status"));
            String resultJson = rs.getString("result_json");
            // 任务以 success 收尾但结果标记 partial=true（如“全部店铺”同步时部分店铺未登录）时，
            // 统一展示为“部分成功”。
            if ("success".equals(status) && resultJson != null && !resultJson.isBlank()) {
                try {
                    Map<?, ?> body = objectMapper.readValue(resultJson, Map.class);
                    if (Boolean.TRUE.equals(body.get("partial"))) {
                        status = "partial";
                    }
                } catch (Exception ignored) {
                    // 非 JSON 结果忽略
                }
            }
            String startedAt = rs.getString("started_at");
            String finishedAt = rs.getString("finished_at");
            Long durationMs = durationMs(startedAt, finishedAt, status);
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", taskType + "@" + startedAt + "@" + finishedAt);
            row.put("task_type", taskType);
            row.put("label", taskLabel(taskType));
            row.put("status", status);
            row.put("startedAt", startedAt == null ? "" : startedAt);
            row.put("finishedAt", finishedAt == null ? "" : finishedAt);
            row.put("durationMs", durationMs == null ? null : durationMs);
            row.put("createdAt", rs.getString("created_at") == null ? "" : rs.getString("created_at"));
            row.put("errorCode", rs.getString("error_code"));
            row.put("errorMessage", rs.getString("error_message"));
            row.put("summary", summary(resultJson));
            putCounts(row, resultJson);
            items.add(row);
        }, args.toArray());

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("items", items);
        data.put("count", items.size());
        return ApiResult.ok(data);
    }

    private String normalizeStatus(String status) {
        if (status == null || status.isBlank()) return "pending";
        String s = status.toLowerCase();
        if (s.equals("success")) return "success";
        if (s.equals("failed")) return "failed";
        if (s.equals("running")) return "running";
        if (s.equals("partial")) return "partial";
        return "pending";
    }

    private Long durationMs(String startedAt, String finishedAt, String status) {
        LocalDateTime start = parseTs(startedAt);
        if (start == null) return null;
        LocalDateTime end = parseTs(finishedAt);
        if (end == null && "running".equalsIgnoreCase(status)) {
            end = LocalDateTime.now();
        }
        if (end == null) return null;
        return Math.max(0, java.time.Duration.between(start, end).toMillis());
    }

    private LocalDateTime parseTs(String text) {
        if (text == null || text.isBlank()) return null;
        try {
            return LocalDateTime.parse(text.trim(), TS);
        } catch (Exception ex) {
            return null;
        }
    }

    private String summary(String resultJson) {
        if (resultJson == null || resultJson.isBlank()) return "";
        try {
            Map<?, ?> body = objectMapper.readValue(resultJson, Map.class);
            Object msg = body.get("message");
            if (msg != null && !String.valueOf(msg).isBlank()) {
                return String.valueOf(msg);
            }
            Object count = body.get("products_count");
            if (count == null) count = body.get("orders_count");
            if (count == null) count = body.get("issues_count");
            if (count != null && !String.valueOf(count).isBlank()) {
                return "同步 " + count + " 条";
            }
        } catch (Exception ignored) {
            // 非 JSON 或字段缺失时返回空
        }
        return "";
    }

    private void putCounts(Map<String, Object> row, String resultJson) {
        if (resultJson == null || resultJson.isBlank()) return;
        try {
            Map<?, ?> body = objectMapper.readValue(resultJson, Map.class);
            for (String key : new String[]{
                    "products_count",
                    "orders_count",
                    "issues_count",
                    "compass_count",
                    "peer_bestsellers_count",
                    "rows_count",
            }) {
                Object value = body.get(key);
                if (value != null && !String.valueOf(value).isBlank()) {
                    try {
                        row.put(key, Long.parseLong(String.valueOf(value)));
                    } catch (NumberFormatException ignored) {
                        row.put(key, String.valueOf(value));
                    }
                }
            }
        } catch (Exception ignored) {
            // 非 JSON 或字段缺失时忽略
        }
    }

    private String taskLabel(String type) {
        if (type == null || type.isBlank()) return "同步任务";
        String t = type.toLowerCase();
        String platform;
        if (t.startsWith("douyin_")) platform = "抖音";
        else if (t.startsWith("pdd_")) platform = "拼多多";
        else if (t.startsWith("1688_") || t.startsWith("alibaba1688_")) platform = "1688";
        else if (t.startsWith("aliexpress_") || t.startsWith("ae_")) platform = "速卖通";
        else if (t.startsWith("amazon_")) platform = "Amazon";
        else if (t.startsWith("temu_")) platform = "Temu";
        else if (t.startsWith("taobao_")) platform = "淘宝";
        else platform = "跨平台";

        String scope;
        if (t.contains("products_sync")) scope = "商品同步";
        else if (t.contains("orders_sync") || t.equals("pdd_sync")) scope = "订单同步";
        else if (t.contains("issues_sync")) scope = "内容预警";
        else if (t.contains("compass")) scope = "罗盘";
        else if (t.contains("opportunity")) scope = "商机";
        else if (t.contains("login_open")) scope = "打开登录";
        else if (t.contains("session_probe")) scope = "会话探测";
        else if (t.contains("peer_bestsellers")) scope = "同行爆款";
        else if (t.contains("monitor_crawl")) scope = "监控爬取";
        else if (t.contains("crawl")) scope = "数据爬取";
        else scope = "同步";
        return platform + "·" + scope;
    }
}
