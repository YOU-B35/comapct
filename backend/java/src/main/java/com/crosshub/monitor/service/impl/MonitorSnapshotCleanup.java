package com.crosshub.monitor.service.impl;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 旧快照清理：每天清理 90 天前且超出每目标最近 200 次之外的快照（含信号与商品明细）。 */
@Component
public class MonitorSnapshotCleanup {
    private static final Logger log = LoggerFactory.getLogger(MonitorSnapshotCleanup.class);
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final int KEEP_LATEST = 200;

    private final JdbcTemplate jdbc;

    public MonitorSnapshotCleanup(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Scheduled(cron = "${crosshub.monitor.cleanup.cron:0 30 3 * * *}", zone = "Asia/Shanghai")
    public void cleanupOldSnapshots() {
        String cutoff = LocalDateTime.now().minusDays(90).format(TS);
        List<Map<String, Object>> targets = jdbc.queryForList(
                "SELECT id, tenant_id FROM monitor_target WHERE platform = '1688' AND status = 'active'"
        );
        int totalDeleted = 0;
        for (Map<String, Object> target : targets) {
            String targetId = String.valueOf(target.get("id"));
            Long tenantId = toLong(target.get("tenant_id"));
            List<String> keepIds = jdbc.queryForList(
                    """
                    SELECT id FROM monitor_snapshot
                    WHERE tenant_id = ? AND target_id = ?
                    ORDER BY snapshot_at DESC LIMIT ?
                    """,
                    String.class, tenantId, targetId, KEEP_LATEST
            );
            Set<String> keep = new HashSet<>(keepIds);
            List<String> oldIds = jdbc.queryForList(
                    """
                    SELECT id FROM monitor_snapshot
                    WHERE tenant_id = ? AND target_id = ? AND snapshot_at < ?
                    ORDER BY snapshot_at DESC
                    """,
                    String.class, tenantId, targetId, cutoff
            );
            for (String snapshotId : oldIds) {
                if (keep.contains(snapshotId)) {
                    continue;
                }
                jdbc.update("DELETE FROM monitor_signal WHERE tenant_id = ? AND snapshot_id = ?", tenantId, snapshotId);
                jdbc.update("DELETE FROM monitor_product_snapshot WHERE tenant_id = ? AND snapshot_id = ?", tenantId, snapshotId);
                jdbc.update("DELETE FROM monitor_snapshot WHERE tenant_id = ? AND id = ?", tenantId, snapshotId);
                totalDeleted++;
            }
        }
        if (totalDeleted > 0) {
            log.info("[MonitorCleanup] deleted {} old snapshots (cutoff={})", totalDeleted, cutoff);
        }
    }

    private Long toLong(Object value) {
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (Exception ex) {
            return 0L;
        }
    }
}
