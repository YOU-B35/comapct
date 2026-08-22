package com.crosshub.taobao.repository;

import com.crosshub.taobao.entity.TaobaoIssue;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/**
 * 淘宝/天猫工单预警数据访问层。对齐抖音 {@code DouyinIssueRepository}。
 */
public interface TaobaoIssueRepository extends JpaRepository<TaobaoIssue, String> {
    List<TaobaoIssue> findByTenantIdOrderByReportedAtDesc(Long tenantId);

    List<TaobaoIssue> findByTenantIdAndStoreIdOrderByReportedAtDesc(Long tenantId, String storeId);

    Optional<TaobaoIssue> findByTenantIdAndStoreIdAndExternalId(Long tenantId, String storeId, String externalId);

    Optional<TaobaoIssue> findByIdAndTenantId(String id, Long tenantId);
}
