package com.crosshub.monitor.service.impl;

import com.crosshub.agent.entity.IntegrationAgent;
import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.alibaba1688.service.Alibaba1688AgentTasks;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** 竞店监控任务入队：为指定 monitor_target 创建 1688_monitor_crawl agent 任务。 */
@Service
public class MonitorAgentTaskEnqueuer {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final AgentPresenceService agentPresenceService;
    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;

    public MonitorAgentTaskEnqueuer(
            AgentPresenceService agentPresenceService,
            JdbcTemplate jdbc,
            ObjectMapper objectMapper
    ) {
        this.agentPresenceService = agentPresenceService;
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    public Map<String, Object> enqueue(Long tenantId, String targetId, String jobId) {
        Map<String, Object> fail = Map.of("queued", false, "message", "1688 本机助手不在线");
        if (tenantId == null || targetId == null || targetId.isBlank()) {
            return fail;
        }
        List<Map<String, Object>> targets = jdbc.queryForList(
                "SELECT id, target_url, crawl_strategy, config_json FROM monitor_target WHERE tenant_id = ? AND id = ? LIMIT 1",
                tenantId, targetId
        );
        if (targets.isEmpty()) {
            return fail;
        }
        IntegrationAgent agent = agentPresenceService.findLatestOnlineAgentForTenant(tenantId);
        if (agent == null || agent.getId() == null || agent.getId().isBlank()) {
            return fail;
        }
        Map<String, Object> target = targets.get(0);
        int topN = topNFromConfig(String.valueOf(target.get("config_json")));
        String taskId = "agt_" + UUID.randomUUID();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tenant_id", tenantId);
        payload.put("target_id", targetId);
        payload.put("job_id", jobId == null ? "" : jobId);
        payload.put("target_url", String.valueOf(target.get("target_url")));
        payload.put("crawl_strategy", String.valueOf(target.get("crawl_strategy")));
        payload.put("config_json", String.valueOf(target.get("config_json")));
        payload.put("top_n", topN);
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
                ) VALUES (?, ?, ?, ?, 'pending', ?, '{}', '', '', ?, '', '')
                """,
                taskId, tenantId, agent.getId(), Alibaba1688AgentTasks.MONITOR_CRAWL, payloadJson, now()
        );
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("queued", true);
        out.put("task_id", taskId);
        out.put("message", "已通知本机助手抓取竞店快照");
        return out;
    }

    private int topNFromConfig(String configJson) {
        try {
            Map<String, Object> config = objectMapper.readValue(
                    configJson == null || configJson.isBlank() ? "{}" : configJson,
                    new TypeReference<Map<String, Object>>() {}
            );
            Object topN = config.get("top_n");
            if (topN != null) {
                return Math.max(1, Math.min(Integer.parseInt(String.valueOf(topN)), 50));
            }
        } catch (Exception ignored) {
            // fall through
        }
        return 20;
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }
}
