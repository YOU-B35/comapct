package com.crosshub.alibaba1688.repository;

import com.crosshub.alibaba1688.entity.Alibaba1688Order;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface Alibaba1688OrderRepository extends JpaRepository<Alibaba1688Order, String> {
    Optional<Alibaba1688Order> findByTenantIdAndStoreIdAndOrderNo(
            Long tenantId,
            String storeId,
            String orderNo
    );

    List<Alibaba1688Order> findByTenantIdAndStoreIdOrderByCreatedAtDesc(Long tenantId, String storeId);
}
