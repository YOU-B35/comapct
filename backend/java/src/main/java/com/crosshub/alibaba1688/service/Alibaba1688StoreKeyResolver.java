package com.crosshub.alibaba1688.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/** 解析租户的默认 1688 店铺键：优先会话快照 shops[0].id，其次唯一 1688 账号。 */
@Component
public class Alibaba1688StoreKeyResolver {
    private static final Logger log = LoggerFactory.getLogger(Alibaba1688StoreKeyResolver.class);

    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;

    public Alibaba1688StoreKeyResolver(JdbcTemplate jdbc, ObjectMapper objectMapper) {
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    public String resolveDefaultAccountId(Long tenantId) {
        if (tenantId == null) {
            return "";
        }
        try {
            List<Map<String, Object>> snapshots = jdbc.queryForList(
                    "SELECT payload_json FROM alibaba1688_session_snapshot WHERE tenant_id = ? LIMIT 1",
                    tenantId
            );
            if (!snapshots.isEmpty()) {
                String raw = String.valueOf(snapshots.get(0).get("payload_json"));
                Map<String, Object> payload = objectMapper.readValue(
                        raw == null || raw.isBlank() ? "{}" : raw,
                        new TypeReference<Map<String, Object>>() {}
                );
                Object shopsRaw = payload.get("shops");
                if (shopsRaw instanceof List<?> shops) {
                    for (Object item : shops) {
                        if (!(item instanceof Map<?, ?> shop)) {
                            continue;
                        }
                        // 1) 会话里的真实店铺 ID（探活/登录时写入）
                        Object shopId = shop.get("id");
                        if (shopId != null && !String.valueOf(shopId).isBlank()) {
                            Integer exists = jdbc.queryForObject(
                                    "SELECT COUNT(1) FROM platform_account WHERE id = ? AND tenant_id = ? AND platform = '1688'",
                                    Integer.class, String.valueOf(shopId), tenantId
                            );
                            if (exists != null && exists > 0) {
                                return String.valueOf(shopId);
                            }
                        }
                        // 2) 会员ID（external_shop_id）匹配
                        Object memberId = shop.get("external_shop_id") == null
                                ? shop.get("member_id") : shop.get("external_shop_id");
                        if (memberId != null && !String.valueOf(memberId).isBlank()) {
                            List<String> matched = jdbc.queryForList(
                                    "SELECT id FROM platform_account WHERE tenant_id = ? AND platform = '1688' AND external_shop_id = ? LIMIT 1",
                                    String.class, tenantId, String.valueOf(memberId)
                            );
                            if (!matched.isEmpty()) {
                                return matched.get(0);
                            }
                        }
                        // 3) 店铺名匹配（探活时从工作台页面提取的真实名称）
                        Object storeName = shop.get("store_name") == null ? shop.get("storeName") : shop.get("store_name");
                        if (storeName != null && !String.valueOf(storeName).isBlank()) {
                            List<String> matched = jdbc.queryForList(
                                    "SELECT id FROM platform_account WHERE tenant_id = ? AND platform = '1688' AND store_name = ? LIMIT 1",
                                    String.class, tenantId, String.valueOf(storeName)
                            );
                            if (!matched.isEmpty()) {
                                return matched.get(0);
                            }
                        }
                    }
                }
            }
        } catch (Exception ex) {
            log.warn("[1688StoreKey] session snapshot parse failed for tenant {}: {}", tenantId, ex.toString());
        }
        List<String> candidates = jdbc.queryForList(
                """
                SELECT pa.id
                FROM platform_account pa
                LEFT JOIN alibaba1688_product p ON p.store_id = pa.id AND p.tenant_id = pa.tenant_id
                LEFT JOIN alibaba1688_order o ON o.store_id = pa.id AND o.tenant_id = pa.tenant_id
                WHERE pa.tenant_id = ? AND pa.platform = '1688'
                GROUP BY pa.id
                ORDER BY COUNT(DISTINCT p.id) DESC, COUNT(DISTINCT o.id) DESC, pa.bound_at ASC
                LIMIT 1
                """,
                String.class, tenantId
        );
        return candidates.isEmpty() ? "" : candidates.get(0);
    }
}
