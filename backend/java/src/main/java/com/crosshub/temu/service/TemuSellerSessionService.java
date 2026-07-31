package com.crosshub.temu.service;

import com.crosshub.platform.entity.PlatformAccount;
import com.crosshub.platform.repository.PlatformAccountRepository;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class TemuSellerSessionService {
    private final PlatformAccountRepository platformAccountRepository;

    public TemuSellerSessionService(PlatformAccountRepository platformAccountRepository) {
        this.platformAccountRepository = platformAccountRepository;
    }

    public List<Map<String, Object>> listSellerSessions(Long tenantId) {
        if (tenantId == null) {
            return List.of(defaultSession());
        }
        List<PlatformAccount> accounts = platformAccountRepository
                .findByTenantIdAndPlatformOrderByBoundAtDesc(tenantId, "temu");
        if (accounts.isEmpty()) {
            return List.of(defaultSession());
        }

        Map<String, Map<String, Object>> grouped = new LinkedHashMap<>();
        for (PlatformAccount account : accounts) {
            String sessionKey = buildSessionKey(account.getAccount(), account.getId());
            Map<String, Object> group = grouped.computeIfAbsent(sessionKey, key -> {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("session_key", sessionKey);
                row.put("account", trim(account.getAccount()));
                row.put("platform_account_id", account.getId());
                row.put("store_names", new ArrayList<String>());
                return row;
            });
            @SuppressWarnings("unchecked")
            List<String> storeNames = (List<String>) group.get("store_names");
            String storeName = trim(account.getStoreName());
            if (!storeName.isBlank()) {
                storeNames.add(storeName);
            }
        }
        return new ArrayList<>(grouped.values());
    }

    public String resolveSessionKey(Long tenantId, String platformAccountId) {
        if (platformAccountId == null || platformAccountId.isBlank()) {
            return "default";
        }
        return platformAccountRepository.findByIdAndTenantId(platformAccountId.trim(), tenantId)
                .map(account -> buildSessionKey(account.getAccount(), account.getId()))
                .orElse("default");
    }

    public static String buildSessionKey(String account, String platformAccountId) {
        String normalized = account == null ? "" : account.trim().toLowerCase();
        if (!normalized.isBlank()) {
            String slug = normalized.replaceAll("[^a-z0-9]+", "_").replaceAll("^_|_$", "");
            if (slug.length() > 48) {
                slug = slug.substring(0, 48).replaceAll("_+$", "");
            }
            if (!slug.isBlank()) {
                return slug;
            }
        }
        String id = platformAccountId == null ? "" : platformAccountId.trim();
        if (!id.isBlank()) {
            return "pa_" + id;
        }
        return "default";
    }

    private Map<String, Object> defaultSession() {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("session_key", "default");
        row.put("account", "");
        row.put("platform_account_id", "");
        row.put("store_names", List.of());
        return row;
    }

    private String trim(String value) {
        return value == null ? "" : value.trim();
    }
}
