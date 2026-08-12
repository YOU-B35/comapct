package com.crosshub.aliexpress.service;

import com.crosshub.aliexpress.service.impl.AliExpressCrawlServiceImpl;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class AliExpressCrawlJobListLimitTest {
    @Test
    void clampLimit() {
        assertEquals(20, AliExpressCrawlServiceImpl.clampJobListLimit(null));
        assertEquals(20, AliExpressCrawlServiceImpl.clampJobListLimit(0));
        assertEquals(1, AliExpressCrawlServiceImpl.clampJobListLimit(1));
        assertEquals(60, AliExpressCrawlServiceImpl.clampJobListLimit(999));
    }
}
