package com.crosshub.amazon.service;

import com.crosshub.amazon.dto.AmazonSyncRequest;
import com.crosshub.amazon.entity.AmazonSyncJob;

import java.util.Map;

public interface AmazonSyncService {
    Map<String, Object> triggerSync(AmazonSyncRequest request);
    Map<String, Object> triggerSyncForTenant(Long tenantId, AmazonSyncRequest request);
    AmazonSyncJob getJob(String jobId);
    void onAgentTaskStarted(String taskId);
    void onAgentTaskCompleted(String taskId, String status, Map<String, Object> result, String errorCode, String errorMessage);

    /** 系统日批：按租户入队账户状况同步（不依赖登录态） */
    Map<String, Object> enqueueDailySync(Long tenantId);

    /** 系统日批；force=true 忽略「今日已跑过」 */
    Map<String, Object> enqueueDailySync(Long tenantId, boolean force);

    /** 打开应用展示用：最近一次 Amazon 任务摘要 */
    Map<String, Object> buildSyncStatus(Long tenantId);

    /** Helper 运维日志：列出租户最近 Amazon 同步任务 */
    Map<String, Object> listRecentJobsForTenant(Long tenantId);
}
