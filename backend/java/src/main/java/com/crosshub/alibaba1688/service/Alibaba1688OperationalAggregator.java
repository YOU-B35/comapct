package com.crosshub.alibaba1688.service;

import com.crosshub.alibaba1688.entity.Alibaba1688PurchaseOrder;
import com.crosshub.alibaba1688.entity.Alibaba1688SupplierAlert;
import com.crosshub.alibaba1688.entity.Alibaba1688SupplierStat;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

public final class Alibaba1688OperationalAggregator {
    private static final Set<String> ACTION_NEEDED = Set.of("pending_payment", "pending_shipment");
    /** Status used when judging lateness for ranking so terminal orders past ETA are not treated as on-time. */
    private static final String RANKING_DELAY_STATUS = "pending_receive";

    private Alibaba1688OperationalAggregator() {}

    /**
     * Ranking reference time: syncedAt, else createdAt. Null if both unparseable (exclude from window).
     */
    public static LocalDateTime rankingRefTime(String syncedAt, String createdAt) {
        LocalDateTime ref = Alibaba1688PurchaseRules.parseFlexible(syncedAt);
        if (ref != null) return ref;
        return Alibaba1688PurchaseRules.parseFlexible(createdAt);
    }

    /** True only when ref is parseable and on/after cutoff. Undated (null) orders are excluded. */
    public static boolean isWithinRankingWindow(LocalDateTime ref, LocalDateTime cutoff) {
        if (ref == null || cutoff == null) return false;
        return !ref.isBefore(cutoff);
    }

    /**
     * On-time contribution for ranking: null = no ETA (omit from rate);
     * true = on-time; false = late.
     * Evaluates lateness as if status were still open ({@code pending_receive}), so completed
     * past-ETA orders do not inflate onTimeRate.
     */
    public static Boolean computeOnTimeContribution(String expectedArrivalAt, LocalDateTime now) {
        if (expectedArrivalAt == null || expectedArrivalAt.isBlank()) return null;
        if (now == null) return null;
        return !Alibaba1688PurchaseRules.isDelayed(expectedArrivalAt, RANKING_DELAY_STATUS, now);
    }

    public static Map<String, Object> buildOverview(
            List<Alibaba1688PurchaseOrder> orders,
            List<Alibaba1688SupplierAlert> alerts
    ) {
        int pendingPurchase = 0;
        int delayedCount = 0;
        int stockoutCount = 0;
        for (Alibaba1688PurchaseOrder o : orders == null ? List.<Alibaba1688PurchaseOrder>of() : orders) {
            String status = o.getStatus() == null ? "" : o.getStatus().trim().toLowerCase(Locale.ROOT);
            if (ACTION_NEEDED.contains(status)) pendingPurchase++;
            if (o.getIsDelayed() != null && o.getIsDelayed() == 1) delayedCount++;
            if (o.getIsStockout() != null && o.getIsStockout() == 1) stockoutCount++;
        }
        int openAlerts = 0;
        for (Alibaba1688SupplierAlert a : alerts == null ? List.<Alibaba1688SupplierAlert>of() : alerts) {
            if (a.getIsOpen() != null && a.getIsOpen() == 1) openAlerts++;
        }
        Map<String, Object> overview = new LinkedHashMap<>();
        overview.put("pendingPurchase", pendingPurchase);
        overview.put("openAlerts", openAlerts);
        overview.put("delayedCount", delayedCount);
        overview.put("stockoutCount", stockoutCount);
        return overview;
    }

    public static boolean isActionNeeded(String status) {
        String s = status == null ? "" : status.trim().toLowerCase(Locale.ROOT);
        return ACTION_NEEDED.contains(s);
    }

    public static Map<String, Object> toPurchaseOrderDto(Alibaba1688PurchaseOrder o) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", o.getId());
        m.put("storeId", o.getStoreId());
        m.put("orderNo", o.getOrderNo());
        m.put("status", o.getStatus());
        m.put("payStatus", o.getPayStatus());
        m.put("shipStatus", o.getShipStatus());
        m.put("productName", o.getProductName());
        m.put("sku", o.getSku());
        m.put("supplierName", o.getSupplierName());
        m.put("supplierId", o.getSupplierId());
        m.put("quantity", o.getQuantity());
        m.put("unitPrice", o.getUnitPrice());
        m.put("amount", o.getAmount());
        m.put("currency", o.getCurrency());
        m.put("linkedPlatform", o.getLinkedPlatform());
        m.put("expectedArrivalAt", o.getExpectedArrivalAt());
        m.put("expectedShipAt", o.getExpectedShipAt());
        m.put("actualShipAt", o.getActualShipAt());
        m.put("logisticsStatus", o.getLogisticsStatus());
        m.put("logisticsNo", o.getLogisticsNo());
        m.put("isDelayed", o.getIsDelayed() != null && o.getIsDelayed() == 1);
        m.put("isStockout", o.getIsStockout() != null && o.getIsStockout() == 1);
        m.put("isActionNeeded", isActionNeeded(o.getStatus()));
        m.put("syncedAt", o.getSyncedAt());
        return m;
    }

    public static Map<String, Object> toAlertDto(Alibaba1688SupplierAlert a) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", a.getId());
        m.put("storeId", a.getStoreId());
        m.put("type", a.getType());
        m.put("supplierName", a.getSupplierName());
        m.put("relatedOrderNo", a.getRelatedOrderNo());
        m.put("level", a.getLevel());
        m.put("message", a.getMessage());
        m.put("isOpen", a.getIsOpen() != null && a.getIsOpen() == 1);
        m.put("createdAt", a.getCreatedAt());
        m.put("resolvedAt", a.getResolvedAt());
        return m;
    }

    public static Map<String, Object> toRankingDto(Alibaba1688SupplierStat s) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("supplierKey", s.getSupplierKey());
        m.put("supplierName", s.getSupplierName());
        m.put("orderCount", s.getOrderCount());
        m.put("totalAmount", s.getTotalAmount());
        m.put("onTimeRate", s.getOnTimeRate());
        m.put("lastOrderAt", s.getLastOrderAt());
        m.put("storeId", s.getStoreId());
        return m;
    }

    public static List<Map<String, Object>> mapOrders(List<Alibaba1688PurchaseOrder> orders) {
        List<Map<String, Object>> out = new ArrayList<>();
        for (Alibaba1688PurchaseOrder o : orders) out.add(toPurchaseOrderDto(o));
        return out;
    }

    public static List<Map<String, Object>> mapAlerts(List<Alibaba1688SupplierAlert> alerts) {
        List<Map<String, Object>> out = new ArrayList<>();
        for (Alibaba1688SupplierAlert a : alerts) out.add(toAlertDto(a));
        return out;
    }

    public static List<Map<String, Object>> mapRanking(List<Alibaba1688SupplierStat> stats) {
        List<Map<String, Object>> out = new ArrayList<>();
        for (Alibaba1688SupplierStat s : stats) out.add(toRankingDto(s));
        return out;
    }
}
