package com.crosshub.douyin.service;

import com.crosshub.douyin.entity.DouyinIssue;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

class DouyinIssueUpsertTest {
    @Test
    void ingestDoesNotReopenResolved() {
        DouyinIssue row = new DouyinIssue();
        row.setResolved(1);
        row.setResolvedAt("2026-08-01 10:00:00");
        row.setNote("已处理");
        row.setDetail("旧详情");
        row.setReportedAt("2026-08-01 09:00:00");

        Map<String, Object> incoming = new LinkedHashMap<>();
        incoming.put("type", "violation");
        incoming.put("detail", "新详情");
        incoming.put("priority", "high");
        incoming.put("source", "violation_xhr");

        DouyinIssueUpsert.applyIncoming(row, incoming, "2026-08-14 12:00:00", false);

        assertEquals(1, row.getResolved());
        assertEquals("已处理", row.getNote());
        assertEquals("2026-08-01 10:00:00", row.getResolvedAt());
        assertEquals("新详情", row.getDetail());
        assertEquals("violation", row.getType());
        assertEquals("high", row.getPriority());
        assertEquals("2026-08-01 09:00:00", row.getReportedAt());
    }

    @Test
    void ingestAppliesProductImage() {
        DouyinIssue row = new DouyinIssue();
        Map<String, Object> incoming = Map.of(
                "type", "product",
                "detail", "缺讲解",
                "product_image", "https://cdn.example/cover.jpg"
        );
        DouyinIssueUpsert.applyIncoming(row, incoming, "2026-08-14 12:00:00", true);
        assertEquals("https://cdn.example/cover.jpg", row.getProductImage());
    }

    @Test
    void newRowStartsOpen() {
        DouyinIssue row = new DouyinIssue();
        Map<String, Object> incoming = Map.of(
                "type", "live",
                "detail", "挂车失效",
                "severity", "high"
        );
        DouyinIssueUpsert.applyIncoming(row, incoming, "2026-08-14 12:00:00", true);
        assertEquals(0, row.getResolved());
        assertEquals("high", row.getPriority());
        assertEquals("live", row.getType());
        assertEquals("直播异常", row.getTypeLabel());
    }
}
