package com.crosshub.taobao.service;

import com.crosshub.taobao.entity.TaobaoIssue;

import java.util.Locale;
import java.util.Map;

/**
 * Pure upsert rules for Taobao issues (spec: do not reopen resolved).
 * 对齐抖音 {@code DouyinIssueUpsert}。
 */
public final class TaobaoIssueUpsert {
    private TaobaoIssueUpsert() {}

    public static void applyIncoming(TaobaoIssue row, Map<String, Object> incoming, String now, boolean isNew) {
        if (row == null || incoming == null) {
            return;
        }
        String type = text(incoming.get("type"));
        String typeLabel = firstNonBlank(text(incoming.get("type_label")), text(incoming.get("typeLabel")), defaultLabel(type));
        String sku = firstNonBlank(text(incoming.get("sku")), "");
        String productName = firstNonBlank(text(incoming.get("product_name")), text(incoming.get("productName")));
        String productImage = firstNonBlank(
                text(incoming.get("product_image")),
                text(incoming.get("productImage")),
                text(incoming.get("main_image")),
                text(incoming.get("mainImage")),
                text(incoming.get("img"))
        );
        String detail = firstNonBlank(text(incoming.get("detail")), text(incoming.get("title")), text(incoming.get("message")));
        String priority = normalizePriority(firstNonBlank(
                text(incoming.get("priority")),
                text(incoming.get("severity")),
                text(incoming.get("level"))
        ));
        String reportedAt = firstNonBlank(
                text(incoming.get("reported_at")),
                text(incoming.get("reportedAt")),
                text(incoming.get("created_at")),
                now
        );
        String source = firstNonBlank(text(incoming.get("source")), "unknown");

        row.setType(normalizeType(type));
        row.setTypeLabel(typeLabel);
        row.setSku(sku);
        row.setProductName(productName);
        if (!productImage.isBlank()) {
            row.setProductImage(productImage);
        }
        if (!detail.isBlank()) {
            row.setDetail(detail);
        }
        row.setPriority(priority);
        if (isNew || isBlank(row.getReportedAt())) {
            row.setReportedAt(reportedAt);
        }
        row.setSource(source);
        row.setUpdatedAt(now);
        if (isNew) {
            row.setCreatedAt(now);
            row.setResolved(0);
            row.setResolvedAt("");
            row.setNote("");
        }
        // Existing resolved rows stay resolved (do not reopen).
    }

    public static String normalizeType(String type) {
        String t = type == null ? "" : type.trim().toLowerCase(Locale.ROOT);
        return switch (t) {
            case "violation", "违规", "平台违规" -> "violation";
            case "product", "商品", "商品问题" -> "product";
            case "logistics", "物流", "物流异常" -> "logistics";
            case "service", "客服", "服务工单", "服务" -> "service";
            default -> t.isBlank() ? "product" : t;
        };
    }

    public static String defaultLabel(String type) {
        return switch (normalizeType(type)) {
            case "violation" -> "平台违规";
            case "product" -> "商品问题";
            case "logistics" -> "物流异常";
            case "service" -> "服务工单";
            default -> "工单预警";
        };
    }

    public static String normalizePriority(String raw) {
        String p = raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
        if (p.isBlank()) {
            return "medium";
        }
        if (p.contains("high") || p.contains("高") || "1".equals(p) || "danger".equals(p)) {
            return "high";
        }
        if (p.contains("low") || p.contains("低") || "3".equals(p) || "info".equals(p)) {
            return "low";
        }
        return "medium";
    }

    private static boolean isBlank(String s) {
        return s == null || s.isBlank();
    }

    private static String text(Object v) {
        return v == null ? "" : String.valueOf(v).trim();
    }

    private static String firstNonBlank(String... vals) {
        if (vals == null) {
            return "";
        }
        for (String v : vals) {
            if (v != null && !v.isBlank()) {
                return v;
            }
        }
        return "";
    }
}
