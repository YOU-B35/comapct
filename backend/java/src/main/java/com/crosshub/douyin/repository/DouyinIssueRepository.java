package com.crosshub.douyin.repository;

import com.crosshub.douyin.entity.DouyinIssue;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface DouyinIssueRepository extends JpaRepository<DouyinIssue, String> {
    List<DouyinIssue> findByTenantIdOrderByReportedAtDesc(Long tenantId);

    List<DouyinIssue> findByTenantIdAndStoreIdOrderByReportedAtDesc(Long tenantId, String storeId);

    Optional<DouyinIssue> findByTenantIdAndStoreIdAndExternalId(Long tenantId, String storeId, String externalId);

    Optional<DouyinIssue> findByIdAndTenantId(String id, Long tenantId);
}
