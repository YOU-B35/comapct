package com.crosshub.taobao.repository;

import com.crosshub.taobao.entity.TaobaoOrder;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;

public interface TaobaoOrderRepository extends JpaRepository<TaobaoOrder, String> {
    List<TaobaoOrder> findByTenantIdAndReportDayOrderByOrderedAtDesc(Long tenantId, String reportDay);

    List<TaobaoOrder> findByTenantIdAndReportDayAndStoreIdOrderByOrderedAtDesc(
            Long tenantId,
            String reportDay,
            String storeId
    );

    /** 按时间段窗口查询（对齐用户「订单按时间段分」需求） */
    List<TaobaoOrder> findByTenantIdAndDateWindowOrderByOrderedAtDesc(Long tenantId, String dateWindow);

    List<TaobaoOrder> findByTenantIdAndStoreIdAndDateWindowOrderByOrderedAtDesc(
            Long tenantId,
            String storeId,
            String dateWindow
    );

    List<TaobaoOrder> findByTenantIdAndReportDayInOrderByOrderedAtDesc(
            Long tenantId,
            Collection<String> reportDays
    );

    List<TaobaoOrder> findByTenantIdAndStoreIdAndReportDayInOrderByOrderedAtDesc(
            Long tenantId,
            String storeId,
            Collection<String> reportDays
    );

    void deleteByTenantIdAndStoreIdAndReportDayAndDateWindow(
            Long tenantId, String storeId, String reportDay, String dateWindow);
}
