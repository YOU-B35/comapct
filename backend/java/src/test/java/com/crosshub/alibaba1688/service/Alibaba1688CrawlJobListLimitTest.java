package com.crosshub.alibaba1688.service;

import com.crosshub.alibaba1688.dto.Alibaba1688CrawlRequest;
import com.crosshub.alibaba1688.entity.Alibaba1688CrawlJob;
import com.crosshub.alibaba1688.service.impl.Alibaba1688CrawlServiceImpl;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

class Alibaba1688CrawlJobListLimitTest {
    /** Mutex treats only these as active — matches service ACTIVE_STATUSES. */
    private static final Set<String> ACTIVE_STATUSES = Set.of("pending", "running");

    @Test
    void clampLimit() {
        assertEquals(20, Alibaba1688CrawlServiceImpl.clampJobListLimit(null));
        assertEquals(20, Alibaba1688CrawlServiceImpl.clampJobListLimit(0));
        assertEquals(1, Alibaba1688CrawlServiceImpl.clampJobListLimit(1));
        assertEquals(60, Alibaba1688CrawlServiceImpl.clampJobListLimit(999));
    }

    @Test
    void mapSpawnScope_loginProbeAndSync() {
        assertEquals("login_probe", Alibaba1688CrawlServiceImpl.mapSpawnScope("login_probe"));
        assertEquals("sync", Alibaba1688CrawlServiceImpl.mapSpawnScope("sync"));
        assertEquals("sync", Alibaba1688CrawlServiceImpl.mapSpawnScope("crawl"));
        assertEquals("sync", Alibaba1688CrawlServiceImpl.mapSpawnScope(null));
    }

    @Test
    void resolvedJobType_mapsCrawlToSync() {
        Alibaba1688CrawlRequest body = new Alibaba1688CrawlRequest();
        body.setJobType("crawl");
        assertEquals("sync", body.resolvedJobType());
        body.setJobType("sync");
        assertEquals("sync", body.resolvedJobType());
        body.setJobType("login_probe");
        assertEquals("login_probe", body.resolvedJobType());
        body.setJobType(null);
        assertEquals("sync", body.resolvedJobType());
    }

    @Test
    void conflictException_exposesExistingJobAndCode() {
        Alibaba1688CrawlJob existing = new Alibaba1688CrawlJob();
        existing.setId("job-active-1");
        existing.setTenantId(7L);
        existing.setJobType("sync");
        existing.setStatus("running");
        assertTrue(ACTIVE_STATUSES.contains(existing.getStatus()));

        Alibaba1688CrawlConflictException ex = new Alibaba1688CrawlConflictException(existing);
        assertSame(existing, ex.getExistingJob());
        assertEquals("CRAWL_IN_PROGRESS", ex.getMessage());
        // Mutex key is (tenant_id, job_type) — documented via fields on the conflict payload job.
        assertEquals(7L, ex.getExistingJob().getTenantId());
        assertEquals("sync", ex.getExistingJob().getJobType());
    }
}
