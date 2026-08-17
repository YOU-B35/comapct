package com.crosshub.alibaba1688.service.impl;

import com.crosshub.alibaba1688.entity.Alibaba1688PurchaseOrder;
import com.crosshub.alibaba1688.entity.Alibaba1688SupplierAlert;
import com.crosshub.alibaba1688.entity.Alibaba1688SupplierStat;
import com.crosshub.alibaba1688.repository.Alibaba1688PurchaseOrderRepository;
import com.crosshub.alibaba1688.repository.Alibaba1688SupplierAlertRepository;
import com.crosshub.alibaba1688.repository.Alibaba1688SupplierStatRepository;
import com.crosshub.alibaba1688.service.Alibaba1688OperationalAggregator;
import com.crosshub.alibaba1688.service.Alibaba1688OperationalService;
import com.crosshub.alibaba1688.service.Alibaba1688PurchaseRules;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Service
public class Alibaba1688OperationalServiceImpl implements Alibaba1688OperationalService {
    private static final int WINDOW_DAYS = 90;
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final Alibaba1688PurchaseOrderRepository orderRepository;
    private final Alibaba1688SupplierAlertRepository alertRepository;
    private final Alibaba1688SupplierStatRepository statRepository;

    public Alibaba1688OperationalServiceImpl(
            Alibaba1688PurchaseOrderRepository orderRepository,
            Alibaba1688SupplierAlertRepository alertRepository,
            Alibaba1688SupplierStatRepository statRepository
    ) {
        this.orderRepository = orderRepository;
        this.alertRepository = alertRepository;
        this.statRepository = statRepository;
    }

    @Override
    public Map<String, Object> getOperational(Long tenantId, String storeIdOrNull) {
        List<Alibaba1688PurchaseOrder> orders;
        List<Alibaba1688SupplierAlert> alerts;
        List<Alibaba1688SupplierStat> stats;
        if (storeIdOrNull != null && !storeIdOrNull.isBlank() && !"all".equalsIgnoreCase(storeIdOrNull)) {
            orders = orderRepository.findByTenantIdAndStoreIdOrderBySyncedAtDesc(tenantId, storeIdOrNull);
            alerts = alertRepository.findByTenantIdAndStoreIdOrderByCreatedAtDesc(tenantId, storeIdOrNull);
            stats = statRepository.findByTenantIdAndStoreIdAndWindowDaysOrderByOrderCountDesc(
                    tenantId, storeIdOrNull, WINDOW_DAYS);
        } else {
            orders = orderRepository.findByTenantIdOrderBySyncedAtDesc(tenantId);
            alerts = alertRepository.findByTenantIdOrderByCreatedAtDesc(tenantId);
            stats = statRepository.findByTenantIdAndWindowDaysOrderByOrderCountDesc(tenantId, WINDOW_DAYS);
        }

        String syncedAt = "";
        for (Alibaba1688PurchaseOrder o : orders) {
            if (o.getSyncedAt() != null && !o.getSyncedAt().isBlank()) {
                syncedAt = o.getSyncedAt();
                break;
            }
        }

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("syncedAt", syncedAt);
        body.put("purchaseOrders", Alibaba1688OperationalAggregator.mapOrders(orders));
        body.put("supplierAlerts", Alibaba1688OperationalAggregator.mapAlerts(alerts));
        body.put("supplierRanking", Alibaba1688OperationalAggregator.mapRanking(stats));
        body.put("overview", Alibaba1688OperationalAggregator.buildOverview(orders, alerts));
        return body;
    }

    @Override
    @Transactional
    public void rebuildAlertsAndStats(Long tenantId) {
        LocalDateTime now = LocalDateTime.now();
        String nowTs = now.format(TS);
        List<Alibaba1688PurchaseOrder> orders = orderRepository.findByTenantIdOrderBySyncedAtDesc(tenantId);

        // Refresh delay flags from ETA rules (stockout left as ingested)
        for (Alibaba1688PurchaseOrder o : orders) {
            boolean delayed = Alibaba1688PurchaseRules.isDelayed(o.getExpectedArrivalAt(), o.getStatus(), now);
            o.setIsDelayed(delayed ? 1 : 0);
            o.setUpdatedAt(nowTs);
        }
        orderRepository.saveAll(orders);

        Set<String> keepKeys = new HashSet<>();
        for (Alibaba1688PurchaseOrder o : orders) {
            if (o.getIsDelayed() != null && o.getIsDelayed() == 1) {
                keepKeys.add(upsertAlert(tenantId, o, "delay", "high",
                        "采购单 " + o.getOrderNo() + " 已超过预计到货时间", nowTs));
            }
            if (o.getIsStockout() != null && o.getIsStockout() == 1) {
                keepKeys.add(upsertAlert(tenantId, o, "stockout", "high",
                        "采购单 " + o.getOrderNo() + " 缺货", nowTs));
            }
        }

        List<Alibaba1688SupplierAlert> existing = alertRepository.findByTenantIdOrderByCreatedAtDesc(tenantId);
        for (Alibaba1688SupplierAlert a : existing) {
            if (a.getIsOpen() == null || a.getIsOpen() != 1) continue;
            String type = a.getType() == null ? "" : a.getType();
            if (!"delay".equals(type) && !"stockout".equals(type)) continue;
            String key = alertKey(a.getStoreId(), type, a.getRelatedOrderNo());
            if (!keepKeys.contains(key)) {
                a.setIsOpen(0);
                a.setResolvedAt(nowTs);
                a.setUpdatedAt(nowTs);
                alertRepository.save(a);
            }
        }

        rebuildStats(tenantId, orders, now, nowTs);
    }

    private String upsertAlert(
            Long tenantId,
            Alibaba1688PurchaseOrder o,
            String type,
            String level,
            String message,
            String nowTs
    ) {
        String key = alertKey(o.getStoreId(), type, o.getOrderNo());
        Alibaba1688SupplierAlert alert = alertRepository
                .findByTenantIdAndStoreIdAndTypeAndRelatedOrderNo(tenantId, o.getStoreId(), type, o.getOrderNo())
                .orElseGet(Alibaba1688SupplierAlert::new);
        if (alert.getId() == null) {
            alert.setId(UUID.randomUUID().toString().replace("-", ""));
            alert.setCreatedAt(nowTs);
        }
        alert.setTenantId(tenantId);
        alert.setStoreId(o.getStoreId());
        alert.setType(type);
        alert.setSupplierName(o.getSupplierName());
        alert.setRelatedOrderNo(o.getOrderNo());
        alert.setLevel(level);
        alert.setMessage(message);
        alert.setIsOpen(1);
        alert.setResolvedAt(null);
        alert.setUpdatedAt(nowTs);
        alertRepository.save(alert);
        return key;
    }

    private static String alertKey(String storeId, String type, String orderNo) {
        return String.valueOf(storeId) + "|" + type + "|" + String.valueOf(orderNo);
    }

    private void rebuildStats(Long tenantId, List<Alibaba1688PurchaseOrder> orders, LocalDateTime now, String nowTs) {
        LocalDateTime cutoff = now.minusDays(WINDOW_DAYS);
        Map<String, Agg> byKey = new HashMap<>();
        for (Alibaba1688PurchaseOrder o : orders) {
            LocalDateTime ref = Alibaba1688OperationalAggregator.rankingRefTime(o.getSyncedAt(), o.getCreatedAt());
            if (!Alibaba1688OperationalAggregator.isWithinRankingWindow(ref, cutoff)) continue;
            String supplierKey = o.getSupplierId() != null && !o.getSupplierId().isBlank()
                    ? o.getSupplierId()
                    : (o.getSupplierName() == null ? "unknown" : o.getSupplierName().trim().toLowerCase(Locale.ROOT));
            String mapKey = o.getStoreId() + "|" + supplierKey;
            Agg agg = byKey.computeIfAbsent(mapKey, k -> new Agg(o.getStoreId(), supplierKey, o.getSupplierName()));
            agg.orderCount++;
            agg.totalAmount += o.getAmount() == null ? 0d : o.getAmount();
            Boolean onTime = Alibaba1688OperationalAggregator.computeOnTimeContribution(o.getExpectedArrivalAt(), now);
            if (onTime != null) {
                agg.etaCount++;
                if (onTime) agg.onTimeCount++;
            }
            String last = o.getSyncedAt() != null ? o.getSyncedAt() : o.getCreatedAt();
            if (last != null && (agg.lastOrderAt == null || last.compareTo(agg.lastOrderAt) > 0)) {
                agg.lastOrderAt = last;
            }
        }

        List<Alibaba1688SupplierStat> existing = new ArrayList<>(
                statRepository.findByTenantIdAndWindowDaysOrderByOrderCountDesc(tenantId, WINDOW_DAYS));
        Set<String> seen = new HashSet<>();
        for (Agg agg : byKey.values()) {
            seen.add(agg.storeId + "|" + agg.supplierKey);
            Alibaba1688SupplierStat row = statRepository
                    .findByTenantIdAndStoreIdAndSupplierKeyAndWindowDays(
                            tenantId, agg.storeId, agg.supplierKey, WINDOW_DAYS)
                    .orElseGet(Alibaba1688SupplierStat::new);
            if (row.getId() == null) {
                row.setId(UUID.randomUUID().toString().replace("-", ""));
            }
            row.setTenantId(tenantId);
            row.setStoreId(agg.storeId);
            row.setSupplierKey(agg.supplierKey);
            row.setSupplierName(agg.supplierName);
            row.setOrderCount(agg.orderCount);
            row.setTotalAmount(agg.totalAmount);
            row.setOnTimeRate(agg.etaCount == 0 ? 0d : (double) agg.onTimeCount / (double) agg.etaCount);
            row.setLastOrderAt(agg.lastOrderAt);
            row.setWindowDays(WINDOW_DAYS);
            row.setUpdatedAt(nowTs);
            statRepository.save(row);
        }
        for (Alibaba1688SupplierStat old : existing) {
            String k = old.getStoreId() + "|" + old.getSupplierKey();
            if (!seen.contains(k)) {
                statRepository.delete(old);
            }
        }
    }

    private static final class Agg {
        final String storeId;
        final String supplierKey;
        final String supplierName;
        int orderCount;
        double totalAmount;
        int etaCount;
        int onTimeCount;
        String lastOrderAt;

        Agg(String storeId, String supplierKey, String supplierName) {
            this.storeId = storeId;
            this.supplierKey = supplierKey;
            this.supplierName = supplierName;
        }
    }
}
