package com.crosshub.alibaba1688.repository;

import com.crosshub.alibaba1688.entity.Alibaba1688Product;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface Alibaba1688ProductRepository extends JpaRepository<Alibaba1688Product, String> {
    List<Alibaba1688Product> findByTenantIdOrderBySyncedAtDesc(Long tenantId);

    List<Alibaba1688Product> findByTenantIdAndStoreIdOrderBySyncedAtDesc(Long tenantId, String storeId);

    Optional<Alibaba1688Product> findByTenantIdAndStoreIdAndOfferId(Long tenantId, String storeId, String offerId);
}
