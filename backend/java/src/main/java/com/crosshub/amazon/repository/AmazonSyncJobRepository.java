package com.crosshub.amazon.repository;

import com.crosshub.amazon.entity.AmazonSyncJob;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface AmazonSyncJobRepository extends JpaRepository<AmazonSyncJob, String> {
    List<AmazonSyncJob> findByTenantIdAndStatusInOrderByCreatedAtDesc(Long tenantId, Collection<String> statuses);
    Optional<AmazonSyncJob> findByIdAndTenantId(String id, Long tenantId);
    Optional<AmazonSyncJob> findFirstByAgentTaskId(String agentTaskId);
    Optional<AmazonSyncJob> findFirstByTenantIdAndPlatformAccountIdAndScopeAndStatusInOrderByCreatedAtDesc(
            Long tenantId, String platformAccountId, String scope, Collection<String> statuses
    );

    Optional<AmazonSyncJob> findFirstByTenantIdOrderByCreatedAtDesc(Long tenantId);
}
