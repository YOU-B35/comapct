package com.crosshub.temu.service;

import com.crosshub.temu.entity.TemuSale;

import java.util.List;
import java.util.Map;

public interface TemuSkuCostService {
    void upsertCosts(Long tenantId, List<Map<String, Object>> items);

    Map<String, Integer> costMapForTenant(Long tenantId);

    void overlaySaleCosts(Long tenantId, List<TemuSale> sales);
}
