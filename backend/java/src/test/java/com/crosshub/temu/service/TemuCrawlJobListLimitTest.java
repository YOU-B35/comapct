package com.crosshub.temu.service;

import com.crosshub.temu.service.impl.TemuCrawlServiceImpl;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class TemuCrawlJobListLimitTest {
    @Test
    void clampLimit() {
        assertEquals(20, TemuCrawlServiceImpl.clampJobListLimit(null));
        assertEquals(20, TemuCrawlServiceImpl.clampJobListLimit(0));
        assertEquals(1, TemuCrawlServiceImpl.clampJobListLimit(1));
        assertEquals(60, TemuCrawlServiceImpl.clampJobListLimit(999));
    }
}
