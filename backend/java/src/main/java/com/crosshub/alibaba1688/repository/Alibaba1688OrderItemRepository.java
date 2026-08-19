package com.crosshub.alibaba1688.repository;

import com.crosshub.alibaba1688.entity.Alibaba1688OrderItem;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface Alibaba1688OrderItemRepository extends JpaRepository<Alibaba1688OrderItem, String> {
    List<Alibaba1688OrderItem> findByTenantIdAndStoreIdAndOrderNo(
            Long tenantId,
            String storeId,
            String orderNo
    );

    void deleteByTenantIdAndStoreIdAndOrderNo(Long tenantId, String storeId, String orderNo);
}
