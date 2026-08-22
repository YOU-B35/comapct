package com.crosshub.pdd.repository;

import com.crosshub.pdd.entity.PddProduct;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PddProductRepository extends JpaRepository<PddProduct, String> {
    List<PddProduct> findByTenantIdOrderByUpdatedAtDesc(Long tenantId);

    List<PddProduct> findByTenantIdAndStoreIdOrderByUpdatedAtDesc(Long tenantId, String storeId);

    Optional<PddProduct> findByTenantIdAndProductKey(Long tenantId, String productKey);

    void deleteByTenantIdAndStoreId(Long tenantId, String storeId);
}
