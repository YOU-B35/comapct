package com.crosshub.pdd.repository;

import com.crosshub.pdd.entity.PddProduct;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface PddProductRepository extends JpaRepository<PddProduct, String> {
    List<PddProduct> findByTenantIdOrderByUpdatedAtDesc(Long tenantId);

    List<PddProduct> findByTenantIdAndStoreIdOrderByUpdatedAtDesc(Long tenantId, String storeId);

    Optional<PddProduct> findByTenantIdAndProductKey(Long tenantId, String productKey);

    /**
     * 立即执行的批量删除（先删后写全量替换）。
     * 不能使用派生 deleteBy…：它会先 SELECT 再逐个 remove()，删除动作被 Hibernate
     * 排到 INSERT 之后执行，导致同 product_key 重插时撞 uk_pdd_product_key 唯一索引。
     */
    @Modifying
    @Query("delete from PddProduct p where p.tenantId = :tenantId and p.storeId = :storeId")
    void deleteByTenantIdAndStoreId(@Param("tenantId") Long tenantId, @Param("storeId") String storeId);
}
