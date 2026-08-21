package com.crosshub.monitor;

import com.crosshub.monitor.util.Alibaba1688MonitorUrlValidator;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class Alibaba1688MonitorUrlValidatorTest {

    @Test
    void canonicalize_acceptsShopAndOfferUrls() {
        assertEquals(
                "https://shop16yx1905b2433.1688.com",
                Alibaba1688MonitorUrlValidator.canonicalize("https://shop16yx1905b2433.1688.com")
        );
        assertEquals(
                "https://detail.1688.com/offer/930671411701.html",
                Alibaba1688MonitorUrlValidator.canonicalize("https://m.1688.com/offer/930671411701.html")
        );
    }

    @Test
    void requireValidForCreate_rejectsUnrelatedUrl() {
        assertThrows(Exception.class, () ->
                Alibaba1688MonitorUrlValidator.requireValidForCreate(
                        "https://www.temu.com/mall.html?mall_id=1",
                        "1688_shop_topn"
                )
        );
    }
}
