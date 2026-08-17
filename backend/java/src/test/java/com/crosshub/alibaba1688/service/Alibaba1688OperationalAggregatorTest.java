package com.crosshub.alibaba1688.service;

import com.crosshub.alibaba1688.entity.Alibaba1688PurchaseOrder;
import com.crosshub.alibaba1688.entity.Alibaba1688SupplierAlert;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class Alibaba1688OperationalAggregatorTest {

    private static final LocalDateTime NOW = LocalDateTime.of(2026, 8, 17, 12, 0);

    private static Alibaba1688PurchaseOrder order(String no, String status, boolean delayed, boolean stockout) {
        Alibaba1688PurchaseOrder o = new Alibaba1688PurchaseOrder();
        o.setOrderNo(no);
        o.setStatus(status);
        o.setIsDelayed(delayed ? 1 : 0);
        o.setIsStockout(stockout ? 1 : 0);
        o.setAmount(100d);
        o.setSupplierName("S-" + no);
        return o;
    }

    @Test
    void overviewCountsDelayedAndStockout() {
        var orders = List.of(
                order("A", "pending_payment", true, false),
                order("B", "pending_shipment", false, true),
                order("C", "completed", false, false)
        );
        Map<String, Object> overview = Alibaba1688OperationalAggregator.buildOverview(orders, List.of());
        assertEquals(1, overview.get("delayedCount"));
        assertEquals(1, overview.get("stockoutCount"));
        assertEquals(2, overview.get("pendingPurchase"));
        assertEquals(0, overview.get("openAlerts"));
    }

    @Test
    void overviewCountsOpenAlerts() {
        Alibaba1688SupplierAlert open = new Alibaba1688SupplierAlert();
        open.setIsOpen(1);
        Alibaba1688SupplierAlert closed = new Alibaba1688SupplierAlert();
        closed.setIsOpen(0);
        Map<String, Object> overview = Alibaba1688OperationalAggregator.buildOverview(
                List.of(), List.of(open, closed));
        assertEquals(1, overview.get("openAlerts"));
    }

    @Test
    void completedPastEtaDoesNotCountAsOnTime() {
        // PurchaseRules.isDelayed(completed) == false, but ranking must still treat past ETA as late
        assertFalse(Alibaba1688PurchaseRules.isDelayed(
                "2026-08-01 00:00:00", "completed", NOW));
        Boolean contribution = Alibaba1688OperationalAggregator.computeOnTimeContribution(
                "2026-08-01 00:00:00", NOW);
        assertEquals(Boolean.FALSE, contribution);
    }

    @Test
    void futureEtaCountsAsOnTime() {
        assertEquals(Boolean.TRUE, Alibaba1688OperationalAggregator.computeOnTimeContribution(
                "2026-08-20 00:00:00", NOW));
    }

    @Test
    void blankEtaOmitsFromOnTimeRate() {
        assertNull(Alibaba1688OperationalAggregator.computeOnTimeContribution(null, NOW));
        assertNull(Alibaba1688OperationalAggregator.computeOnTimeContribution("  ", NOW));
    }

    @Test
    void undatedOrdersExcludedFromRankingWindow() {
        LocalDateTime cutoff = NOW.minusDays(90);
        assertNull(Alibaba1688OperationalAggregator.rankingRefTime(null, null));
        assertNull(Alibaba1688OperationalAggregator.rankingRefTime("", "not-a-date"));
        assertFalse(Alibaba1688OperationalAggregator.isWithinRankingWindow(null, cutoff));
    }

    @Test
    void datedOrderInsideWindowIncluded() {
        LocalDateTime cutoff = NOW.minusDays(90);
        LocalDateTime ref = Alibaba1688OperationalAggregator.rankingRefTime("2026-07-01 10:00:00", null);
        assertTrue(Alibaba1688OperationalAggregator.isWithinRankingWindow(ref, cutoff));
    }

    @Test
    void datedOrderBeforeCutoffExcluded() {
        LocalDateTime cutoff = NOW.minusDays(90);
        LocalDateTime ref = Alibaba1688OperationalAggregator.rankingRefTime("2025-01-01 00:00:00", null);
        assertFalse(Alibaba1688OperationalAggregator.isWithinRankingWindow(ref, cutoff));
    }
}
