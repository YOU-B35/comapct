package com.crosshub.taobao.repository;

import com.crosshub.taobao.entity.TaobaoCompassSnapshot;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface TaobaoCompassSnapshotRepository extends JpaRepository<TaobaoCompassSnapshot, String> {
    Optional<TaobaoCompassSnapshot> findByTenantIdAndStoreIdAndDateWindow(
            Long tenantId, String storeId, String dateWindow);

    List<TaobaoCompassSnapshot> findByTenantIdOrderByUpdatedAtDesc(Long tenantId);

    List<TaobaoCompassSnapshot> findByTenantIdAndStoreIdOrderByUpdatedAtDesc(Long tenantId, String storeId);
}
