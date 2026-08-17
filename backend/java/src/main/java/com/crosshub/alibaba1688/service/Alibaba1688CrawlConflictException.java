package com.crosshub.alibaba1688.service;

import com.crosshub.alibaba1688.entity.Alibaba1688CrawlJob;

public class Alibaba1688CrawlConflictException extends RuntimeException {
    private final Alibaba1688CrawlJob existingJob;

    public Alibaba1688CrawlConflictException(Alibaba1688CrawlJob existingJob) {
        super("CRAWL_IN_PROGRESS");
        this.existingJob = existingJob;
    }

    public Alibaba1688CrawlJob getExistingJob() {
        return existingJob;
    }
}
