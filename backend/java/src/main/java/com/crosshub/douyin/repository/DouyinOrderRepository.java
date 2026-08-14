package com.crosshub.douyin.repository;

import com.crosshub.douyin.entity.DouyinOrder;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;

public interface DouyinOrderRepository extends JpaRepository<DouyinOrder, String> {
    List<DouyinOrder> findByTenantIdAndReportDayOrderByOrderedAtDesc(Long tenantId, String reportDay);

    List<DouyinOrder> findByTenantIdAndReportDayAndStoreIdOrderByOrderedAtDesc(
            Long tenantId,
            String reportDay,
            String storeId
    );

    List<DouyinOrder> findByTenantIdAndReportDayInOrderByOrderedAtDesc(
            Long tenantId,
            Collection<String> reportDays
    );

    List<DouyinOrder> findByTenantIdAndStoreIdAndReportDayInOrderByOrderedAtDesc(
            Long tenantId,
            String storeId,
            Collection<String> reportDays
    );

    void deleteByTenantIdAndStoreIdAndReportDay(Long tenantId, String storeId, String reportDay);
}
