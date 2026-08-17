package com.crosshub.alibaba1688.service;

import com.crosshub.alibaba1688.dto.Alibaba1688CrawlRequest;
import com.crosshub.alibaba1688.entity.Alibaba1688CrawlJob;

import java.util.List;

public interface Alibaba1688CrawlService {
    Alibaba1688CrawlJob triggerCrawl(Alibaba1688CrawlRequest request);

    Alibaba1688CrawlJob getJob(String jobId);

    List<Alibaba1688CrawlJob> listRecentJobs(int limit);
}
