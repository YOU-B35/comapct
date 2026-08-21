package com.crosshub.monitor.service.impl;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.UUID;

/** 竞店监控排程器：扫描 monitor_schedule 到期项，创建 monitor_job 并派发 agent 任务。 */
@Component
public class MonitorTaskScheduler {
    private static final Logger log = LoggerFactory.getLogger(MonitorTaskScheduler.class);
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final JdbcTemplate jdbc;
    private final MonitorAgentTaskEnqueuer enqueuer;
    private final Random random = new Random();

    public MonitorTaskScheduler(JdbcTemplate jdbc, MonitorAgentTaskEnqueuer enqueuer) {
        this.jdbc = jdbc;
        this.enqueuer = enqueuer;
    }

    @Scheduled(fixedDelayString = "${crosshub.monitor.scheduler.delay-ms:60000}")
    public void enqueueDueSchedules() {
        String now = now();
        List<Map<String, Object>> due = jdbc.queryForList(
                """
                SELECT s.id AS schedule_id, s.tenant_id, s.target_id, s.interval_minutes, t.platform
                FROM monitor_schedule s
                JOIN monitor_target t ON t.id = s.target_id AND t.tenant_id = s.tenant_id
                WHERE s.enabled = 1 AND t.status = 'active'
                  AND (s.next_run_at IS NULL OR s.next_run_at <= ?)
                """,
                now
        );
        for (Map<String, Object> row : due) {
            Long tenantId = toLong(row.get("tenant_id"));
            String targetId = String.valueOf(row.get("target_id"));
            String scheduleId = String.valueOf(row.get("schedule_id"));
            String platform = String.valueOf(row.get("platform"));
            int intervalMinutes = Math.max(1, toInt(row.get("interval_minutes")));
            try {
                Integer active = jdbc.queryForObject(
                        """
                        SELECT COUNT(1) FROM monitor_job
                        WHERE tenant_id = ? AND target_id = ? AND status IN ('pending', 'running')
                        """,
                        Integer.class, tenantId, targetId
                );
                if (active != null && active > 0) {
                    advanceNextRun(scheduleId, now, intervalMinutes);
                    continue;
                }
                String jobId = "mj_" + UUID.randomUUID().toString().replace("-", "");
                jdbc.update(
                        """
                        INSERT INTO monitor_job (
                          id, tenant_id, target_id, schedule_id, platform, trigger_type, force, status,
                          attempt_no, queued_at, started_at, finished_at, worker_id, error_code,
                          error_message, error_detail, snapshot_id, created_by, reason
                        ) VALUES (?, ?, ?, ?, ?, 'scheduled', 0, 'pending', 1, ?, '', '', '', '', '', '', '', NULL, 'scheduled')
                        """,
                        jobId, tenantId, targetId, scheduleId, platform, now
                );
                Map<String, Object> result = enqueuer.enqueue(tenantId, targetId, jobId);
                if (!Boolean.TRUE.equals(result.get("queued"))) {
                    jdbc.update(
                            """
                            UPDATE monitor_job
                            SET status = 'failed', finished_at = ?, error_code = 'A1688_AGENT_OFFLINE',
                                error_message = ?
                            WHERE id = ? AND status = 'pending'
                            """,
                            now(), String.valueOf(result.get("message")), jobId
                    );
                }
                advanceNextRun(scheduleId, now, intervalMinutes);
            } catch (Exception ex) {
                log.warn("[MonitorScheduler] target={} schedule failed: {}", targetId, ex.toString());
                advanceNextRun(scheduleId, now, intervalMinutes);
            }
        }
    }

    private void advanceNextRun(String scheduleId, String now, int intervalMinutes) {
        int jitterSeconds = random.nextInt(601);
        LocalDateTime next = LocalDateTime.parse(now, TS)
                .plusMinutes(intervalMinutes)
                .plusSeconds(jitterSeconds);
        jdbc.update(
                "UPDATE monitor_schedule SET next_run_at = ?, last_run_at = ?, updated_at = ? WHERE id = ?",
                next.format(TS), now, now, scheduleId
        );
    }

    private Long toLong(Object value) {
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (Exception ex) {
            return 0L;
        }
    }

    private int toInt(Object value) {
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (Exception ex) {
            return 1440;
        }
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }
}
