package com.crosshub.alibaba1688.repository;

import com.crosshub.alibaba1688.entity.Alibaba1688PurchaseOrder;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface Alibaba1688PurchaseOrderRepository extends JpaRepository<Alibaba1688PurchaseOrder, String> {
    List<Alibaba1688PurchaseOrder> findByTenantIdOrderBySyncedAtDesc(Long tenantId);

    List<Alibaba1688PurchaseOrder> findByTenantIdAndStoreIdOrderBySyncedAtDesc(Long tenantId, String storeId);

    Optional<Alibaba1688PurchaseOrder> findByTenantIdAndStoreIdAndOrderNo(Long tenantId, String storeId, String orderNo);
}
