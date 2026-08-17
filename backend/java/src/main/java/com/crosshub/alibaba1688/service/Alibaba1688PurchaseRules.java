package com.crosshub.alibaba1688.service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.Collection;
import java.util.Locale;

public final class Alibaba1688PurchaseRules {
    private static final DateTimeFormatter[] DATE_TIMES = {
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"),
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss"),
            DateTimeFormatter.ISO_LOCAL_DATE_TIME
    };
    private static final DateTimeFormatter DATE_ONLY = DateTimeFormatter.ISO_LOCAL_DATE;

    private Alibaba1688PurchaseRules() {}

    public static boolean isReceivedOrCompleted(String status) {
        String s = status == null ? "" : status.trim().toLowerCase(Locale.ROOT);
        if (s.equals("completed")) return true;
        // Require positive forms — avoid matching 未完成 / 未签收
        return s.contains("已完成") || s.contains("已签收");
    }

    public static boolean isDelayed(String expectedArrivalAt, String status, LocalDateTime now) {
        if (isReceivedOrCompleted(status)) return false;
        if (expectedArrivalAt == null || expectedArrivalAt.isBlank()) return false;
        LocalDateTime eta = parseFlexible(expectedArrivalAt);
        return eta != null && eta.isBefore(now);
    }

    public static boolean isStockout(String statusText, Collection<String> keywords) {
        String text = statusText == null ? "" : statusText;
        if (keywords == null) return false;
        for (String k : keywords) {
            if (k != null && !k.isBlank() && text.contains(k)) return true;
        }
        return false;
    }

    public static LocalDateTime parseFlexible(String raw) {
        String value = raw == null ? "" : raw.trim();
        if (value.isEmpty()) return null;
        for (DateTimeFormatter formatter : DATE_TIMES) {
            try {
                return LocalDateTime.parse(value, formatter);
            } catch (DateTimeParseException ignored) {
                // try next
            }
        }
        try {
            return LocalDate.parse(value, DATE_ONLY).atStartOfDay();
        } catch (DateTimeParseException ignored) {
            return null;
        }
    }
}
