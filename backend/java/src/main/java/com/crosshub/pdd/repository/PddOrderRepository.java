package com.crosshub.pdd.repository;

import com.crosshub.pdd.entity.PddOrder;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;

public interface PddOrderRepository extends JpaRepository<PddOrder, String> {
    List<PddOrder> findByTenantIdAndReportDayOrderByOrderedAtDesc(Long tenantId, String reportDay);

    List<PddOrder> findByTenantIdAndReportDayAndStoreIdOrderByOrderedAtDesc(
            Long tenantId,
            String reportDay,
            String storeId
    );

    /** 按时间段窗口查询（对齐用户「订单按时间段分」需求） */
    List<PddOrder> findByTenantIdAndDateWindowOrderByOrderedAtDesc(Long tenantId, String dateWindow);

    List<PddOrder> findByTenantIdAndStoreIdAndDateWindowOrderByOrderedAtDesc(
            Long tenantId,
            String storeId,
            String dateWindow
    );

    List<PddOrder> findByTenantIdAndReportDayInOrderByOrderedAtDesc(
            Long tenantId,
            Collection<String> reportDays
    );

    List<PddOrder> findByTenantIdAndStoreIdAndReportDayInOrderByOrderedAtDesc(
            Long tenantId,
            String storeId,
            Collection<String> reportDays
    );

    void deleteByTenantIdAndStoreIdAndReportDayAndDateWindow(
            Long tenantId, String storeId, String reportDay, String dateWindow);
}
