package com.crosshub.amazon.service;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.agent.repository.AgentTaskRepository;
import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.platform.entity.PlatformAccount;
import com.crosshub.platform.repository.PlatformAccountRepository;
import com.crosshub.security.AuthContext;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class AmazonChatService {
    public static final String TASK_TYPE = "amazon_chat";

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final int MAX_MESSAGE_CHARS = 3000;

    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;
    private final DataScopeService dataScopeService;
    private final AuthContext authContext;
    private final PlatformAccountRepository platformAccountRepository;
    private final AgentTaskRepository agentTaskRepository;
    private final AgentPresenceService agentPresenceService;

    public AmazonChatService(
            JdbcTemplate jdbc,
            ObjectMapper objectMapper,
            DataScopeService dataScopeService,
            AuthContext authContext,
            PlatformAccountRepository platformAccountRepository,
            AgentTaskRepository agentTaskRepository,
            AgentPresenceService agentPresenceService
    ) {
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
        this.dataScopeService = dataScopeService;
        this.authContext = authContext;
        this.platformAccountRepository = platformAccountRepository;
        this.agentTaskRepository = agentTaskRepository;
        this.agentPresenceService = agentPresenceService;
    }

    @Transactional
    public Map<String, Object> submit(Map<String, Object> request) {
        Long tenantId = dataScopeService.requireTenantId();
        Long userId = authContext.userId();
        String storeId = text(request == null ? null : request.get("store_id"));
        if (storeId.isBlank()) {
            storeId = text(request == null ? null : request.get("platform_account_id"));
        }
        if (storeId.isBlank() || "all".equalsIgnoreCase(storeId)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请选择一个 Amazon 店铺后再提问");
        }
        String message = text(request == null ? null : request.get("message"));
        if (message.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "问题不能为空");
        }
        if (message.length() > MAX_MESSAGE_CHARS) {
            message = message.substring(0, MAX_MESSAGE_CHARS);
        }

        PlatformAccount account = platformAccountRepository.findByIdAndTenantId(storeId, tenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Amazon 店铺不存在"));
        if (!"amazon".equalsIgnoreCase(account.getPlatform())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "只能选择 Amazon 店铺");
        }

        String sessionId = normalizeId(text(request == null ? null : request.get("session_id")));
        if (sessionId.isBlank() || !sessionExists(tenantId, sessionId, storeId)) {
            sessionId = "amz_chat_sess_" + UUID.randomUUID();
            insertSession(sessionId, tenantId, userId, storeId);
        } else {
            touchSession(sessionId, "pending");
        }

        insertMessage("amz_chat_msg_" + UUID.randomUUID(), tenantId, sessionId, "user", message, "{}");

        String taskId = "amz_chat_task_" + UUID.randomUUID();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("platform", "amazon");
        payload.put("tenant_id", tenantId);
        payload.put("platform_account_id", account.getId());
        payload.put("store_id", account.getId());
        payload.put("store_name", defaultText(account.getStoreName(), ""));
        payload.put("external_shop_id", defaultText(account.getExternalShopId(), ""));
        payload.put("browser_id", defaultText(account.getExternalShopId(), ""));
        payload.put("browser_oauth", defaultText(account.getZiniaoBrowserOauth(), ""));
        payload.put("merchant_id", defaultText(account.getAmazonMerchantId(), ""));
        payload.put("session_id", sessionId);
        payload.put("message", message);
        payload.put("memory", listMemoryRows(tenantId, storeId));
        payload.put("data_snapshot", buildDataSnapshot(tenantId, account));

        AgentTask task = new AgentTask();
        task.setId(taskId);
        task.setTenantId(tenantId);
        task.setAgentId(resolveAgentId(tenantId));
        task.setTaskType(TASK_TYPE);
        task.setStatus("pending");
        task.setPayloadJson(writeJson(payload));
        task.setResultJson("{}");
        task.setErrorCode("");
        task.setErrorMessage("");
        task.setCreatedAt(now());
        task.setStartedAt("");
        task.setFinishedAt("");
        agentTaskRepository.save(task);

        return Map.of(
                "session_id", sessionId,
                "job_id", taskId,
                "task_type", TASK_TYPE,
                "status", "pending"
        );
    }

    @Transactional
    public Map<String, Object> getJob(String jobId) {
        Long tenantId = dataScopeService.requireTenantId();
        AgentTask task = agentTaskRepository.findByIdAndTenantId(jobId, tenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "聊天任务不存在"));
        Map<String, Object> payload = parseJson(task.getPayloadJson());
        String sessionId = text(payload.get("session_id"));
        Map<String, Object> result = parseJson(task.getResultJson());
        String status = defaultText(task.getStatus(), "pending");
        if ("success".equalsIgnoreCase(status) || "failed".equalsIgnoreCase(status)) {
            appendTerminalAssistantMessage(task, tenantId, sessionId, result);
            touchSession(sessionId, status);
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("job_id", task.getId());
        out.put("session_id", sessionId);
        out.put("status", status);
        out.put("error_code", defaultText(task.getErrorCode(), ""));
        out.put("error_message", defaultText(task.getErrorMessage(), ""));
        out.put("answer", text(result.get("answer")));
        out.put("source", result.get("source"));
        out.put("captured_at", text(result.get("captured_at")));
        out.put("duration_ms", result.getOrDefault("duration_ms", 0));
        out.put("token_usage", result.getOrDefault("token_usage", Map.of()));
        out.put("created_at", defaultText(task.getCreatedAt(), ""));
        out.put("started_at", defaultText(task.getStartedAt(), ""));
        out.put("finished_at", defaultText(task.getFinishedAt(), ""));
        return out;
    }

    public List<Map<String, Object>> listSessions(String storeId, int limit) {
        Long tenantId = dataScopeService.requireTenantId();
        int safeLimit = Math.max(1, Math.min(limit <= 0 ? 20 : limit, 100));
        if (storeId == null || storeId.isBlank() || "all".equalsIgnoreCase(storeId)) {
            return jdbc.queryForList(
                    """
                    SELECT id, tenant_id, user_id, store_id, platform, status, created_at, updated_at
                    FROM amazon_chat_session
                    WHERE tenant_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    tenantId, safeLimit
            );
        }
        return jdbc.queryForList(
                """
                SELECT id, tenant_id, user_id, store_id, platform, status, created_at, updated_at
                FROM amazon_chat_session
                WHERE tenant_id = ? AND store_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                tenantId, storeId.trim(), safeLimit
        );
    }

    public List<Map<String, Object>> listMessages(String sessionId) {
        Long tenantId = dataScopeService.requireTenantId();
        String id = normalizeId(sessionId);
        if (id.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "session_id 不能为空");
        }
        assertSessionTenant(tenantId, id);
        return jdbc.queryForList(
                """
                SELECT id, session_id, role, content, tool_calls, created_at
                FROM amazon_chat_message
                WHERE tenant_id = ? AND session_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                tenantId, id
        );
    }

    public List<Map<String, Object>> listMemory(String storeId) {
        Long tenantId = dataScopeService.requireTenantId();
        String id = normalizeId(storeId);
        if (id.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "store_id 不能为空");
        }
        return listMemoryRows(tenantId, id);
    }

    @Transactional
    public Map<String, Object> clearMemory(String storeId) {
        Long tenantId = dataScopeService.requireTenantId();
        String id = normalizeId(storeId);
        if (id.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "store_id 不能为空");
        }
        int deleted = jdbc.update(
                "DELETE FROM amazon_chat_memory WHERE tenant_id = ? AND store_id = ?",
                tenantId, id
        );
        return Map.of("store_id", id, "deleted", deleted);
    }

    private void appendTerminalAssistantMessage(AgentTask task, Long tenantId, String sessionId, Map<String, Object> result) {
        if (sessionId == null || sessionId.isBlank()) {
            return;
        }
        Integer existing = jdbc.queryForObject(
                """
                SELECT COUNT(1)
                FROM amazon_chat_message
                WHERE tenant_id = ? AND session_id = ? AND role = 'assistant' AND tool_calls LIKE ?
                """,
                Integer.class,
                tenantId, sessionId, "%" + task.getId() + "%"
        );
        if (existing != null && existing > 0) {
            return;
        }
        String content = text(result.get("answer"));
        if (content.isBlank()) {
            content = task.getErrorMessage() == null || task.getErrorMessage().isBlank()
                    ? "本次 Amazon AI 问答未返回结果"
                    : task.getErrorMessage();
        }
        Map<String, Object> toolCalls = new LinkedHashMap<>();
        toolCalls.put("agent_task_id", task.getId());
        toolCalls.put("source", result.get("source"));
        toolCalls.put("captured_at", result.get("captured_at"));
        toolCalls.put("duration_ms", result.getOrDefault("duration_ms", 0));
        toolCalls.put("token_usage", result.getOrDefault("token_usage", Map.of()));
        insertMessage("amz_chat_msg_" + UUID.randomUUID(), tenantId, sessionId, "assistant", content, writeJson(toolCalls));
        insertToolLogs(task, tenantId, sessionId, result);
    }

    private void insertToolLogs(AgentTask task, Long tenantId, String sessionId, Map<String, Object> result) {
        Object raw = result.get("tool_calls");
        if (!(raw instanceof List<?> calls) || calls.isEmpty()) {
            return;
        }
        for (int i = 0; i < calls.size(); i++) {
            Object item = calls.get(i);
            if (!(item instanceof Map<?, ?> call)) {
                continue;
            }
            String toolName = text(call.get("tool_name"));
            if (toolName.isBlank()) {
                toolName = text(call.get("name"));
            }
            Object args = call.get("args");
            String argsJson = writeJson(args instanceof Map<?, ?> ? args : Map.of());
            String summary = text(call.get("summary"));
            int ok = Boolean.TRUE.equals(call.get("ok")) ? 1 : 0;
            int durationMs = intValue(call.get("duration_ms"));
            jdbc.update(
                    """
                    INSERT OR IGNORE INTO amazon_chat_tool_log (
                      id, tenant_id, session_id, tool_name, args_json, result_summary, ok, duration_ms, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    "amz_chat_tool_" + task.getId() + "_" + i,
                    tenantId,
                    sessionId,
                    toolName,
                    argsJson,
                    summary,
                    ok,
                    durationMs,
                    now()
            );
        }
    }

    private String resolveAgentId(Long tenantId) {
        var agent = agentPresenceService.findLatestOnlineAgentForTenant(tenantId);
        return agent == null ? "" : defaultText(agent.getId(), "");
    }

    private void insertSession(String sessionId, Long tenantId, Long userId, String storeId) {
        jdbc.update(
                """
                INSERT INTO amazon_chat_session (
                  id, tenant_id, user_id, store_id, platform, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'amazon', 'pending', ?, ?)
                """,
                sessionId, tenantId, userId, storeId, now(), now()
        );
    }

    private void touchSession(String sessionId, String status) {
        if (sessionId == null || sessionId.isBlank()) {
            return;
        }
        jdbc.update(
                "UPDATE amazon_chat_session SET status = ?, updated_at = ? WHERE id = ?",
                defaultText(status, "pending"), now(), sessionId
        );
    }

    private void insertMessage(String id, Long tenantId, String sessionId, String role, String content, String toolCalls) {
        jdbc.update(
                """
                INSERT INTO amazon_chat_message (
                  id, tenant_id, session_id, role, content, tool_calls, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                id, tenantId, sessionId, role, content, defaultText(toolCalls, "{}"), now()
        );
        touchSession(sessionId, "pending");
    }

    private boolean sessionExists(Long tenantId, String sessionId, String storeId) {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(1) FROM amazon_chat_session WHERE tenant_id = ? AND id = ? AND store_id = ?",
                Integer.class,
                tenantId, sessionId, storeId
        );
        return count != null && count > 0;
    }

    private void assertSessionTenant(Long tenantId, String sessionId) {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(1) FROM amazon_chat_session WHERE tenant_id = ? AND id = ?",
                Integer.class,
                tenantId, sessionId
        );
        if (count == null || count <= 0) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "聊天会话不存在");
        }
    }

    private List<Map<String, Object>> listMemoryRows(Long tenantId, String storeId) {
        return jdbc.queryForList(
                """
                SELECT id, store_id, mem_key, mem_value, ttl_at, updated_at
                FROM amazon_chat_memory
                WHERE tenant_id = ? AND store_id = ?
                ORDER BY updated_at DESC
                """,
                tenantId, storeId
        );
    }

    private Map<String, Object> buildDataSnapshot(Long tenantId, PlatformAccount account) {
        Map<String, Object> snapshot = new LinkedHashMap<>();
        snapshot.put("source", "crosshub_local_amazon_tables");
        snapshot.put("store_id", account.getId());
        snapshot.put("store_name", defaultText(account.getStoreName(), ""));
        snapshot.put("captured_at", now());
        snapshot.put("account_metrics", queryRows("""
                SELECT metric_key, metric_label, status, value_text, threshold_text, trend, note_text, synced_at
                FROM amazon_account_metric
                WHERE tenant_id = ? AND platform_account_id = ?
                ORDER BY synced_at DESC
                LIMIT 20
                """, tenantId, account.getId()));
        snapshot.put("operational_items", queryRows("""
                SELECT item_type, external_key, payload_json, synced_at
                FROM amazon_operational_item
                WHERE tenant_id = ? AND platform_account_id = ?
                ORDER BY synced_at DESC
                LIMIT 40
                """, tenantId, account.getId()));
        snapshot.put("top_products", queryRows("""
                SELECT asin, sku, product_name, orders_30d, revenue_30d, page_views, inventory,
                       acos, ad_spend_30d, tacos, conversion_rate, period_days, rank_no, currency, synced_at
                FROM amazon_product_snapshot
                WHERE tenant_id = ? AND platform_account_id = ?
                ORDER BY rank_no ASC, orders_30d DESC
                LIMIT 20
                """, tenantId, account.getId()));
        return snapshot;
    }

    private List<Map<String, Object>> queryRows(String sql, Object... args) {
        try {
            return jdbc.queryForList(sql, args);
        } catch (Exception ex) {
            return List.of();
        }
    }

    private Map<String, Object> parseJson(String raw) {
        if (raw == null || raw.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(raw, new TypeReference<Map<String, Object>>() {});
        } catch (Exception ex) {
            return Map.of();
        }
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value == null ? Map.of() : value);
        } catch (Exception ex) {
            return "{}";
        }
    }

    private static String now() {
        return LocalDateTime.now().format(TS);
    }

    private static String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static String normalizeId(String value) {
        return value == null ? "" : value.trim();
    }

    private static String defaultText(String value, String fallback) {
        if (value == null || value.isBlank()) {
            return fallback == null ? "" : fallback;
        }
        return value;
    }

    private static int intValue(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (Exception ex) {
            return 0;
        }
    }
}
