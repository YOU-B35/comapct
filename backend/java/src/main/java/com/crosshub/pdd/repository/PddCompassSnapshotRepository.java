package com.crosshub.pdd.repository;

import com.crosshub.pdd.entity.PddCompassSnapshot;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PddCompassSnapshotRepository extends JpaRepository<PddCompassSnapshot, String> {
    Optional<PddCompassSnapshot> findByTenantIdAndStoreIdAndDateWindow(
            Long tenantId, String storeId, String dateWindow);

    List<PddCompassSnapshot> findByTenantIdOrderByUpdatedAtDesc(Long tenantId);

    List<PddCompassSnapshot> findByTenantIdAndStoreIdOrderByUpdatedAtDesc(Long tenantId, String storeId);
}
