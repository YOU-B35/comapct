package com.crosshub.pdd.service;

import java.util.Set;

/**
 * 拼多多 Agent 任务类型常量。对齐抖音 {@code DouyinAgentTasks} 模式：
 * Agent 拉取这些 task_type 后，调用 Python {@code pdd_tasks.py} 执行浏览器任务。
 */
public final class PddAgentTasks {
    public static final String SESSION_PROBE = "pdd_session_probe";
    public static final String LOGIN_OPEN = "pdd_login_open";
    public static final String SYNC = "pdd_sync";
    public static final String PRODUCTS_SYNC = "pdd_products_sync";
    public static final String ISSUES_SYNC = "pdd_issues_sync";

    /** 占用浏览器 profile 的任务类型集合（用于互斥与 busy 判定） */
    public static final Set<String> BROWSER_BUSY_TYPES = Set.of(
            SESSION_PROBE, LOGIN_OPEN, SYNC, PRODUCTS_SYNC, ISSUES_SYNC
    );

    private PddAgentTasks() {
    }
}
