package com.crosshub.alibaba1688.service;

import java.util.Set;

public final class Alibaba1688AgentTasks {
    public static final String SESSION_PROBE = "1688_session_probe";
    public static final String LOGIN_OPEN = "1688_login_open";
    public static final String PRODUCTS_SYNC = "1688_products_sync";
    public static final String ORDERS_SYNC = "1688_orders_sync";
    public static final String PEER_BESTSELLERS_SYNC = "1688_peer_bestsellers_sync";
    public static final String MONITOR_CRAWL = "1688_monitor_crawl";

    public static final Set<String> BROWSER_BUSY_TYPES = Set.of(
            SESSION_PROBE, LOGIN_OPEN, PRODUCTS_SYNC, ORDERS_SYNC, PEER_BESTSELLERS_SYNC, MONITOR_CRAWL
    );

    private Alibaba1688AgentTasks() {
    }
}
