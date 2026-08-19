package com.crosshub.alibaba1688.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.time.LocalDateTime;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.time.format.DateTimeFormatter;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 1688 零售经营数据服务：消费者订单幂等入库 + 退款回写 + 经营指标聚合。
 * 金额以字符串保存，聚合时转 BigDecimal；旧采购订单绝不参与。
 */
@Service
public class Alibaba1688RetailOpsService {
    private static final DateTimeFormatter DT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final DateTimeFormatter TS_SHORT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;

    public Alibaba1688RetailOpsService(JdbcTemplate jdbc, ObjectMapper objectMapper) {
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public Map<String, Object> ingestOrders(Long tenantId, Map<String, Object> body) {
        if (tenantId == null || tenantId <= 0) {
            throw new IllegalArgumentException("tenant required");
        }
        if (body == null) {
            body = Map.of();
        }
        String storeId = text(body.get("store_id"));
        if (storeId.isBlank()) {
            storeId = "default";
        }
        String syncId = text(body.get("sync_id"));
        String now = now();

        int orderCount = 0;
        int itemCount = 0;
        for (Map<?, ?> entry : listOf(body.get("orders"))) {
            Object orderObj = entry.get("order");
            if (!(orderObj instanceof Map<?, ?> order)) {
                continue;
            }
            String orderNo = text(order.get("order_no"));
            if (orderNo.isBlank()) {
                continue;
            }
            upsertOrder(tenantId, storeId, orderNo, order, syncId, now);
            orderCount++;
            List<Map<?, ?>> items = listOf(entry.get("items"));
            itemCount += replaceItems(tenantId, storeId, orderNo, items, now);
        }

        int refundCount = 0;
        for (Map<?, ?> refund : listOf(body.get("refunds"))) {
            refundCount += applyRefund(tenantId, storeId, refund, now);
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("orderCount", orderCount);
        out.put("itemCount", itemCount);
        out.put("refundCount", refundCount);
        return out;
    }

    /** 经营口径：销售额只统计已支付订单，退款按退款发生日扣减净销售额。 */
    public Map<String, Object> summary(
            Long tenantId,
            LocalDate start,
            LocalDate end,
            String storeIdOrNull
    ) {
        Map<String, Object> current = aggregate(tenantId, start, end, storeIdOrNull);
        String storeId = normalizeStore(storeIdOrNull);
        Map<String, Object> prev = aggregate(
                tenantId,
                start.minusDays(daysBetween(start, end) + 1),
                start.minusDays(1),
                storeId
        );
        current.put("comparison", Map.of(
                "paid_sales", prev.get("paid_sales"),
                "net_sales", prev.get("net_sales"),
                "paid_order_count", prev.get("paid_order_count")
        ));
        return current;
    }

    private Map<String, Object> aggregate(
            Long tenantId,
            LocalDate start,
            LocalDate end,
            String storeIdOrNull
    ) {
        String storeId = normalizeStore(storeIdOrNull);
        List<Map<String, Object>> orders = queryOrders(tenantId, storeId);
        BigDecimal paidSales = BigDecimal.ZERO;
        BigDecimal refundAmount = BigDecimal.ZERO;
        int paidOrderCount = 0;
        int refundOrderCount = 0;
        for (Map<String, Object> row : orders) {
            String paidDay = day(text(row.get("paid_at")));
            if (!text(row.get("paid_at")).isBlank() && inRange(paidDay, start, end)) {
                paidSales = paidSales.add(decimal(text(row.get("paid_amount"))));
                paidOrderCount++;
            }
            String refundDay = day(text(row.get("refunded_at")));
            BigDecimal refund = decimal(text(row.get("refunded_amount")));
            if (!text(row.get("refunded_at")).isBlank() && inRange(refundDay, start, end) && refund.signum() > 0) {
                refundAmount = refundAmount.add(refund);
                refundOrderCount++;
            }
        }
        BigDecimal netSales = paidSales.subtract(refundAmount);
        BigDecimal averageOrderValue = paidOrderCount == 0
                ? BigDecimal.ZERO
                : paidSales.divide(BigDecimal.valueOf(paidOrderCount), 2, RoundingMode.HALF_UP);

        BigDecimal soldQuantity = BigDecimal.ZERO;
        java.util.Set<String> soldProducts = new java.util.HashSet<>();
        for (Map<String, Object> item : queryItems(tenantId, storeId)) {
            String orderPaidDay = day(text(item.get("paid_at")));
            if (text(item.get("paid_at")).isBlank() || !inRange(orderPaidDay, start, end)) {
                continue;
            }
            soldQuantity = soldQuantity.add(decimal(text(item.get("quantity"))));
            String offerId = text(item.get("offer_id"));
            if (!offerId.isBlank()) {
                soldProducts.add(offerId);
            }
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("paid_sales", paidSales);
        out.put("refund_amount", refundAmount);
        out.put("net_sales", netSales);
        out.put("paid_order_count", paidOrderCount);
        out.put("refund_order_count", refundOrderCount);
        out.put("average_order_value", averageOrderValue);
        out.put("sold_quantity", soldQuantity);
        out.put("sold_product_count", soldProducts.size());
        return out;
    }

    /** 按日趋势：支付销售额、退款金额、净销售额、订单数。 */
    public List<Map<String, Object>> trend(
            Long tenantId,
            LocalDate start,
            LocalDate end,
            String storeIdOrNull
    ) {
        String storeId = normalizeStore(storeIdOrNull);
        List<Map<String, Object>> orders = queryOrders(tenantId, storeId);
        java.util.Map<LocalDate, Map<String, Object>> byDay = new java.util.TreeMap<>();
        LocalDate cursor = start;
        while (!cursor.isAfter(end)) {
            Map<String, Object> day = new LinkedHashMap<>();
            day.put("date", cursor.toString());
            day.put("paid_sales", BigDecimal.ZERO);
            day.put("refund_amount", BigDecimal.ZERO);
            day.put("net_sales", BigDecimal.ZERO);
            day.put("paid_order_count", 0);
            day.put("refund_order_count", 0);
            byDay.put(cursor, day);
            cursor = cursor.plusDays(1);
        }
        for (Map<String, Object> row : orders) {
            LocalDate paidDate = parseDay(text(row.get("paid_at")));
            if (paidDate != null && inRange(paidDate, start, end)) {
                Map<String, Object> day = byDay.get(paidDate);
                if (day != null) {
                    day.put("paid_sales", ((BigDecimal) day.get("paid_sales"))
                            .add(decimal(text(row.get("paid_amount")))));
                    day.put("paid_order_count", ((Number) day.get("paid_order_count")).intValue() + 1);
                }
            }
            LocalDate refundDate = parseDay(text(row.get("refunded_at")));
            if (refundDate != null && inRange(refundDate, start, end)
                    && decimal(text(row.get("refunded_amount"))).signum() > 0) {
                Map<String, Object> day = byDay.get(refundDate);
                if (day != null) {
                    day.put("refund_amount", ((BigDecimal) day.get("refund_amount"))
                            .add(decimal(text(row.get("refunded_amount")))));
                    day.put("refund_order_count", ((Number) day.get("refund_order_count")).intValue() + 1);
                }
            }
        }
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> day : byDay.values()) {
            BigDecimal paid = (BigDecimal) day.get("paid_sales");
            BigDecimal refund = (BigDecimal) day.get("refund_amount");
            day.put("net_sales", paid.subtract(refund));
            out.add(day);
        }
        return out;
    }

    /** 订单明细（订单行级），支持日期/店铺/状态/关键词/退款筛选与分页。 */
    public Map<String, Object> listOrders(
            Long tenantId,
            LocalDate start,
            LocalDate end,
            String status,
            String keyword,
            String storeIdOrNull,
            int page,
            int pageSize
    ) {
        String storeId = normalizeStore(storeIdOrNull);
        int safePage = Math.max(1, page);
        int safeSize = Math.min(100, Math.max(1, pageSize));
        String statusFilter = text(status);
        String keywordFilter = text(keyword);
        StringBuilder where = new StringBuilder(
                " WHERE o.tenant_id = ? AND (? = '' OR o.store_id = ?) AND (? = '' OR o.status = ?)");
        List<Object> args = new ArrayList<>();
        args.add(tenantId);
        args.add(storeId);
        args.add(storeId);
        args.add(statusFilter);
        args.add(statusFilter);
        if (start != null && end != null) {
            where.append(" AND substr(o.paid_at,1,10) BETWEEN ? AND ?");
            args.add(start.toString());
            args.add(end.toString());
        }
        if (!keywordFilter.isBlank()) {
            where.append(" AND (? = '' OR o.order_no LIKE ? OR i.product_name LIKE ?)");
            args.add(keywordFilter);
            args.add("%" + keywordFilter + "%");
            args.add("%" + keywordFilter + "%");
        } else {
            where.append(" AND ? = ''");
            args.add(keywordFilter);
        }

        Integer total = jdbc.queryForObject(
                "SELECT COUNT(1) FROM alibaba1688_order o "
                        + "JOIN alibaba1688_order_item i ON i.tenant_id = o.tenant_id "
                        + "AND i.store_id = o.store_id AND i.order_no = o.order_no"
                        + where,
                Integer.class,
                args.toArray()
        );

        String sql = "SELECT o.order_no, o.status, o.paid_amount, o.refunded_amount, o.paid_at, "
                + "o.refunded_at, o.created_platform_at, o.store_id, o.buyer_masked, "
                + "i.line_id, i.offer_id, i.sku_id, i.sku_text, i.product_name, i.quantity, "
                + "i.paid_amount AS item_amount, i.actual_unit_price, i.image_url "
                + "FROM alibaba1688_order o JOIN alibaba1688_order_item i "
                + "ON i.tenant_id = o.tenant_id AND i.store_id = o.store_id AND i.order_no = o.order_no"
                + where
                + " ORDER BY o.paid_at DESC, o.order_no, i.line_id LIMIT ? OFFSET ?";
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(safeSize);
        pageArgs.add((safePage - 1) * safeSize);
        List<Map<String, Object>> rows = jdbc.queryForList(sql, pageArgs.toArray());
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            Map<String, Object> dto = new LinkedHashMap<>();
            dto.put("storeId", row.get("store_id"));
            dto.put("orderNo", row.get("order_no"));
            dto.put("status", row.get("status"));
            dto.put("paidAmount", row.get("paid_amount"));
            dto.put("refundedAmount", row.get("refunded_amount"));
            dto.put("paidAt", row.get("paid_at"));
            dto.put("refundedAt", row.get("refunded_at"));
            dto.put("createdAt", row.get("created_platform_at"));
            dto.put("buyerMasked", row.get("buyer_masked"));
            dto.put("lineId", row.get("line_id"));
            dto.put("offerId", row.get("offer_id"));
            dto.put("skuId", row.get("sku_id"));
            dto.put("skuText", row.get("sku_text"));
            dto.put("productName", row.get("product_name"));
            dto.put("quantity", row.get("quantity"));
            dto.put("itemAmount", row.get("item_amount"));
            dto.put("unitPrice", row.get("actual_unit_price"));
            dto.put("imageUrl", row.get("image_url"));
            items.add(dto);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", items);
        out.put("total", total == null ? 0 : total);
        out.put("page", safePage);
        out.put("pageSize", safeSize);
        return out;
    }

    /**
     * 商品数据分析列表：
     * - bestsellers：近 30 天销量分层（爆款≥30 / 潜力爆款≥10 / 一般≥1 / 无销量=0）
     * - today_bestsellers：24 小时内销量 ≥10
     * - recent_sales：近 3 天上架（product_updated_at）商品及其销售/状态
     */
    public Map<String, Object> productAnalytics(String type, Long tenantId, String storeIdOrNull) {
        String storeId = normalizeStore(storeIdOrNull);
        LocalDate today = LocalDate.now();
        List<Object> args = new ArrayList<>();
        String salesWhere;
        switch (type == null ? "" : type) {
            case "bestsellers", "recent_sales" -> {
                salesWhere = " AND o.paid_at <> '' AND substr(o.paid_at,1,10) BETWEEN '"
                        + today.minusDays(29) + "' AND '" + today + "'";
            }
            case "today_bestsellers" -> {
                String cutoff = LocalDateTime.now().minusHours(24).format(DT);
                salesWhere = " AND o.paid_at <> '' AND o.paid_at >= '" + cutoff + "'";
            }
            default -> throw new IllegalArgumentException("未知分析类型: " + type);
        }
        String salesSub = """
                SELECT i.offer_id,
                       SUM(CAST(i.quantity AS REAL)) sales_qty,
                       SUM(CAST(i.paid_amount AS REAL)) sales_amount,
                       COUNT(DISTINCT o.order_no) order_count
                FROM alibaba1688_order_item i
                JOIN alibaba1688_order o
                  ON o.tenant_id = i.tenant_id AND o.store_id = i.store_id AND o.order_no = i.order_no
                WHERE i.tenant_id = ? AND (? = '' OR i.store_id = ?)
                """ + salesWhere + " GROUP BY i.offer_id";
        args.add(tenantId);
        args.add(storeId);
        args.add(storeId);

        StringBuilder sql = new StringBuilder("""
                SELECT p.offer_id, p.product_name, p.price, p.stock, p.status, p.image_url, p.product_updated_at,
                       COALESCE(a.sales_qty, 0) sales_qty,
                       COALESCE(a.sales_amount, 0) sales_amount,
                       COALESCE(a.order_count, 0) order_count
                FROM alibaba1688_product p
                LEFT JOIN (%s) a ON a.offer_id = p.offer_id
                WHERE p.tenant_id = ? AND (? = '' OR p.store_id = ?)
                """.formatted(salesSub));
        args.add(tenantId);
        args.add(storeId);
        args.add(storeId);
        if ("recent_sales".equals(type)) {
            sql.append(" AND p.product_updated_at <> '' AND p.product_updated_at >= ?");
            args.add(LocalDateTime.now().minusDays(3).format(TS_SHORT));
        }
        if ("today_bestsellers".equals(type)) {
            sql.append(" AND a.sales_qty >= 10");
        }
        sql.append(" ORDER BY a.sales_qty DESC, p.offer_id");

        List<Map<String, Object>> rows = jdbc.queryForList(sql.toString(), args.toArray());
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            double qty = doubleOf(row.get("sales_qty"));
            Map<String, Object> dto = new LinkedHashMap<>();
            dto.put("offerId", row.get("offer_id"));
            dto.put("productName", row.get("product_name"));
            dto.put("price", row.get("price"));
            dto.put("stock", row.get("stock"));
            dto.put("status", row.get("status"));
            dto.put("imageUrl", row.get("image_url"));
            dto.put("productUpdatedAt", row.get("product_updated_at"));
            dto.put("salesQty", qty);
            dto.put("salesAmount", row.get("sales_amount"));
            dto.put("orderCount", row.get("order_count"));
            if ("bestsellers".equals(type)) {
                dto.put("tier", bestsellerTier(qty));
            }
            items.add(dto);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("type", type);
        out.put("items", items);
        out.put("total", items.size());
        return out;
    }

    private static String bestsellerTier(double qty) {
        if (qty >= 30) {
            return "爆款";
        }
        if (qty >= 10) {
            return "潜力爆款";
        }
        if (qty >= 1) {
            return "一般";
        }
        return "无销量";
    }

    /** 最近 1688 商品/订单同步任务日志（时间 + 成功/失败 + 结果摘要）。 */
    public Map<String, Object> listSyncLogs(Long tenantId, int limit) {
        int safeLimit = Math.min(50, Math.max(1, limit));
        List<Map<String, Object>> rows = jdbc.queryForList(
                """
                SELECT id, task_type, status, error_code, error_message, result_json,
                       created_at, started_at, finished_at
                FROM agent_task
                WHERE tenant_id = ?
                  AND task_type IN ('1688_products_sync', '1688_orders_sync')
                ORDER BY rowid DESC
                LIMIT ?
                """,
                tenantId,
                safeLimit
        );
        List<Map<String, Object>> logs = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            String taskType = text(row.get("task_type"));
            Map<String, Object> log = new LinkedHashMap<>();
            log.put("taskId", row.get("id"));
            log.put("type", "1688_orders_sync".equals(taskType) ? "orders" : "products");
            log.put("label", "1688_orders_sync".equals(taskType) ? "订单同步" : "商品同步");
            log.put("status", row.get("status"));
            log.put("errorCode", row.get("error_code"));
            log.put("errorMessage", row.get("error_message"));
            log.put("createdAt", row.get("created_at"));
            log.put("startedAt", row.get("started_at"));
            log.put("finishedAt", row.get("finished_at"));
            log.put("durationMs", durationMs(text(row.get("started_at")), text(row.get("finished_at"))));
            log.put("summary", parseResultSummary(text(row.get("result_json"))));
            logs.add(log);
        }
        return Map.of("items", logs, "total", logs.size());
    }

    /** 替换整份同行爆款快照（由 Helper 爬取任务调用）。 */
    @Transactional
    public Map<String, Object> replacePeerBestsellers(Long tenantId, Map<String, Object> body) {
        if (tenantId == null || tenantId <= 0) {
            throw new IllegalArgumentException("tenant required");
        }
        String now = now();
        jdbc.update("DELETE FROM alibaba1688_peer_bestseller WHERE tenant_id = ?", tenantId);
        int count = 0;
        for (Map<?, ?> item : listOf(body == null ? null : body.get("items"))) {
            String offerId = text(item.get("offer_id"));
            if (offerId.isBlank()) {
                continue;
            }
            int sales = (int) Math.round(doubleOf(item.get("sales")));
            String suggestion = text(item.get("suggestion"));
            if (suggestion.isBlank()) {
                suggestion = peerSuggestion(sales);
            }
            jdbc.update(
                    """
                    INSERT INTO alibaba1688_peer_bestseller (
                      id, tenant_id, offer_id, shop_name, title, price, sales, sale_text,
                      offer_url, image_url, quality_score, suggestion, synced_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    UUID.randomUUID().toString(),
                    tenantId,
                    offerId,
                    text(item.get("shop_name")),
                    text(item.get("title")),
                    text(item.get("price")),
                    sales,
                    text(item.get("sale_text")),
                    text(item.get("offer_url")),
                    text(item.get("image_url")),
                    text(item.get("quality_score")),
                    suggestion,
                    now,
                    now,
                    now
            );
            count++;
        }
        return Map.of("ingested", count);
    }

    /** 同行爆款分页查询（按销量降序），每页默认 10 条。 */
    public Map<String, Object> listPeerBestsellers(Long tenantId, int page, int pageSize) {
        int safePage = Math.max(1, page);
        int safeSize = Math.min(50, Math.max(1, pageSize));
        Integer total = jdbc.queryForObject(
                "SELECT COUNT(1) FROM alibaba1688_peer_bestseller WHERE tenant_id = ?",
                Integer.class,
                tenantId
        );
        List<Map<String, Object>> rows = jdbc.queryForList(
                """
                SELECT offer_id, shop_name, title, price, sales, sale_text, offer_url, image_url, quality_score, suggestion, synced_at
                FROM alibaba1688_peer_bestseller
                WHERE tenant_id = ?
                ORDER BY sales DESC, offer_id
                LIMIT ? OFFSET ?
                """,
                tenantId,
                safeSize,
                (safePage - 1) * safeSize
        );
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            Map<String, Object> dto = new LinkedHashMap<>();
            dto.put("offerId", row.get("offer_id"));
            dto.put("shopName", row.get("shop_name"));
            dto.put("title", row.get("title"));
            dto.put("price", row.get("price"));
            dto.put("sales", row.get("sales"));
            dto.put("saleText", row.get("sale_text"));
            dto.put("offerUrl", row.get("offer_url"));
            dto.put("imageUrl", row.get("image_url"));
            dto.put("qualityScore", row.get("quality_score"));
            dto.put("suggestion", row.get("suggestion"));
            dto.put("syncedAt", row.get("synced_at"));
            items.add(dto);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", items);
        out.put("total", total == null ? 0 : total);
        out.put("page", safePage);
        out.put("pageSize", safeSize);
        return out;
    }

    private static String peerSuggestion(int sales) {
        if (sales >= 100000) {
            return "现象级爆款，建议重点对标价格与卖点";
        }
        if (sales >= 10000) {
            return "高销量爆款，建议重点追踪";
        }
        if (sales >= 1000) {
            return "热销款，建议持续关注";
        }
        if (sales >= 100) {
            return "有起量迹象，建议观察趋势";
        }
        return "销量一般，建议结合价格与质量评估";
    }

    private Map<String, Object> parseResultSummary(String resultJson) {
        Map<String, Object> out = new LinkedHashMap<>();
        if (resultJson == null || resultJson.isBlank()) {
            return out;
        }
        try {
            Map<?, ?> root = objectMapper.readValue(resultJson, Map.class);
            for (String key : new String[]{"orders_count", "items_count", "refunds_count", "products_count", "count", "partial"}) {
                Object value = root.get(key);
                if (value != null) {
                    out.put(key, value);
                }
            }
            if (root.get("categories") instanceof Map<?, ?> categories) {
                long failed = categories.values().stream()
                        .filter(v -> v instanceof Map<?, ?> m && "failed".equals(m.get("status")))
                        .count();
                out.put("category_failed", failed);
            }
        } catch (Exception ignored) {
            // 非 JSON 结果（失败任务）不解析
        }
        return out;
    }

    private static Long durationMs(String startedAt, String finishedAt) {
        if (startedAt == null || startedAt.isBlank() || finishedAt == null || finishedAt.isBlank()) {
            return null;
        }
        try {
            LocalDateTime start = LocalDateTime.parse(startedAt, DT);
            LocalDateTime end = LocalDateTime.parse(finishedAt, DT);
            return java.time.Duration.between(start, end).toMillis();
        } catch (DateTimeParseException ex) {
            return null;
        }
    }

    private void upsertOrder(
            Long tenantId,
            String storeId,
            String orderNo,
            Map<?, ?> order,
            String syncId,
            String now
    ) {
        jdbc.update(
                """
                INSERT INTO alibaba1688_order (
                  id, tenant_id, store_id, order_no, status, paid_amount, refunded_amount,
                  paid_at, refunded_at, created_platform_at, updated_platform_at,
                  buyer_masked, raw_json, synced_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, store_id, order_no) DO UPDATE SET
                  status = excluded.status,
                  paid_amount = excluded.paid_amount,
                  paid_at = excluded.paid_at,
                  created_platform_at = excluded.created_platform_at,
                  updated_platform_at = excluded.updated_platform_at,
                  buyer_masked = excluded.buyer_masked,
                  raw_json = excluded.raw_json,
                  synced_at = excluded.synced_at,
                  updated_at = excluded.updated_at
                """,
                UUID.randomUUID().toString(),
                tenantId,
                storeId,
                orderNo,
                text(order.get("status")),
                text(order.get("paid_amount"), "0"),
                text(order.get("refunded_amount"), "0"),
                text(order.get("paid_at")),
                text(order.get("refunded_at")),
                text(order.get("created_platform_at")),
                text(order.get("updated_platform_at")),
                text(order.get("buyer_masked")),
                compactJson(order),
                syncId.isBlank() ? now : syncId,
                now,
                now
        );
    }

    private int replaceItems(
            Long tenantId,
            String storeId,
            String orderNo,
            List<Map<?, ?>> items,
            String now
    ) {
        jdbc.update(
                "DELETE FROM alibaba1688_order_item WHERE tenant_id = ? AND store_id = ? AND order_no = ?",
                tenantId,
                storeId,
                orderNo
        );
        int count = 0;
        for (Map<?, ?> item : items) {
            jdbc.update(
                    """
                    INSERT INTO alibaba1688_order_item (
                      id, tenant_id, store_id, order_no, line_id, offer_id, sku_id,
                      sku_text, product_name, quantity, paid_amount, refunded_amount,
                      actual_unit_price, image_url, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    UUID.randomUUID().toString(),
                    tenantId,
                    storeId,
                    orderNo,
                    text(item.get("line_id")),
                    text(item.get("offer_id")),
                    text(item.get("sku_id")),
                    text(item.get("sku_text")),
                    text(item.get("product_name")),
                    text(item.get("quantity"), "0"),
                    text(item.get("paid_amount"), "0"),
                    text(item.get("refunded_amount"), "0"),
                    text(item.get("unit_price")),
                    text(item.get("image_url")),
                    compactJson(item)
            );
            count++;
        }
        return count;
    }

    private int applyRefund(Long tenantId, String storeId, Map<?, ?> refund, String now) {
        String orderNo = text(refund.get("order_no"));
        if (orderNo.isBlank()) {
            return 0;
        }
        int updated = jdbc.update(
                """
                UPDATE alibaba1688_order
                SET refunded_amount = ?, refunded_at = ?, updated_at = ?
                WHERE tenant_id = ? AND store_id = ? AND order_no = ?
                """,
                text(refund.get("refunded_amount"), "0"),
                text(refund.get("refunded_at")),
                now,
                tenantId,
                storeId,
                orderNo
        );
        if (updated > 0) {
            return updated;
        }
        // 平台退款接口的 orderId 会因 JS 精度丢失末几位（例如 5127251402284040047
        // -> 5127251402284040000）；用前 15 位前缀匹配已入库订单。
        return jdbc.update(
                """
                UPDATE alibaba1688_order
                SET refunded_amount = ?, refunded_at = ?, updated_at = ?
                WHERE tenant_id = ? AND store_id = ? AND substr(order_no, 1, 15) = substr(?, 1, 15)
                """,
                text(refund.get("refunded_amount"), "0"),
                text(refund.get("refunded_at")),
                now,
                tenantId,
                storeId,
                orderNo
        );
    }

    private List<Map<String, Object>> queryOrders(Long tenantId, String storeId) {
        return jdbc.queryForList(
                """
                SELECT order_no, status, paid_amount, refunded_amount, paid_at, refunded_at
                FROM alibaba1688_order
                WHERE tenant_id = ? AND (? = '' OR store_id = ?)
                """,
                tenantId,
                storeId,
                storeId
        );
    }

    private List<Map<String, Object>> queryItems(Long tenantId, String storeId) {
        return jdbc.queryForList(
                """
                SELECT i.order_no, i.offer_id, i.quantity, o.paid_at
                FROM alibaba1688_order_item i
                JOIN alibaba1688_order o
                  ON o.tenant_id = i.tenant_id AND o.store_id = i.store_id AND o.order_no = i.order_no
                WHERE i.tenant_id = ? AND (? = '' OR i.store_id = ?)
                """,
                tenantId,
                storeId,
                storeId
        );
    }

    private static String normalizeStore(String storeIdOrNull) {
        String storeId = text(storeIdOrNull);
        return storeId.isBlank() ? "" : storeId;
    }

    private static String day(String dateTime) {
        String s = text(dateTime);
        return s.length() >= 10 ? s.substring(0, 10) : s;
    }

    private static LocalDate parseDay(String dateTime) {
        String d = day(dateTime);
        if (d.isBlank()) {
            return null;
        }
        try {
            return LocalDate.parse(d);
        } catch (DateTimeParseException ex) {
            return null;
        }
    }

    private static boolean inRange(String day, LocalDate start, LocalDate end) {
        LocalDate d = parseDay(day);
        return d != null && !d.isBefore(start) && !d.isAfter(end);
    }

    private static boolean inRange(LocalDate d, LocalDate start, LocalDate end) {
        return d != null && !d.isBefore(start) && !d.isAfter(end);
    }

    private static long daysBetween(LocalDate start, LocalDate end) {
        return java.time.temporal.ChronoUnit.DAYS.between(start, end);
    }

    private static BigDecimal decimal(String value) {
        String s = text(value);
        if (s.isBlank()) {
            return BigDecimal.ZERO;
        }
        try {
            return new BigDecimal(s);
        } catch (NumberFormatException ex) {
            return BigDecimal.ZERO;
        }
    }

    private static double doubleOf(Object value) {
        if (value == null) {
            return 0d;
        }
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        try {
            return Double.parseDouble(String.valueOf(value));
        } catch (NumberFormatException ex) {
            return 0d;
        }
    }

    private static List<Map<?, ?>> listOf(Object value) {
        List<Map<?, ?>> out = new ArrayList<>();
        if (value instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map<?, ?>) {
                    out.add((Map<?, ?>) item);
                }
            }
        }
        return out;
    }

    private static String text(Object value) {
        return text(value, "");
    }

    private static String text(Object value, String defaultValue) {
        if (value == null) {
            return defaultValue;
        }
        return String.valueOf(value).trim();
    }

    private static String compactJson(Map<?, ?> map) {
        if (map == null || map.isEmpty()) {
            return "";
        }
        try {
            StringBuilder sb = new StringBuilder();
            appendJson(sb, map);
            return sb.toString();
        } catch (Exception ex) {
            return "";
        }
    }

    @SuppressWarnings("unchecked")
    private static void appendJson(StringBuilder sb, Object value) {
        if (value == null) {
            sb.append("null");
        } else if (value instanceof String s) {
            sb.append('"').append(s.replace("\\", "\\\\").replace("\"", "\\\"")).append('"');
        } else if (value instanceof Number || value instanceof Boolean) {
            sb.append(value);
        } else if (value instanceof Map<?, ?> map) {
            sb.append('{');
            boolean first = true;
            for (Map.Entry<?, ?> e : map.entrySet()) {
                if (!first) {
                    sb.append(',');
                }
                first = false;
                appendJson(sb, String.valueOf(e.getKey()));
                sb.append(':');
                appendJson(sb, e.getValue());
            }
            sb.append('}');
        } else if (value instanceof List<?> list) {
            sb.append('[');
            boolean first = true;
            for (Object item : list) {
                if (!first) {
                    sb.append(',');
                }
                first = false;
                appendJson(sb, item);
            }
            sb.append(']');
        } else {
            appendJson(sb, String.valueOf(value));
        }
    }

    static String now() {
        return LocalDateTime.now().format(DT);
    }
}
