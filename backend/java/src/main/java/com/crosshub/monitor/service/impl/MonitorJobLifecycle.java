package com.crosshub.monitor.service.impl;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.alibaba1688.service.Alibaba1688AgentTasks;
import com.crosshub.pdd.service.PddAgentTasks;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Map;

/** agent 任务与 monitor_job 的状态桥接：agent 失败时把对应 monitor_job 标记失败，避免排程器卡死。 */
@Component
public class MonitorJobLifecycle {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;

    public MonitorJobLifecycle(JdbcTemplate jdbc, ObjectMapper objectMapper) {
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    public void onAgentTaskCompleted(AgentTask task, String status, String errorMessage) {
        if (task == null || !isMonitorCrawlTask(task.getTaskType())) {
            return;
        }
        String jobId = jobIdFromPayload(task.getPayloadJson());
        if (jobId.isBlank()) {
            return;
        }
        boolean failed = status != null && !"success".equals(status);
        if (!failed) {
            return;
        }
        String now = LocalDateTime.now().format(TS);
        jdbc.update(
                """
                UPDATE monitor_job
                SET status = 'failed', finished_at = ?, error_code = 'MONITOR_AGENT_TASK_FAILED',
                    error_message = ?
                WHERE id = ? AND status IN ('pending', 'running')
                """,
                now, errorMessage == null ? "agent task failed" : errorMessage, jobId
        );
    }

    private boolean isMonitorCrawlTask(String taskType) {
        return Alibaba1688AgentTasks.MONITOR_CRAWL.equals(taskType)
                || PddAgentTasks.MONITOR_CRAWL.equals(taskType);
    }

    private String jobIdFromPayload(String payloadJson) {
        try {
            Map<String, Object> payload = objectMapper.readValue(
                    payloadJson == null || payloadJson.isBlank() ? "{}" : payloadJson,
                    new TypeReference<Map<String, Object>>() {}
            );
            Object jobId = payload.get("job_id");
            return jobId == null ? "" : String.valueOf(jobId);
        } catch (Exception ex) {
            return "";
        }
    }
}
