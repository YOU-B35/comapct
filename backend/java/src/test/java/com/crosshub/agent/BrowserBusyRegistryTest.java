package com.crosshub.agent;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class BrowserBusyRegistryTest {
    @Test
    void douyinAndTemuAreDifferentPlatforms() {
        assertEquals("douyin", BrowserBusyRegistry.platformOf("douyin_sync"));
        assertEquals("temu", BrowserBusyRegistry.platformOf("temu_crawl"));
        assertTrue(BrowserBusyRegistry.typesFor("douyin").contains("douyin_login_open"));
        assertTrue(BrowserBusyRegistry.isBusyType("douyin_session_probe"));
    }
}
