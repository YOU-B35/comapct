package com.crosshub.aliexpress.repository;

import com.crosshub.aliexpress.entity.AliExpressCrawlJob;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface AliExpressCrawlJobRepository extends JpaRepository<AliExpressCrawlJob, String> {
    Optional<AliExpressCrawlJob> findByIdAndTenantId(String id, Long tenantId);

    Optional<AliExpressCrawlJob> findFirstByTenantIdAndStatusInOrderByCreatedAtDesc(Long tenantId, Collection<String> statuses);

    Optional<AliExpressCrawlJob> findFirstByTenantIdOrderByCreatedAtDesc(Long tenantId);

    List<AliExpressCrawlJob> findTop60ByTenantIdOrderByCreatedAtDesc(Long tenantId);
}

