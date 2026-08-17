package com.crosshub.alibaba1688.repository;

import com.crosshub.alibaba1688.entity.Alibaba1688CrawlJob;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface Alibaba1688CrawlJobRepository extends JpaRepository<Alibaba1688CrawlJob, String> {
    Optional<Alibaba1688CrawlJob> findByIdAndTenantId(String id, Long tenantId);

    Optional<Alibaba1688CrawlJob> findFirstByTenantIdAndJobTypeAndStatusInOrderByCreatedAtDesc(
            Long tenantId, String jobType, Collection<String> statuses);

    List<Alibaba1688CrawlJob> findTop60ByTenantIdOrderByCreatedAtDesc(Long tenantId);
}
