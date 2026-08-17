package com.crosshub.alibaba1688.repository;

import com.crosshub.alibaba1688.entity.Alibaba1688SupplierStat;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface Alibaba1688SupplierStatRepository extends JpaRepository<Alibaba1688SupplierStat, String> {
    List<Alibaba1688SupplierStat> findByTenantIdAndWindowDaysOrderByOrderCountDesc(Long tenantId, Integer windowDays);

    List<Alibaba1688SupplierStat> findByTenantIdAndStoreIdAndWindowDaysOrderByOrderCountDesc(
            Long tenantId, String storeId, Integer windowDays);

    Optional<Alibaba1688SupplierStat> findByTenantIdAndStoreIdAndSupplierKeyAndWindowDays(
            Long tenantId, String storeId, String supplierKey, Integer windowDays);
}
