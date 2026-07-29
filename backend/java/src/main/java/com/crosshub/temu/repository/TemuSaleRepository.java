package com.crosshub.temu.repository;

import com.crosshub.temu.entity.TemuSale;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface TemuSaleRepository extends JpaRepository<TemuSale, Long> {
    @Query("SELECT MAX(s.reportTime) FROM TemuSale s WHERE s.tenantId = :tenantId")
    String findLatestReportTimeByTenantId(@Param("tenantId") Long tenantId);

    List<TemuSale> findByTenantIdAndReportTime(Long tenantId, String reportTime);

    List<TemuSale> findByTenantIdAndReportTimeAndShopId(Long tenantId, String reportTime, String shopId);

    List<TemuSale> findByTenantIdAndReportTimeAndShopIdIn(Long tenantId, String reportTime, List<String> shopIds);

    /**
     * 按同步日汇总今日销量与近 7 日销量（排除 Demo SKU）。
     * 返回列：reportTime, sum(today), sum(sevenDays)
     */
    @Query("""
            SELECT s.reportTime,
                   COALESCE(SUM(s.sonTodaySales), 0),
                   COALESCE(SUM(s.sonSalesSevenDays), 0)
            FROM TemuSale s
            WHERE s.tenantId = :tenantId
              AND s.shopId IN :shopIds
              AND s.reportTime >= :fromDay
              AND s.reportTime <= :toDay
              AND (s.extCode IS NULL OR s.extCode = '' OR UPPER(s.extCode) NOT LIKE 'YT-T%')
            GROUP BY s.reportTime
            ORDER BY s.reportTime
            """)
    List<Object[]> sumSalesByReportTime(
            @Param("tenantId") Long tenantId,
            @Param("shopIds") List<String> shopIds,
            @Param("fromDay") String fromDay,
            @Param("toDay") String toDay
    );
}
