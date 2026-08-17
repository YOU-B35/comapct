package com.crosshub.alibaba1688.repository;

import com.crosshub.alibaba1688.entity.Alibaba1688SupplierAlert;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface Alibaba1688SupplierAlertRepository extends JpaRepository<Alibaba1688SupplierAlert, String> {
    List<Alibaba1688SupplierAlert> findByTenantIdOrderByCreatedAtDesc(Long tenantId);

    List<Alibaba1688SupplierAlert> findByTenantIdAndStoreIdOrderByCreatedAtDesc(Long tenantId, String storeId);

    List<Alibaba1688SupplierAlert> findByTenantIdAndIsOpenOrderByCreatedAtDesc(Long tenantId, Integer isOpen);

    Optional<Alibaba1688SupplierAlert> findByTenantIdAndStoreIdAndTypeAndRelatedOrderNo(
            Long tenantId, String storeId, String type, String relatedOrderNo);
}
