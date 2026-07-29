package com.crosshub.temu.service;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.common.AppErrorCode;
import com.crosshub.common.TenantCrawlCooldownService;
import com.crosshub.config.CrawlerProperties;
import com.crosshub.platform.service.PlatformAccountService;
import com.crosshub.temu.entity.TemuCrawlJob;
import com.crosshub.temu.repository.TemuCrawlJobRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
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
public class TemuAgentService {
    private static final Logger log = LoggerFactory.getLogger(TemuAgentService.class);
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final long SESSION_PROBE_COOLDOWN_SECONDS = 8;

    private final AgentPresenceService agentPresenceService;
    private final CrawlerProperties crawlerProperties;
    private final TemuCrawlJobRepository jobRepository;
    private final TemuAgentIngestService ingestService;
    private final PlatformAccountService platformAccountService;
    private final TenantCrawlCooldownService crawlCooldownService;
    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;

    public TemuAgentService(
            AgentPresenceService agentPresenceService,
            CrawlerProperties crawlerProperties,
            TemuCrawlJobRepository jobRepository,
            TemuAgentIngestService ingestService,
            PlatformAccountService platformAccountService,
            TenantCrawlCooldownService crawlCooldownService,
            JdbcTemplate jdbc,
            ObjectMapper objectMapper
    ) {
        this.agentPresenceService = agentPresenceService;
        this.crawlerProperties = crawlerProperties;
        this.jobRepository = jobRepository;
        this.ingestService = ingestService;
        this.platformAccountService = platformAccountService;
        this.crawlCooldownService = crawlCooldownService;
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    public boolean useAgentMode() {
        return crawlerProperties.isUseAgent();
    }

    public void assertAgentOnline(Long tenantId) {
        if (!useAgentMode()) {
            return;
        }
        if (!agentPresenceService.isAgentOnline(tenantId)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    AppErrorCode.TEMU_AGENT_OFFLINE.getUserMessage()
            );
        }
    }

    public Map<String, Object> integrationStatus(Long tenantId) {
        Map<String, Object> out = new LinkedHashMap<>(agentPresenceService.integrationStatus(tenantId));
        out.put("mode", useAgentMode() ? "agent" : "local");
        return out;
    }

    @Transactional
    public void enqueueCrawlJob(TemuCrawlJob job) {
        String taskId = "agt_" + UUID.randomUUID();
        job.setAgentTaskId(taskId);
        jobRepository.save(job);

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenant_id", job.getTenantId());
        payload.put("job_id", job.getId());
        payload.put("mode", job.getMode());
        payload.put("report_time", job.getReportTime() == null ? "" : job.getReportTime());
        payload.put("seed", "seed".equals(job.getMode()));
        insertAgentTask(job.getTenantId(), taskId, TemuAgentTasks.CRAWL, payload);
    }

    @Transactional
    public Map<String, Object> enqueueLoginOpen(Long tenantId) {
        assertAgentOnline(tenantId);
        String taskId = "agt_" + UUID.randomUUID();
        Map<String, Object> payload = Map.of("tenant_id", tenantId);
        insertAgentTask(tenantId, taskId, TemuAgentTasks.LOGIN_OPEN, payload);
        return Map.of(
                "tenant_id", tenantId,
                "queued", true,
                "mode", "agent",
                "task_id", taskId,
                "message", "已通知本机同步助手打开 Temu 登录窗口，请在弹出的 CrossHub 浏览器中完成登录"
        );
    }

    @Transactional
    public Map<String, Object> enqueueFrontendLoginOpen(Long tenantId, String url) {
        assertAgentOnline(tenantId);
        String taskId = "agt_" + UUID.randomUUID();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenant_id", tenantId);
        if (url != null && !url.isBlank()) {
            payload.put("url", url.trim());
        }
        insertAgentTask(tenantId, taskId, TemuAgentTasks.FRONTEND_LOGIN_OPEN, payload);
        return Map.of(
                "tenant_id", tenantId,
                "queued", true,
                "mode", "agent",
                "task_id", taskId,
                "engine", "manual_chrome",
                "message", "已通知本机同步助手打开普通 Chrome（Temu 买家前台登录）。请完成登录后关闭该 Chrome，再重试竞店发现"
        );
    }

    public Map<String, Object> readSessionSnapshot(Long tenantId) {
        List<Map<String, Object>> rows = jdbc.query(
                """
                SELECT payload_json, updated_at
                FROM temu_session_snapshot
                WHERE tenant_id = ?
                LIMIT 1
                """,
                (rs, rowNum) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("payload_json", rs.getString("payload_json"));
                    row.put("updated_at", rs.getString("updated_at"));
                    return row;
                },
                tenantId
        );
        if (rows.isEmpty()) {
            return defaultSessionPayload(tenantId);
        }
        try {
            String payloadJson = String.valueOf(rows.get(0).get("payload_json"));
            Map<String, Object> payload = objectMapper.readValue(
                    payloadJson == null || payloadJson.isBlank() ? "{}" : payloadJson,
                    new TypeReference<Map<String, Object>>() {}
            );
            payload.putIfAbsent("tenant_id", tenantId);
            payload.put("snapshot_at", rows.get(0).get("updated_at"));
            return payload;
        } catch (Exception ex) {
            return defaultSessionPayload(tenantId);
        }
    }

    /**
     * Temu 会话诊断信息（替代抓日志）。
     * 返回 tenant 维度的 session snapshot + 最近的登录/会话探测 agent_task 记录。
     */
    public Map<String, Object> sessionDebug(Long tenantId) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("mode", useAgentMode() ? "agent" : "local");
        out.put("agent_online", useAgentMode() ? agentPresenceService.isAgentOnline(tenantId) : null);
        out.put("snapshot", readSessionSnapshot(tenantId));

        if (useAgentMode()) {
            Map<String, Object> snapshot = (Map<String, Object>) out.get("snapshot");
            String snapshotAt = stringValue(snapshot.get("snapshot_at"));
            LocalDateTime updated = parseTime(snapshotAt);
            if (updated != null) {
                out.put(
                        "probe_cooldown_until",
                        updated.plusSeconds(SESSION_PROBE_COOLDOWN_SECONDS).format(TS)
                );
            } else {
                out.put("probe_cooldown_until", "");
            }

            List<Map<String, Object>> tasks = jdbc.query(
                    """
                    SELECT
                      id,
                      task_type,
                      status,
                      error_code,
                      error_message,
                      created_at,
                      started_at,
                      finished_at
                    FROM agent_task
                    WHERE tenant_id = ?
                      AND task_type IN (?, ?, ?)
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    (rs, rowNum) -> {
                        Map<String, Object> row = new LinkedHashMap<>();
                        row.put("id", rs.getString("id"));
                        row.put("task_type", rs.getString("task_type"));
                        row.put("status", rs.getString("status"));
                        row.put("error_code", rs.getString("error_code"));
                        row.put("error_message", rs.getString("error_message"));
                        row.put("created_at", rs.getString("created_at"));
                        row.put("started_at", rs.getString("started_at"));
                        row.put("finished_at", rs.getString("finished_at"));
                        return row;
                    },
                    tenantId,
                    TemuAgentTasks.LOGIN_OPEN,
                    TemuAgentTasks.FRONTEND_LOGIN_OPEN,
                    TemuAgentTasks.SESSION_PROBE
            );
            out.put("recent_tasks", tasks);
        }

        return out;
    }

    @Transactional
    public void maybeEnqueueSessionProbe(Long tenantId) {
        if (!useAgentMode() || !agentPresenceService.isAgentOnline(tenantId)) {
            return;
        }
        Map<String, Object> snapshot = readSessionSnapshot(tenantId);
        String snapshotAt = stringValue(snapshot.get("snapshot_at"));
        LocalDateTime updated = parseTime(snapshotAt);
        if (updated != null && updated.plusSeconds(SESSION_PROBE_COOLDOWN_SECONDS).isAfter(LocalDateTime.now())) {
            return;
        }
        Integer pending = jdbc.queryForObject(
                """
                SELECT COUNT(*) FROM agent_task
                WHERE tenant_id = ? AND task_type = ? AND status IN ('pending', 'running')
                """,
                Integer.class,
                tenantId,
                TemuAgentTasks.SESSION_PROBE
        );
        if (pending != null && pending > 0) {
            return;
        }
        String taskId = "agt_" + UUID.randomUUID();
        insertAgentTask(tenantId, taskId, TemuAgentTasks.SESSION_PROBE, Map.of("tenant_id", tenantId));
    }

    @Transactional
    public Map<String, Object> ingestFromAgent(Long tenantId, Map<String, Object> payload) {
        if (payload.get("tenant_id") != null) {
            long requested = Long.parseLong(String.valueOf(payload.get("tenant_id")).split("\\.")[0]);
            if (requested != tenantId) {
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, AppErrorCode.FORBIDDEN.getUserMessage());
            }
        }
        return ingestService.ingest(tenantId, payload);
    }

    @Transactional
    public void onAgentTaskStarted(AgentTask task) {
        if (task == null || !TemuAgentTasks.CRAWL.equals(task.getTaskType())) {
            return;
        }
        TemuCrawlJob job = findJobByAgentTaskId(task.getId());
        if (job == null || !List.of("pending", "running").contains(job.getStatus())) {
            return;
        }
        job.setStatus("running");
        if (job.getStartedAt() == null || job.getStartedAt().isBlank()) {
            job.setStartedAt(now());
        }
        jobRepository.save(job);
    }

    @Transactional
    public void onAgentTaskCompleted(
            AgentTask task,
            String status,
            Map<String, Object> result,
            String errorCode,
            String errorMessage
    ) {
        if (task == null) {
            return;
        }
        String taskType = task.getTaskType();
        if (TemuAgentTasks.CRAWL.equals(taskType)) {
            completeCrawlTask(task, status, result, errorCode, errorMessage);
            return;
        }
        if (TemuAgentTasks.LOGIN_OPEN.equals(taskType)
                || TemuAgentTasks.FRONTEND_LOGIN_OPEN.equals(taskType)
                || TemuAgentTasks.SESSION_PROBE.equals(taskType)) {
            completeSessionTask(task.getTenantId(), status, result, errorCode, errorMessage);
        }
    }

    private void completeCrawlTask(
            AgentTask task,
            String status,
            Map<String, Object> result,
            String errorCode,
            String errorMessage
    ) {
        TemuCrawlJob job = findJobByAgentTaskId(task.getId());
        if (job == null) {
            return;
        }
        if (!"success".equalsIgnoreCase(status)) {
            job.setStatus("failed");
            job.setFinishedAt(now());
            job.setErrorCode(defaultText(errorCode, AppErrorCode.CRAWL_PROCESS_FAILED.getCode()));
            job.setErrorMessage(defaultText(errorMessage, AppErrorCode.CRAWL_PROCESS_FAILED.getUserMessage()));
            jobRepository.save(job);
            return;
        }

        Map<String, Object> safe = result == null ? Map.of() : result;
        if (safe.get("report_time") != null) {
            job.setReportTime(String.valueOf(safe.get("report_time")));
        }
        if (safe.get("shops") != null) {
            job.setShopsCount(intValue(safe.get("shops")));
        }
        if (safe.get("rows") != null) {
            job.setRowsCount(intValue(safe.get("rows")));
        }
        job.setStatus("success");
        job.setFinishedAt(now());
        job.setErrorCode("");
        job.setErrorMessage("");
        jobRepository.save(job);
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

    private void completeSessionTask(
            Long tenantId,
            String status,
            Map<String, Object> result,
            String errorCode,
            String errorMessage
    ) {
        if (!"success".equalsIgnoreCase(status)) {
            Map<String, Object> payload = defaultSessionPayload(tenantId);
            if (errorMessage != null && !errorMessage.isBlank()) {
                payload.put("message", errorMessage);
            }
            if (errorCode != null && !errorCode.isBlank()) {
                payload.put("error_code", errorCode);
            }
            saveSessionSnapshot(tenantId, payload);
            return;
        }
        Map<String, Object> session = result == null ? Map.of() : result;
        if (session.containsKey("session")) {
            Object nested = session.get("session");
            if (nested instanceof Map<?, ?> map) {
                Map<String, Object> payload = new LinkedHashMap<>();
                for (Map.Entry<?, ?> entry : map.entrySet()) {
                    payload.put(String.valueOf(entry.getKey()), entry.getValue());
                }
                saveSessionSnapshot(tenantId, payload);
                return;
            }
        }
        saveSessionSnapshot(tenantId, session);
    }

    @Transactional
    public void saveSessionSnapshot(Long tenantId, Map<String, Object> payload) {
        String json;
        try {
            json = objectMapper.writeValueAsString(payload == null ? Map.of() : payload);
        } catch (Exception ex) {
            json = "{}";
        }
        jdbc.update(
                """
                INSERT INTO temu_session_snapshot (tenant_id, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                  payload_json = excluded.payload_json,
                  updated_at = excluded.updated_at
                """,
                tenantId,
                json,
                now()
        );
    }

    private TemuCrawlJob findJobByAgentTaskId(String taskId) {
        return jobRepository.findFirstByAgentTaskId(taskId).orElse(null);
    }

    private void insertAgentTask(Long tenantId, String taskId, String taskType, Map<String, Object> payload) {
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
                "",
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

    private Map<String, Object> defaultSessionPayload(Long tenantId) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenant_id", tenantId);
        payload.put("ready", false);
        payload.put("logged_in", false);
        payload.put("profile_busy", false);
        payload.put("requires_auth", true);
        payload.put("mall_id", "");
        payload.put("mall_count", 0);
        payload.put("malls", List.of());
        payload.put("message", useAgentMode()
                ? "请联系运维启动 CrossHub-Sync-Helper.exe"
                : "未检测到会话");
        return payload;
    }

    private String defaultText(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    private int intValue(Object value) {
        if (value == null) {
            return 0;
        }
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value).trim().split("\\.")[0]);
        } catch (NumberFormatException ex) {
            return 0;
        }
    }

    private String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
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
