package com.crosshub.pdd.repository;

import com.crosshub.pdd.entity.PddOrder;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

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

    @Modifying
    @Query("delete from PddOrder p where p.tenantId = :tenantId and p.storeId = :storeId "
            + "and p.reportDay = :reportDay and p.dateWindow = :dateWindow")
    void deleteByTenantIdAndStoreIdAndReportDayAndDateWindow(
            @Param("tenantId") Long tenantId,
            @Param("storeId") String storeId,
            @Param("reportDay") String reportDay,
            @Param("dateWindow") String dateWindow);

    /** 按自然日整体替换（不区分 date_window，避免历史窗口标签残留导致重复）。 */
    @Modifying
    @Query("delete from PddOrder p where p.tenantId = :tenantId and p.storeId = :storeId "
            + "and p.reportDay = :reportDay")
    void deleteByTenantIdAndStoreIdAndReportDay(
            @Param("tenantId") Long tenantId,
            @Param("storeId") String storeId,
            @Param("reportDay") String reportDay);
}
