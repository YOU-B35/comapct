package com.crosshub.temu.repository;

import com.crosshub.temu.entity.TemuCrawlJob;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.Optional;

public interface TemuCrawlJobRepository extends JpaRepository<TemuCrawlJob, String> {
    Optional<TemuCrawlJob> findFirstByTenantIdAndStatusInOrderByCreatedAtDesc(
            Long tenantId,
            Collection<String> statuses
    );

    Optional<TemuCrawlJob> findByIdAndTenantId(String id, Long tenantId);

    Optional<TemuCrawlJob> findFirstByAgentTaskId(String agentTaskId);

    Optional<TemuCrawlJob> findFirstByTenantIdOrderByCreatedAtDesc(Long tenantId);
}
