package com.crosshub.monitor;

import com.crosshub.monitor.util.TemuMonitorUrlValidator;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TemuMonitorUrlValidatorTest {

    @Test
    void isValidTemuMallUrl_acceptsMallPagesWithMallId() {
        assertTrue(TemuMonitorUrlValidator.isValidTemuMallUrl(
                "https://www.temu.com/mall.html?mall_id=3678530852421"));
        assertTrue(TemuMonitorUrlValidator.isValidTemuMallUrl(
                "https://www.temu.com/jp-zh-Hans/mall.html?mall_id=1"));
    }

    @Test
    void isValidTemuMallUrl_rejectsProductAndSearchPages() {
        assertFalse(TemuMonitorUrlValidator.isValidTemuMallUrl(
                "https://www.temu.com/jp-zh-Hans/-fishing-g-601105684074765.html?x=1"));
        assertFalse(TemuMonitorUrlValidator.isValidTemuMallUrl(
                "https://www.temu.com/search_result.html?search_key=lead"));
    }
}
