package com.crosshub.monitor;

import com.crosshub.monitor.util.PddMonitorUrlValidator;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PddMonitorUrlValidatorTest {

    @Test
    void isValidPddMonitorUrl_acceptsMallPagesWithMallId() {
        assertTrue(PddMonitorUrlValidator.isValidPddMonitorUrl(
                "https://mobile.yangkeduo.com/mall_page.html?mall_id=123456"));
        assertTrue(PddMonitorUrlValidator.isValidPddMonitorUrl(
                "https://yangkeduo.com/mall_page.html?mall_id=abc"));
    }

    @Test
    void isValidPddMonitorUrl_acceptsGoodsPagesWithGoodsId() {
        assertTrue(PddMonitorUrlValidator.isValidPddMonitorUrl(
                "https://mobile.yangkeduo.com/goods.html?goods_id=987&mall_id=123"));
    }

    @Test
    void isValidPddMonitorUrl_rejectsUnsupportedAndIncompleteUrls() {
        assertFalse(PddMonitorUrlValidator.isValidPddMonitorUrl(
                "https://mobile.yangkeduo.com/mall_page.html"));
        assertFalse(PddMonitorUrlValidator.isValidPddMonitorUrl(
                "https://example.com/goods.html?goods_id=987"));
        assertFalse(PddMonitorUrlValidator.isValidPddMonitorUrl("not-a-url"));
    }

    @Test
    void canonicalize_normalizesMobileHostAndKeepsRequiredIds() {
        assertEquals(
                "https://mobile.yangkeduo.com/goods.html?goods_id=987&mall_id=123",
                PddMonitorUrlValidator.canonicalize("https://yangkeduo.com/goods.html?mall_id=123&goods_id=987")
        );
    }
}
