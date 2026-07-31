package com.crosshub.common;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class TenantCrawlCooldownServiceTest {

    @Test
    void cooldownMs_forMonitorScope_is30Minutes() {
        assertEquals(30L * 60 * 1000, TenantCrawlCooldownService.cooldownMsForScope("monitor:mt_x"));
        assertEquals(TenantCrawlCooldownService.COOLDOWN_MS, TenantCrawlCooldownService.cooldownMsForScope("platform"));
    }
}
