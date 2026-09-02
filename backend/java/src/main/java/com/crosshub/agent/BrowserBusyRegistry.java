package com.crosshub.agent;

import com.crosshub.alibaba1688.service.Alibaba1688AgentTasks;
import com.crosshub.douyin.service.DouyinAgentTasks;
import com.crosshub.temu.service.TemuAgentTasks;

import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Maps agent task types to platform browser-busy sets.
 * Same tenant + same platform: at most one busy browser task; cross-platform allowed.
 */
public final class BrowserBusyRegistry {
    public static final String PLATFORM_TEMU = "temu";
    public static final String PLATFORM_DOUYIN = "douyin";
    public static final String PLATFORM_ALIEXPRESS = "aliexpress";
    public static final String PLATFORM_AMAZON = "amazon";
    public static final String PLATFORM_1688 = "1688";

    private static final Map<String, Set<String>> TYPES = Map.of(
            PLATFORM_TEMU, TemuAgentTasks.BROWSER_BUSY_TYPES,
            PLATFORM_DOUYIN, DouyinAgentTasks.BROWSER_BUSY_TYPES,
            PLATFORM_ALIEXPRESS, Set.of(
                    "aliexpress_crawl",
                    "aliexpress_login_open",
                    "aliexpress_session_probe",
                    "aliexpress_violations_sync"
            ),
            PLATFORM_AMAZON, Set.of("amazon_sync", "amazon_write", "amazon_chat", "ziniao_discover", "amazon_ziniao_discover"),
            PLATFORM_1688, Alibaba1688AgentTasks.BROWSER_BUSY_TYPES
    );

    private BrowserBusyRegistry() {
    }

    public static Set<String> typesFor(String platform) {
        if (platform == null || platform.isBlank()) {
            return Set.of();
        }
        return TYPES.getOrDefault(platform.trim().toLowerCase(Locale.ROOT), Set.of());
    }

    public static String platformOf(String taskType) {
        if (taskType == null || taskType.isBlank()) {
            return "";
        }
        String type = taskType.trim();
        for (Map.Entry<String, Set<String>> entry : TYPES.entrySet()) {
            if (entry.getValue().contains(type)) {
                return entry.getKey();
            }
        }
        int idx = type.indexOf('_');
        if (idx > 0) {
            return type.substring(0, idx).toLowerCase(Locale.ROOT);
        }
        return type.toLowerCase(Locale.ROOT);
    }

    public static boolean isBusyType(String taskType) {
        String platform = platformOf(taskType);
        return !platform.isBlank() && typesFor(platform).contains(taskType == null ? "" : taskType.trim());
    }
}
