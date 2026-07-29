package com.crosshub.temu.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class TemuAgentIngestService {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final List<String> SALE_COLUMNS = List.of(
            "platform", "status", "report_time", "shop_name", "shop_id", "tenant_id", "user_id",
            "cost", "category_name", "img_url", "title", "skc", "spu", "ext_code", "son_sku",
            "son_price", "son_today_sales", "son_sales_seven_days", "son_sales_thirty_days",
            "join_site_time", "warehouse_available_stock", "nickname", "username", "enterprise"
    );

    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;

    public TemuAgentIngestService(JdbcTemplate jdbc, ObjectMapper objectMapper) {
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public Map<String, Object> ingest(Long tenantId, Map<String, Object> payload) {
        String reportTime = stringValue(payload.get("report_time"));
        List<Map<String, Object>> shops = readList(payload.get("shops"));
        List<Map<String, Object>> rows = readList(payload.get("rows"));

        for (Map<String, Object> shop : shops) {
            jdbc.update(
                    """
                    INSERT INTO temu_shop (shop_id, tenant_id, shop_name, is_upload)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(shop_id) DO UPDATE SET
                      shop_name = excluded.shop_name,
                      is_upload = excluded.is_upload,
                      tenant_id = excluded.tenant_id
                    """,
                    stringValue(shop.get("shop_id")),
                    tenantId,
                    stringValue(shop.get("shop_name")),
                    boolToInt(shop.get("is_upload"), 1)
            );
        }

        Set<String> shopIds = new LinkedHashSet<>();
        for (Map<String, Object> row : rows) {
            String shopId = stringValue(row.get("shop_id"));
            if (!shopId.isBlank()) {
                shopIds.add(shopId);
            }
        }
        for (String shopId : shopIds) {
            jdbc.update(
                    "DELETE FROM temu_sale WHERE tenant_id = ? AND report_time = ? AND shop_id = ?",
                    tenantId,
                    reportTime,
                    shopId
            );
        }

        String placeholders = String.join(", ", SALE_COLUMNS.stream().map(c -> "?").toList());
        String assignments = String.join(
                ", ",
                SALE_COLUMNS.stream()
                        .filter(col -> !Set.of("tenant_id", "report_time", "shop_id", "ext_code").contains(col))
                        .map(col -> col + " = excluded." + col)
                        .toList()
        );
        String sql = """
                INSERT INTO temu_sale (%s) VALUES (%s)
                ON CONFLICT(tenant_id, report_time, shop_id, ext_code)
                DO UPDATE SET %s
                """.formatted(String.join(", ", SALE_COLUMNS), placeholders, assignments);

        int count = 0;
        for (Map<String, Object> row : rows) {
            List<Object> values = new ArrayList<>();
            for (String column : SALE_COLUMNS) {
                Object value = row.get(column);
                if ("tenant_id".equals(column) && (value == null || String.valueOf(value).isBlank())) {
                    value = tenantId;
                }
                values.add(normalizeValue(column, value));
            }
            jdbc.update(sql, values.toArray());
            count++;
        }

        return Map.of(
                "tenant_id", tenantId,
                "report_time", reportTime,
                "shops", shops.size(),
                "rows", count
        );
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> readList(Object raw) {
        if (raw instanceof List<?> list) {
            List<Map<String, Object>> out = new ArrayList<>();
            for (Object item : list) {
                if (item instanceof Map<?, ?> map) {
                    Map<String, Object> row = new java.util.LinkedHashMap<>();
                    for (Map.Entry<?, ?> entry : map.entrySet()) {
                        row.put(String.valueOf(entry.getKey()), entry.getValue());
                    }
                    out.add(row);
                }
            }
            return out;
        }
        return List.of();
    }

    private Object normalizeValue(String column, Object value) {
        if (value == null) {
            return "";
        }
        if (value instanceof Number) {
            return value;
        }
        if (Set.of("cost", "son_price", "son_today_sales", "son_sales_seven_days",
                "son_sales_thirty_days", "join_site_time", "warehouse_available_stock", "user_id", "tenant_id"
        ).contains(column)) {
            String text = String.valueOf(value).trim();
            if (text.isEmpty()) {
                return 0;
            }
            try {
                if (column.contains("tenant") || column.equals("user_id")) {
                    return Long.parseLong(text.split("\\.")[0]);
                }
                return Integer.parseInt(text.split("\\.")[0]);
            } catch (NumberFormatException ex) {
                return 0;
            }
        }
        return String.valueOf(value);
    }

    private int boolToInt(Object value, int defaultValue) {
        if (value == null) {
            return defaultValue;
        }
        if (value instanceof Boolean bool) {
            return bool ? 1 : 0;
        }
        String text = String.valueOf(value).trim().toLowerCase();
        if (text.isEmpty()) {
            return defaultValue;
        }
        return ("1".equals(text) || "true".equals(text) || "yes".equals(text)) ? 1 : 0;
    }

    private String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    public String now() {
        return LocalDateTime.now().format(TS);
    }
}
