package com.crosshub.taobao.repository;

import com.crosshub.taobao.entity.TaobaoSyncJob;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface TaobaoSyncJobRepository extends JpaRepository<TaobaoSyncJob, String> {
    Optional<TaobaoSyncJob> findByIdAndTenantId(String id, Long tenantId);

    List<TaobaoSyncJob> findByTenantIdAndStatusInOrderByCreatedAtDesc(Long tenantId, List<String> statuses);

    Optional<TaobaoSyncJob> findFirstByTenantIdAndAgentTaskId(Long tenantId, String agentTaskId);

    List<TaobaoSyncJob> findByTenantIdOrderByCreatedAtDesc(Long tenantId);
}
