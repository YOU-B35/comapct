package com.crosshub.temu.service;

import java.util.Set;

public final class TemuAgentTasks {
    public static final String CRAWL = "temu_crawl";
    public static final String LOGIN_OPEN = "temu_login_open";
    public static final String FRONTEND_LOGIN_OPEN = "temu_frontend_login_open";
    public static final String SESSION_PROBE = "temu_session_probe";
    public static final String COMPETITOR_DISCOVER = "temu_competitor_discover";

    public static final Set<String> BROWSER_BUSY_TYPES = Set.of(
            CRAWL, LOGIN_OPEN, FRONTEND_LOGIN_OPEN, SESSION_PROBE, COMPETITOR_DISCOVER
    );

    private TemuAgentTasks() {
    }
}
