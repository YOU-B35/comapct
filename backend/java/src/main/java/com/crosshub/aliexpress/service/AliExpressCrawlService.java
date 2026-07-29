package com.crosshub.aliexpress.service;

import com.crosshub.aliexpress.dto.AliExpressCrawlRequest;
import com.crosshub.aliexpress.entity.AliExpressCrawlJob;

import java.util.Map;

public interface AliExpressCrawlService {
    AliExpressCrawlJob triggerCrawl(AliExpressCrawlRequest request);
    AliExpressCrawlJob triggerViolationSync();
    AliExpressCrawlJob triggerViolationSync(boolean force);
    AliExpressCrawlJob triggerViolationSync(boolean force, boolean recordCooldown);
    AliExpressCrawlJob getJob(String jobId);

    /** 系统日批：按租户入队（不依赖登录态） */
    Map<String, Object> enqueueDailyCrawl(Long tenantId);

    /** 系统日批；force=true 忽略「今日已跑过」 */
    Map<String, Object> enqueueDailyCrawl(Long tenantId, boolean force);

    /** 打开应用展示用：最近一次 AE 任务摘要 */
    Map<String, Object> buildSyncStatus(Long tenantId);
}
