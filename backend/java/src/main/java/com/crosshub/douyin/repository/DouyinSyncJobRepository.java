package com.crosshub.douyin.repository;

import com.crosshub.douyin.entity.DouyinSyncJob;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface DouyinSyncJobRepository extends JpaRepository<DouyinSyncJob, String> {
    Optional<DouyinSyncJob> findByIdAndTenantId(String id, Long tenantId);

    List<DouyinSyncJob> findByTenantIdAndStatusInOrderByCreatedAtDesc(Long tenantId, List<String> statuses);

    Optional<DouyinSyncJob> findFirstByTenantIdAndAgentTaskId(Long tenantId, String agentTaskId);
}
