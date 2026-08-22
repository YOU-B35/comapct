package com.crosshub.taobao.service;

import java.util.Set;

/**
 * 淘宝/天猫 Agent 任务类型常量。对齐抖音 {@code DouyinAgentTasks} / 拼多多 {@code PddAgentTasks} 模式：
 * Agent 拉取这些 task_type 后，调用 Python {@code taobao_tasks.py} 执行浏览器任务。
 */
public final class TaobaoAgentTasks {
    public static final String SESSION_PROBE = "taobao_session_probe";
    public static final String LOGIN_OPEN = "taobao_login_open";
    public static final String SYNC = "taobao_sync";
    public static final String PRODUCTS_SYNC = "taobao_products_sync";
    public static final String ISSUES_SYNC = "taobao_issues_sync";

    /** 占用浏览器 profile 的任务类型集合（用于互斥与 busy 判定） */
    public static final Set<String> BROWSER_BUSY_TYPES = Set.of(
            SESSION_PROBE, LOGIN_OPEN, SYNC, PRODUCTS_SYNC, ISSUES_SYNC
    );

    private TaobaoAgentTasks() {
    }
}
