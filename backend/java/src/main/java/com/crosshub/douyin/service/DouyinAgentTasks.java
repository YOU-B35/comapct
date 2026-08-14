package com.crosshub.douyin.service;

import java.util.Set;

public final class DouyinAgentTasks {
    public static final String SESSION_PROBE = "douyin_session_probe";
    public static final String LOGIN_OPEN = "douyin_login_open";
    public static final String SYNC = "douyin_sync";
    public static final String PRODUCTS_SYNC = "douyin_products_sync";

    public static final Set<String> BROWSER_BUSY_TYPES = Set.of(
            SESSION_PROBE, LOGIN_OPEN, SYNC, PRODUCTS_SYNC
    );

    private DouyinAgentTasks() {
    }
}
