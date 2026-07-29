package com.crosshub.temu.service.impl;

import com.crosshub.security.AuthContext;
import com.crosshub.temu.entity.TemuSale;
import com.crosshub.temu.entity.TemuShop;
import com.crosshub.temu.mapper.TemuMapper;
import com.crosshub.temu.repository.TemuSaleRepository;
import com.crosshub.temu.service.TemuOperationalService;
import com.crosshub.temu.service.TemuSkuCostService;
import com.crosshub.temu.service.TemuWarningService;
import com.crosshub.tenant.service.DataScopeService;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class TemuOperationalServiceImpl implements TemuOperationalService {
    private final DataScopeService dataScopeService;
    private final TemuWarningService warningService;
    private final AuthContext authContext;
    private final TemuMapper temuMapper;
    private final TemuSaleRepository saleRepository;
    private final TemuSkuCostService skuCostService;

    public TemuOperationalServiceImpl(
            DataScopeService dataScopeService,
            TemuWarningService warningService,
            AuthContext authContext,
            TemuMapper temuMapper,
            TemuSaleRepository saleRepository,
            TemuSkuCostService skuCostService
    ) {
        this.dataScopeService = dataScopeService;
        this.warningService = warningService;
        this.authContext = authContext;
        this.temuMapper = temuMapper;
        this.saleRepository = saleRepository;
        this.skuCostService = skuCostService;
    }

    @Override
    public String latestReportTime() {
        String latest = dataScopeService.latestReportTime();
        return latest != null ? latest : LocalDate.now().toString();
    }

    @Override
    public List<TemuShop> shops() {
        return dataScopeService.scopedShops();
    }

    @Override
    public List<TemuSale> scopedSales(String reportTime, String shopId) {
        return dataScopeService.scopedSales(reportTime, shopId);
    }

    @Override
    public Map<String, Object> operationalBundle(String shopId, String reportTime) {
        String day = reportTime == null || reportTime.isBlank() ? latestReportTime() : reportTime;
        List<TemuSale> sales = scopedSales(day, shopId);
        Long tenantId = authContext.tenantId();
        if (tenantId != null) {
            skuCostService.overlaySaleCosts(tenantId, sales);
        }

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("code", 0);
        body.put("report_time", day);
        body.put("tenant_id", authContext.tenantId());
        body.put("products", sales.stream().map(temuMapper::toSaleDto).toList());
        body.put("lose_products", warningService.loseProducts(sales).stream().map(temuMapper::toSaleDto).toList());
        body.put("low_warnings", warningService.allLowSaleEstimates(sales).stream().map(temuMapper::toLowSaleDto).toList());
        body.put("inventory_warnings", warningService.inventoryWarnings(sales).stream().map(temuMapper::toInventoryDto).toList());
        body.put("overload_products", warningService.overloadProducts(sales, 300).stream().map(temuMapper::toSaleDto).toList());
        return body;
    }

    @Override
    public Map<String, Object> salesTrend(String shopId, int days) {
        int window = Math.max(1, Math.min(days <= 0 ? 7 : days, 30));
        LocalDate today = LocalDate.now();
        LocalDate chartStart = today.minusDays(window - 1L);
        // 多取 6 天，便于用「近 7 日销量」回填缺同步日
        LocalDate lookbackStart = chartStart.minusDays(6);

        List<String> shopIds = resolveTrendShopIds(shopId);
        Map<LocalDate, int[]> aggregates = loadDailyAggregates(shopIds, lookbackStart, today);

        Map<LocalDate, Integer> resolved = new HashMap<>();
        Set<LocalDate> synced = new HashSet<>();
        for (Map.Entry<LocalDate, int[]> entry : aggregates.entrySet()) {
            resolved.put(entry.getKey(), entry.getValue()[0]);
            synced.add(entry.getKey());
        }

        // 从最近同步日往前：用 seven - today 的残差，均分到窗口内仍未知的日期
        List<LocalDate> syncDays = aggregates.keySet().stream()
                .sorted(Comparator.reverseOrder())
                .toList();
        for (LocalDate syncDay : syncDays) {
            int[] agg = aggregates.get(syncDay);
            int residual = Math.max(0, agg[1] - agg[0]);
            List<LocalDate> unknown = new ArrayList<>();
            for (int i = 6; i >= 1; i--) {
                LocalDate day = syncDay.minusDays(i);
                if (resolved.containsKey(day)) {
                    residual -= Math.max(0, resolved.get(day));
                } else {
                    unknown.add(day);
                }
            }
            residual = Math.max(0, residual);
            if (unknown.isEmpty() || residual == 0) {
                continue;
            }
            int base = residual / unknown.size();
            int extra = residual % unknown.size();
            for (int i = 0; i < unknown.size(); i++) {
                resolved.put(unknown.get(i), base + (i < extra ? 1 : 0));
            }
        }

        List<String> labels = new ArrayList<>(window);
        List<Integer> values = new ArrayList<>(window);
        List<Boolean> estimated = new ArrayList<>(window);
        for (int offset = window - 1; offset >= 0; offset--) {
            LocalDate date = today.minusDays(offset);
            labels.add(date.toString().substring(5));
            values.add(Math.max(0, resolved.getOrDefault(date, 0)));
            estimated.add(!synced.contains(date) && resolved.containsKey(date));
        }

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("code", 0);
        body.put("labels", labels);
        body.put("values", values);
        body.put("estimated", estimated);
        return body;
    }

    private List<String> resolveTrendShopIds(String shopId) {
        List<String> allowed = shops().stream().map(TemuShop::getShopId).toList();
        if (allowed.isEmpty()) {
            return List.of();
        }
        if (shopId == null || shopId.isBlank() || "all".equalsIgnoreCase(shopId)) {
            return allowed;
        }
        if (!allowed.contains(shopId)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "无权访问该店铺数据");
        }
        return List.of(shopId);
    }

    private Map<LocalDate, int[]> loadDailyAggregates(List<String> shopIds, LocalDate from, LocalDate to) {
        Map<LocalDate, int[]> out = new LinkedHashMap<>();
        if (shopIds.isEmpty()) {
            return out;
        }
        Long tenantId = authContext.tenantId();
        List<Object[]> rows = saleRepository.sumSalesByReportTime(
                tenantId,
                shopIds,
                from.toString(),
                to.toString()
        );
        for (Object[] row : rows) {
            if (row == null || row.length < 3 || row[0] == null) {
                continue;
            }
            LocalDate day = LocalDate.parse(String.valueOf(row[0]));
            int todaySales = ((Number) row[1]).intValue();
            int sevenSales = ((Number) row[2]).intValue();
            out.put(day, new int[]{todaySales, sevenSales});
        }
        return out;
    }
}
