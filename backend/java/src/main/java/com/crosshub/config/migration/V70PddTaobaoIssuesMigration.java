package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * 拼多多/淘宝 工单预警(issues)表迁移。
 *
 * <p>对齐抖音 V27 的 douyin_issue 表结构，补齐 pdd/taobao 两个平台缺失的 issues 业务线数据表。
 * 前端 issues 同步/解决工单、Agent 回调 ingest 均依赖此表。
 */
@Component
@Order(70)
public class V70PddTaobaoIssuesMigration {
    private static final Logger log = LoggerFactory.getLogger(V70PddTaobaoIssuesMigration.class);

    private final JdbcTemplate jdbc;

    public V70PddTaobaoIssuesMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        // 拼多多工单预警表（对齐 douyin_issue）
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS pdd_issue (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  type TEXT,
                  type_label TEXT,
                  sku TEXT,
                  product_name TEXT,
                  product_image TEXT,
                  detail TEXT,
                  priority TEXT,
                  resolved INTEGER DEFAULT 0,
                  reported_at TEXT,
                  resolved_at TEXT,
                  note TEXT,
                  external_id TEXT,
                  source TEXT,
                  created_at TEXT,
                  updated_at TEXT
                )
                """);
        jdbc.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uk_pdd_issue ON pdd_issue(tenant_id, store_id, external_id)"
        );

        // 淘宝/天猫工单预警表（对齐 douyin_issue）
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS taobao_issue (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  type TEXT,
                  type_label TEXT,
                  sku TEXT,
                  product_name TEXT,
                  product_image TEXT,
                  detail TEXT,
                  priority TEXT,
                  resolved INTEGER DEFAULT 0,
                  reported_at TEXT,
                  resolved_at TEXT,
                  note TEXT,
                  external_id TEXT,
                  source TEXT,
                  created_at TEXT,
                  updated_at TEXT
                )
                """);
        jdbc.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uk_taobao_issue ON taobao_issue(tenant_id, store_id, external_id)"
        );

        log.info("V70 pdd/taobao issues tables migration completed");
    }
}
