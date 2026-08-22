package com.crosshub.taobao.repository;

import com.crosshub.taobao.entity.TaobaoProduct;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface TaobaoProductRepository extends JpaRepository<TaobaoProduct, String> {
    List<TaobaoProduct> findByTenantIdOrderByUpdatedAtDesc(Long tenantId);

    List<TaobaoProduct> findByTenantIdAndStoreIdOrderByUpdatedAtDesc(Long tenantId, String storeId);

    Optional<TaobaoProduct> findByTenantIdAndProductKey(Long tenantId, String productKey);

    void deleteByTenantIdAndStoreId(Long tenantId, String storeId);
}
