package com.crosshub.temu.service.impl;

import com.crosshub.temu.service.TemuWarningService;
import com.crosshub.temu.dto.ReplenishResult;
import com.crosshub.temu.dto.LowSaleWarning;
import com.crosshub.temu.dto.InventoryWarning;

import com.crosshub.temu.entity.TemuSale;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
public class TemuWarningServiceImpl implements TemuWarningService {
    private static final double W1 = 0.7;
    private static final double W2 = 0.3;
    private static final int SAFETY_DAYS = 3;
    private static final int TARGET_DAYS = 15;
    private static final double DEFAULT_LEAD = 7.0;
    private static final double TREND_MIN = 0.8;
    private static final double TREND_MAX = 1.5;
    /** 与前端 RESTOCK_CONFIG.hotSurgeRatio / hotMinDailySales 对齐 */
    private static final double HOT_SURGE_RATIO = 1.5;
    private static final int HOT_MIN_DAILY_SALES = 1;




    public ReplenishResult calcReplenish(int s7, int s30, int stock, double leadTime) {
        double d7 = s7 / 7.0;
        double d30 = s30 / 30.0;
        double d = d7 * W1 + d30 * W2;

        double trend = 1.0;
        if (d30 > 0) {
            trend = d7 / d30;
            trend = Math.max(TREND_MIN, Math.min(trend, TREND_MAX));
        }
        double dAdj = d * trend;
        double warningDays = leadTime + SAFETY_DAYS;

        if (dAdj <= 0) {
            return new ReplenishResult(false, 0, 1e9, 0, dAdj, warningDays);
        }

        double coverDays = stock / dAdj;
        if (coverDays < warningDays) {
            double targetStock = dAdj * TARGET_DAYS;
            int replenish = (int) Math.ceil(targetStock - stock);
            if (replenish < 0) replenish = 0;
            return new ReplenishResult(true, replenish, coverDays, targetStock, dAdj, warningDays);
        }
        return new ReplenishResult(false, 0, coverDays, 0, dAdj, warningDays);
    }

    public int[] estimateS10S15(int today, int last7, int last30) {
        if (last30 < last7) last30 = last7;
        double avg7 = last7 / 7.0;
        double avg30 = last30 / 30.0;
        double weighted = avg7 * 0.5 + avg30 * 0.5;
        int s10 = (int) Math.round(last7 + 3.0 * weighted);
        int s15 = (int) Math.round(last7 + 8.0 * weighted);
        return new int[]{s10, s15};
    }

    public List<TemuSale> loseProducts(List<TemuSale> sales) {
        List<TemuSale> result = new ArrayList<>();
        for (TemuSale sale : sales) {
            int cost = sale.getCost() == null ? 0 : sale.getCost();
            int price = sale.getSonPrice() == null ? 0 : sale.getSonPrice();
            if (cost != 0 && price - cost < 0) {
                result.add(sale);
            }
        }
        return result;
    }

    public List<LowSaleWarning> lowSaleWarnings(List<TemuSale> sales) {
        return slowMovingEstimates(sales);
    }

    public List<LowSaleWarning> allLowSaleEstimates(List<TemuSale> sales) {
        return slowMovingEstimates(sales);
    }

    private List<LowSaleWarning> slowMovingEstimates(List<TemuSale> sales) {
        List<LowSaleWarning> warnings = new ArrayList<>();
        for (TemuSale sale : sales) {
            if (!isSlowCandidate(sale)) {
                continue;
            }
            int today = safeInt(sale.getSonTodaySales());
            int s7 = safeInt(sale.getSonSalesSevenDays());
            int s30 = safeInt(sale.getSonSalesThirtyDays());
            int[] est = estimateS10S15(today, s7, s30);
            warnings.add(new LowSaleWarning(sale, est[0], est[1]));
        }
        return warnings;
    }

    private boolean isSlowCandidate(TemuSale sale) {
        if (!"300".equals(sale.getStatus())) {
            return false;
        }
        int stock = safeInt(sale.getWarehouseAvailableStock());
        if (stock <= 0) {
            return false;
        }
        int s7 = safeInt(sale.getSonSalesSevenDays());
        int today = safeInt(sale.getSonTodaySales());
        return s7 <= 0 && today <= 0;
    }

    public List<InventoryWarning> inventoryWarnings(List<TemuSale> sales) {
        List<InventoryWarning> warnings = new ArrayList<>();
        for (TemuSale sale : sales) {
            int s7 = safeInt(sale.getSonSalesSevenDays());
            int s30 = safeInt(sale.getSonSalesThirtyDays());
            int stock = safeInt(sale.getWarehouseAvailableStock());
            ReplenishResult calc = calcReplenish(s7, s30, stock, DEFAULT_LEAD);
            if (calc.needReplenish()) {
                warnings.add(new InventoryWarning(sale, calc));
            }
        }
        return warnings;
    }

    public List<TemuSale> overloadProducts(List<TemuSale> sales, int limit) {
        int cap = Math.max(0, limit);
        return sales.stream()
                .filter(this::isHotProduct)
                .sorted(Comparator
                        .comparingDouble(this::hotSurgeScore).reversed()
                        .thenComparing((TemuSale s) -> safeInt(s.getSonTodaySales()), Comparator.reverseOrder()))
                .limit(cap)
                .toList();
    }

    /** 与前端 isHotProduct 对齐：今日销量 ≥1，且（新动销 或 今日/7日均 ≥ 1.5） */
    boolean isHotProduct(TemuSale sale) {
        int today = safeInt(sale.getSonTodaySales());
        if (today < HOT_MIN_DAILY_SALES) {
            return false;
        }
        double avg7 = safeInt(sale.getSonSalesSevenDays()) / 7.0;
        if (avg7 <= 0) {
            return true;
        }
        return today / avg7 >= HOT_SURGE_RATIO;
    }

    private double hotSurgeScore(TemuSale sale) {
        int today = safeInt(sale.getSonTodaySales());
        double avg7 = safeInt(sale.getSonSalesSevenDays()) / 7.0;
        if (avg7 <= 0) {
            return today > 0 ? Double.MAX_VALUE : 0;
        }
        return today / avg7;
    }

    private int safeInt(Integer value) {
        return value == null ? 0 : value;
    }
}
