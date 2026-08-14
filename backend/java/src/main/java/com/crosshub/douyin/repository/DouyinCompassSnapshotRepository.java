package com.crosshub.douyin.repository;

import com.crosshub.douyin.entity.DouyinCompassSnapshot;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface DouyinCompassSnapshotRepository extends JpaRepository<DouyinCompassSnapshot, String> {
    Optional<DouyinCompassSnapshot> findFirstByTenantIdAndStoreIdAndDateTypeOrderBySyncedAtDesc(
            Long tenantId,
            String storeId,
            Integer dateType
    );

    Optional<DouyinCompassSnapshot> findFirstByTenantIdAndDateTypeOrderBySyncedAtDesc(
            Long tenantId,
            Integer dateType
    );

    List<DouyinCompassSnapshot> findByTenantIdAndStoreIdAndReportDayAndDateType(
            Long tenantId,
            String storeId,
            String reportDay,
            Integer dateType
    );

    void deleteByTenantIdAndStoreIdAndReportDayAndDateType(
            Long tenantId,
            String storeId,
            String reportDay,
            Integer dateType
    );
}
