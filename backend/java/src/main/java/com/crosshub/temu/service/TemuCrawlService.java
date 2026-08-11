package com.crosshub.temu.service;

import com.crosshub.temu.entity.TemuCrawlJob;

public interface TemuCrawlService {
    TemuCrawlJob triggerCrawl(String reportTime, boolean seed);

    TemuCrawlJob triggerCrawl(String reportTime, boolean seed, boolean force, boolean recordCooldown);

    /** User-scoped async sync enqueue (per-user limits enforced by caller; no tenant-wide single-active lock). */
    TemuCrawlJob enqueueUserSync(String reportTime, boolean seed, boolean force, boolean recordCooldown);

    TemuCrawlJob getJob(String jobId);
}
