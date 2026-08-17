package com.crosshub.alibaba1688.service;

import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class Alibaba1688PurchaseRulesTest {
    @Test
    void delayedWhenEtaPastAndNotCompleted() {
        assertTrue(Alibaba1688PurchaseRules.isDelayed(
                "2026-08-01 00:00:00", "pending_receive",
                LocalDateTime.of(2026, 8, 17, 12, 0)));
    }

    @Test
    void notDelayedWhenCompleted() {
        assertFalse(Alibaba1688PurchaseRules.isDelayed(
                "2026-08-01 00:00:00", "completed",
                LocalDateTime.of(2026, 8, 17, 12, 0)));
    }

    @Test
    void stockoutMatchesKeyword() {
        assertTrue(Alibaba1688PurchaseRules.isStockout("供应商缺货待补", List.of("缺货")));
        assertFalse(Alibaba1688PurchaseRules.isStockout("已发货", List.of("缺货")));
    }

    @Test
    void notCompletedWhenPrefixWei() {
        assertFalse(Alibaba1688PurchaseRules.isReceivedOrCompleted("未完成"));
        assertFalse(Alibaba1688PurchaseRules.isReceivedOrCompleted("未签收"));
        assertTrue(Alibaba1688PurchaseRules.isReceivedOrCompleted("已完成"));
        assertTrue(Alibaba1688PurchaseRules.isReceivedOrCompleted("已签收"));
    }
}
