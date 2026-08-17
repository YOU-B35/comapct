package com.crosshub.alibaba1688.service;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.agent.entity.IntegrationAgent;
import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.common.AppErrorCode;
import com.crosshub.platform.entity.PlatformAccount;
import com.crosshub.platform.repository.PlatformAccountRepository;
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
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class Alibaba1688SessionService {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final DataScopeService dataScopeService;
    private final AgentPresenceService agentPresenceService;
    private final PlatformAccountRepository platformAccountRepository;
    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;

    public Alibaba1688SessionService(
            DataScopeService dataScopeService,
            AgentPresenceService agentPresenceService,
            PlatformAccountRepository platformAccountRepository,
            JdbcTemplate jdbc,
            ObjectMapper objectMapper
    ) {
        this.dataScopeService = dataScopeService;
        this.agentPresenceService = agentPresenceService;
        this.platformAccountRepository = platformAccountRepository;
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    public Map<String, Object> session() {
        Long tenantId = dataScopeService.requireTenantId();
        boolean agentOnline = agentPresenceService.isAgentOnline(tenantId);
        boolean profileBusy = hasRunningBusy(tenantId);
        Map<String, Object> snapshot = readSessionSnapshot(tenantId);
        boolean loggedIn = Boolean.TRUE.equals(snapshot.get("logged_in"))
                || Boolean.TRUE.equals(snapshot.get("ready"));
        Map<String, Object> out = new LinkedHashMap<>(snapshot);
        out.put("tenant_id", tenantId);
        out.put("agent_online", agentOnline);
        out.put("profile_busy", profileBusy || Boolean.TRUE.equals(snapshot.get("profile_busy")));
        out.put("logged_in", loggedIn);
        out.put("ready", loggedIn && agentOnline && !profileBusy);
        out.putIfAbsent("requires_auth", !loggedIn);
        if (!agentOnline) {
            out.put("message", AppErrorCode.A1688_AGENT_OFFLINE.getUserMessage());
            out.put("requires_auth", true);
            out.put("ready", false);
        } else if (profileBusy) {
            out.putIfAbsent("message", "1688 浏览器任务进行中，请稍候");
        } else if (!loggedIn) {
            out.putIfAbsent("message", "请打开登录窗口完成 1688 买家登录");
        }
        List<PlatformAccount> shops = platformAccountRepository
                .findByTenantIdAndPlatformOrderByBoundAtDesc(tenantId, "1688");
        out.put("shop_count", shops.size());
        List<Map<String, Object>> shopRows = new ArrayList<>();
        for (PlatformAccount shop : shops) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", shop.getId());
            row.put("store_name", shop.getStoreName());
            row.put("external_shop_id", shop.getExternalShopId() == null ? "" : shop.getExternalShopId());
            shopRows.add(row);
        }
        out.put("shops", shopRows);
        return out;
    }

    @Transactional
    public Map<String, Object> enqueueLoginOpen() {
        Long tenantId = dataScopeService.requireTenantId();
        IntegrationAgent agent = requireOnlineAgent(tenantId);
        if (hasRunningBusy(tenantId)) {
            return Map.of(
                    "already_open", true,
                    "queued", false,
                    "message", "1688 浏览器任务进行中，请稍候或点「我已完成登录」刷新状态"
            );
        }
        String taskId = "agt_" + UUID.randomUUID();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenant_id", tenantId);
        insertAgentTask(tenantId, taskId, Alibaba1688AgentTasks.LOGIN_OPEN, payload, agent.getId());
        writeSessionSnapshot(tenantId, Map.of(
                "tenant_id", tenantId,
                "ready", false,
                "logged_in", false,
                "requires_auth", true,
                "profile_busy", true,
                "message", "登录窗口已打开，请在弹出的浏览器中完成 1688 登录"
        ));
        return Map.of(
                "queued", true,
                "task_id", taskId,
                "message", "已通知本机助手打开 1688 登录窗口"
        );
    }

    @Transactional
    public Map<String, Object> enqueueSessionProbe() {
        Long tenantId = dataScopeService.requireTenantId();
        IntegrationAgent agent = requireOnlineAgent(tenantId);
        if (hasRunningBusy(tenantId)) {
            return Map.of(
                    "queued", false,
                    "message", "1688 浏览器任务进行中，请稍候再刷新登录状态"
            );
        }
        String taskId = "agt_" + UUID.randomUUID();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenant_id", tenantId);
        insertAgentTask(tenantId, taskId, Alibaba1688AgentTasks.SESSION_PROBE, payload, agent.getId());
        writeSessionSnapshot(tenantId, Map.of(
                "tenant_id", tenantId,
                "ready", false,
                "logged_in", false,
                "requires_auth", true,
                "profile_busy", true,
                "message", "正在检测 1688 登录状态…"
        ));
        return Map.of(
                "queued", true,
                "task_id", taskId,
                "message", "已通知本机助手检测 1688 登录状态"
        );
    }

    @Transactional
    public void onAgentTaskCompleted(
            AgentTask task,
            String status,
            Map<String, Object> result,
            String errorCode,
            String errorMessage
    ) {
        if (task == null || !Alibaba1688AgentTasks.BROWSER_BUSY_TYPES.contains(task.getTaskType())) {
            return;
        }
        Long tenantId = task.getTenantId();
        Map<String, Object> session = result == null ? Map.of() : result;
        Object nested = session.get("session");
        if (nested instanceof Map<?, ?> map) {
            Map<String, Object> copy = new LinkedHashMap<>();
            for (Map.Entry<?, ?> e : map.entrySet()) {
                copy.put(String.valueOf(e.getKey()), e.getValue());
            }
            session = copy;
        }
        Map<String, Object> snap = new LinkedHashMap<>(session);
        snap.put("tenant_id", tenantId);
        if ("success".equalsIgnoreCase(status)) {
            boolean loggedIn = Boolean.TRUE.equals(snap.get("logged_in"))
                    || Boolean.TRUE.equals(snap.get("ready"));
            snap.put("logged_in", loggedIn);
            snap.put("ready", loggedIn);
            snap.put("requires_auth", !loggedIn);
            snap.put("profile_busy", false);
            snap.putIfAbsent("message", loggedIn ? "1688 已登录" : "登录未完成，请重试打开登录");
        } else {
            snap.put("logged_in", false);
            snap.put("ready", false);
            snap.put("requires_auth", true);
            snap.put("profile_busy", false);
            snap.put("message", errorMessage == null || errorMessage.isBlank()
                    ? AppErrorCode.A1688_LOGIN_FAILED.getUserMessage()
                    : errorMessage);
            if (errorCode != null && !errorCode.isBlank()) {
                snap.put("error_code", errorCode);
            }
        }
        writeSessionSnapshot(tenantId, snap);
    }

    public void onAgentTaskStarted(AgentTask task) {
        // Login/probe only — no sync job to mark running yet.
    }

    private IntegrationAgent requireOnlineAgent(Long tenantId) {
        IntegrationAgent agent = agentPresenceService.findLatestOnlineAgentForTenant(tenantId);
        if (agent == null || agent.getId() == null || agent.getId().isBlank()) {
            throw new ResponseStatusException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    AppErrorCode.A1688_AGENT_OFFLINE.getUserMessage()
            );
        }
        return agent;
    }

    private boolean hasRunningBusy(Long tenantId) {
        Integer count = jdbc.queryForObject(
                """
                SELECT COUNT(1) FROM agent_task
                WHERE tenant_id = ?
                  AND status IN ('pending', 'running')
                  AND task_type IN ('1688_session_probe', '1688_login_open')
                """,
                Integer.class,
                tenantId
        );
        return count != null && count > 0;
    }

    private Map<String, Object> readSessionSnapshot(Long tenantId) {
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT payload_json FROM alibaba1688_session_snapshot WHERE tenant_id = ? LIMIT 1",
                tenantId
        );
        if (rows.isEmpty()) {
            Map<String, Object> defaults = new LinkedHashMap<>();
            defaults.put("tenant_id", tenantId);
            defaults.put("ready", false);
            defaults.put("logged_in", false);
            defaults.put("requires_auth", true);
            defaults.put("profile_busy", false);
            defaults.put("message", "尚未登录 1688 买家后台");
            defaults.put("shop_count", 0);
            defaults.put("shops", List.of());
            return defaults;
        }
        return parseJson(String.valueOf(rows.get(0).get("payload_json")));
    }

    private void writeSessionSnapshot(Long tenantId, Map<String, Object> payload) {
        String json;
        try {
            json = objectMapper.writeValueAsString(payload == null ? Map.of() : payload);
        } catch (Exception ex) {
            json = "{}";
        }
        jdbc.update(
                """
                INSERT INTO alibaba1688_session_snapshot (tenant_id, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET payload_json = excluded.payload_json, updated_at = excluded.updated_at
                """,
                tenantId,
                json,
                now()
        );
    }

    private void insertAgentTask(
            Long tenantId,
            String taskId,
            String taskType,
            Map<String, Object> payload,
            String agentId
    ) {
        String payloadJson;
        try {
            payloadJson = objectMapper.writeValueAsString(payload);
        } catch (Exception ex) {
            payloadJson = "{}";
        }
        jdbc.update(
                """
                INSERT INTO agent_task (
                  id, tenant_id, agent_id, task_type, status, payload_json, result_json,
                  error_code, error_message, created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                taskId,
                tenantId,
                agentId == null ? "" : agentId,
                taskType,
                "pending",
                payloadJson,
                "{}",
                "",
                "",
                now(),
                "",
                ""
        );
    }

    private Map<String, Object> parseJson(String json) {
        try {
            return objectMapper.readValue(
                    json == null || json.isBlank() ? "{}" : json,
                    new TypeReference<Map<String, Object>>() {}
            );
        } catch (Exception ex) {
            return new LinkedHashMap<>();
        }
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }
}
