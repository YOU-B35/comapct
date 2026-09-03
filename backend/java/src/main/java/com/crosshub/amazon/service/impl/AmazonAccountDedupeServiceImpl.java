package com.crosshub.amazon.service.impl;

import com.crosshub.amazon.service.AmazonAccountDedupeService;
import com.crosshub.platform.entity.PlatformAccount;
import com.crosshub.platform.repository.PlatformAccountRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class AmazonAccountDedupeServiceImpl implements AmazonAccountDedupeService {
    private static final Logger log = LoggerFactory.getLogger(AmazonAccountDedupeServiceImpl.class);
    private static final List<String> AMAZON_REF_TABLES = List.of(
            "amazon_product_snapshot",
            "amazon_account_metric",
            "amazon_operational_item",
            "amazon_sync_job",
            "amazon_sync_version",
            "amazon_product_version",
            "amazon_metric_version",
            "amazon_item_version"
    );

    private final PlatformAccountRepository platformAccountRepository;
    private final JdbcTemplate jdbc;

    public AmazonAccountDedupeServiceImpl(
            PlatformAccountRepository platformAccountRepository,
            JdbcTemplate jdbc
    ) {
        this.platformAccountRepository = platformAccountRepository;
        this.jdbc = jdbc;
    }

    @Override
    public int dedupeAllTenants() {
        List<Long> tenantIds = jdbc.queryForList(
                "SELECT DISTINCT tenant_id FROM platform_account WHERE lower(platform) = 'amazon'",
                Long.class
        );
        int merged = 0;
        for (Long tenantId : tenantIds) {
            merged += dedupeTenant(tenantId);
        }
        return merged;
    }

    @Override
    @Transactional
    public int dedupeTenant(Long tenantId) {
        if (tenantId == null) {
            return 0;
        }
        List<PlatformAccount> accounts = platformAccountRepository
                .findByTenantIdAndPlatformOrderByBoundAtDesc(tenantId, "amazon");
        Map<String, List<PlatformAccount>> groups = new LinkedHashMap<>();
        for (PlatformAccount account : accounts) {
            String external = trim(account.getExternalShopId());
            String cliStoreId = trim(account.getZiniaoCliStoreId());
            String identity = !external.isBlank() ? "webdriver:" + external
                    : (!cliStoreId.isBlank() ? "cli:" + cliStoreId : "");
            if (identity.isBlank()) {
                continue;
            }
            groups.computeIfAbsent(identity, key -> new ArrayList<>()).add(account);
        }

        int removed = 0;
        for (Map.Entry<String, List<PlatformAccount>> entry : groups.entrySet()) {
            List<PlatformAccount> group = entry.getValue();
            if (group.size() <= 1) {
                continue;
            }
            PlatformAccount keep = pickCanonical(group);
            for (PlatformAccount duplicate : group) {
                if (duplicate.getId().equals(keep.getId())) {
                    continue;
                }
                migrateReferences(tenantId, duplicate.getId(), keep.getId());
                platformAccountRepository.delete(duplicate);
                removed++;
                log.info(
                        "Merged duplicate Amazon account tenant={} external={} removed={} kept={}",
                        tenantId,
                        entry.getKey(),
                        duplicate.getId(),
                        keep.getId()
                );
            }
        }
        return removed;
    }

    private PlatformAccount pickCanonical(List<PlatformAccount> group) {
        List<PlatformAccount> sorted = new ArrayList<>(group);
        sorted.sort(Comparator
                .comparingInt(this::accountScore).reversed()
                .thenComparing(account -> trim(account.getBoundAt()), Comparator.reverseOrder())
                .thenComparing(PlatformAccount::getId));
        return sorted.get(0);
    }

    private int accountScore(PlatformAccount account) {
        int score = 0;
        if ("ziniao".equalsIgnoreCase(trim(account.getIntegrationMode()))
                || "ziniao_cli".equalsIgnoreCase(trim(account.getIntegrationMode()))) {
            score += 4;
        }
        if (!trim(account.getZiniaoCliStoreId()).isBlank()) {
            score += 2;
        }
        if (!trim(account.getZiniaoBrowserOauth()).isBlank()) {
            score += 2;
        }
        if (!trim(account.getExternalShopId()).isBlank()) {
            score += 1;
        }
        return score;
    }

    private void migrateReferences(Long tenantId, String fromId, String toId) {
        if (fromId == null || toId == null || fromId.equals(toId)) {
            return;
        }
        for (String table : AMAZON_REF_TABLES) {
            jdbc.update(
                    "UPDATE " + table + " SET platform_account_id = ? WHERE tenant_id = ? AND platform_account_id = ?",
                    toId,
                    tenantId,
                    fromId
            );
        }
    }

    private String trim(String value) {
        return value == null ? "" : value.trim();
    }
}
