package com.crosshub.douyin.repository;

import com.crosshub.douyin.entity.DouyinOpportunityProduct;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface DouyinOpportunityProductRepository extends JpaRepository<DouyinOpportunityProduct, String> {
    List<DouyinOpportunityProduct> findByTenantIdAndStoreIdAndCategoryKeyOrderByRankNoAsc(
            Long tenantId, String storeId, String categoryKey
    );

    List<DouyinOpportunityProduct> findByTenantIdAndCategoryKeyOrderByRankNoAsc(
            Long tenantId, String categoryKey
    );

    List<DouyinOpportunityProduct> findByTenantIdAndStoreIdOrderBySyncedAtDescRankNoAsc(
            Long tenantId, String storeId
    );

    List<DouyinOpportunityProduct> findByTenantIdOrderBySyncedAtDescRankNoAsc(Long tenantId);

    Optional<DouyinOpportunityProduct> findByIdAndTenantId(String id, Long tenantId);

    void deleteByTenantIdAndStoreIdAndCategoryKey(Long tenantId, String storeId, String categoryKey);
}
