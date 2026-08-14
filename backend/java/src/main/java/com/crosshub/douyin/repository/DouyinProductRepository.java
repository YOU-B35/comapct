package com.crosshub.douyin.repository;

import com.crosshub.douyin.entity.DouyinProduct;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface DouyinProductRepository extends JpaRepository<DouyinProduct, String> {
    List<DouyinProduct> findByTenantIdOrderByUpdatedAtDesc(Long tenantId);

    List<DouyinProduct> findByTenantIdAndStoreIdOrderByUpdatedAtDesc(Long tenantId, String storeId);

    Optional<DouyinProduct> findByProductKey(String productKey);

    void deleteByTenantIdAndStoreId(Long tenantId, String storeId);
}
