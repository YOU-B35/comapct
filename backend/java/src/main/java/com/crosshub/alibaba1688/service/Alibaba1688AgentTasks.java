package com.crosshub.alibaba1688.service;

import java.util.Set;

public final class Alibaba1688AgentTasks {
    public static final String SESSION_PROBE = "1688_session_probe";
    public static final String LOGIN_OPEN = "1688_login_open";

    public static final Set<String> BROWSER_BUSY_TYPES = Set.of(SESSION_PROBE, LOGIN_OPEN);

    private Alibaba1688AgentTasks() {
    }
}
