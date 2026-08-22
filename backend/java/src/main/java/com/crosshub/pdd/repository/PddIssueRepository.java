package com.crosshub.pdd.repository;

import com.crosshub.pdd.entity.PddIssue;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/**
 * 拼多多工单预警数据访问层。对齐抖音 {@code DouyinIssueRepository}。
 */
public interface PddIssueRepository extends JpaRepository<PddIssue, String> {
    List<PddIssue> findByTenantIdOrderByReportedAtDesc(Long tenantId);

    List<PddIssue> findByTenantIdAndStoreIdOrderByReportedAtDesc(Long tenantId, String storeId);

    Optional<PddIssue> findByTenantIdAndStoreIdAndExternalId(Long tenantId, String storeId, String externalId);

    Optional<PddIssue> findByIdAndTenantId(String id, Long tenantId);
}
