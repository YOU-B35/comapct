package com.crosshub.temu.service.impl;

import com.crosshub.temu.entity.TemuSale;
import com.crosshub.temu.service.TemuSkuCostService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class TemuSkuCostServiceImpl implements TemuSkuCostService {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final JdbcTemplate jdbc;

    public TemuSkuCostServiceImpl(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Override
    public void upsertCosts(Long tenantId, List<Map<String, Object>> items) {
        if (tenantId == null || items == null || items.isEmpty()) {
            return;
        }
        String now = LocalDateTime.now().format(TS);
        for (Map<String, Object> item : items) {
            String extCode = stringValue(item.get("ext_code"));
            if (extCode.isBlank()) {
                extCode = stringValue(item.get("sku"));
            }
            if (extCode.isBlank()) {
                continue;
            }
            int cost = parseCostCents(item);
            if (cost < 0) {
                continue;
            }
            jdbc.update(
                    """
                    INSERT INTO temu_sku_cost (tenant_id, ext_code, cost, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(tenant_id, ext_code) DO UPDATE SET
                      cost = excluded.cost,
                      updated_at = excluded.updated_at
                    """,
                    tenantId,
                    extCode,
                    cost,
                    now
            );
        }
    }

    @Override
    public Map<String, Integer> costMapForTenant(Long tenantId) {
        Map<String, Integer> map = new HashMap<>();
        if (tenantId == null) {
            return map;
        }
        jdbc.query(
                "SELECT ext_code, cost FROM temu_sku_cost WHERE tenant_id = ?",
                rs -> {
                    map.put(rs.getString("ext_code"), rs.getInt("cost"));
                },
                tenantId
        );
        return map;
    }

    @Override
    public void overlaySaleCosts(Long tenantId, List<TemuSale> sales) {
        if (tenantId == null || sales == null || sales.isEmpty()) {
            return;
        }
        Map<String, Integer> costs = costMapForTenant(tenantId);
        if (costs.isEmpty()) {
            return;
        }
        for (TemuSale sale : sales) {
            String key = stringValue(sale.getExtCode());
            if (key.isBlank()) {
                continue;
            }
            Integer cost = costs.get(key);
            if (cost != null && cost > 0) {
                sale.setCost(cost);
            }
        }
    }

    private static int parseCostCents(Map<String, Object> item) {
        Object raw = item.get("cost");
        if (raw == null) {
            raw = item.get("cost_cents");
        }
        if (raw == null) {
            raw = item.get("cost_price");
        }
        if (raw == null) {
            return -1;
        }
        if (raw instanceof Number number) {
            double value = number.doubleValue();
            if (item.containsKey("cost_price") && !item.containsKey("cost_cents") && !item.containsKey("cost")) {
                return (int) Math.round(value * 100);
            }
            return (int) Math.round(value);
        }
        try {
            String text = String.valueOf(raw).trim();
            if (text.contains(".")) {
                return (int) Math.round(Double.parseDouble(text) * 100);
            }
            return Integer.parseInt(text);
        } catch (NumberFormatException ex) {
            return -1;
        }
    }

    private static String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }
}
