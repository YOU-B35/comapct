package com.crosshub.pdd.repository;

import com.crosshub.pdd.entity.PddSyncJob;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PddSyncJobRepository extends JpaRepository<PddSyncJob, String> {
    Optional<PddSyncJob> findByIdAndTenantId(String id, Long tenantId);

    List<PddSyncJob> findByTenantIdAndStatusInOrderByCreatedAtDesc(Long tenantId, List<String> statuses);

    Optional<PddSyncJob> findFirstByTenantIdAndAgentTaskId(Long tenantId, String agentTaskId);

    List<PddSyncJob> findByTenantIdOrderByCreatedAtDesc(Long tenantId);
}
