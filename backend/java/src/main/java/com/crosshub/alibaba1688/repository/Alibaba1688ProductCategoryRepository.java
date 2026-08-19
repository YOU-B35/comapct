package com.crosshub.alibaba1688.repository;

import com.crosshub.alibaba1688.entity.Alibaba1688ProductCategory;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface Alibaba1688ProductCategoryRepository extends JpaRepository<Alibaba1688ProductCategory, String> {
    List<Alibaba1688ProductCategory> findByTenantIdAndStoreIdAndCategoryCode(
            Long tenantId,
            String storeId,
            String categoryCode
    );

    List<Alibaba1688ProductCategory> findByTenantIdAndCategoryCode(Long tenantId, String categoryCode);

    List<Alibaba1688ProductCategory> findByTenantId(Long tenantId);
}
