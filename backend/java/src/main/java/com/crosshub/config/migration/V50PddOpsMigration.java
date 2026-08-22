package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * 拼多多运营数据表迁移。
 *
 * <p>对齐抖音 V27 接入模式：Agent + Playwright 爬取卖家后台，回写 ingest 接口入库。
 * 数据 scope：今日/分时段订单、商品列表、经营罗盘。
 *
 * <p>XHR 契约待账号到位 probe 后填入 Python {@code pdd_tasks.py}，本迁移仅建表骨架。
 */
@Component
@Order(50)
public class V50PddOpsMigration {
    private static final Logger log = LoggerFactory.getLogger(V50PddOpsMigration.class);

    private final JdbcTemplate jdbc;

    public V50PddOpsMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        // 订单（按时间段分：report_day + date_window，对齐用户需求）
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS pdd_order (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  external_shop_id TEXT,
                  report_day TEXT NOT NULL,
                  date_window TEXT NOT NULL DEFAULT 'today',
                  order_no TEXT NOT NULL,
                  product_name TEXT,
                  channel TEXT,
                  sku TEXT,
                  quantity INTEGER DEFAULT 1,
                  amount REAL,
                  currency TEXT DEFAULT 'CNY',
                  status TEXT,
                  ship_deadline TEXT,
                  ordered_at TEXT,
                  order_key TEXT NOT NULL,
                  raw_json TEXT,
                  created_at TEXT,
                  updated_at TEXT
                )
                """);
        jdbc.execute("CREATE UNIQUE INDEX IF NOT EXISTS uk_pdd_order_key ON pdd_order(order_key)");
        jdbc.execute(
                "CREATE INDEX IF NOT EXISTS idx_pdd_order_window ON pdd_order(tenant_id, store_id, report_day, date_window)"
        );

        // 商品
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS pdd_product (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  external_shop_id TEXT,
                  product_id TEXT NOT NULL,
                  product_name TEXT,
                  status TEXT,
                  status_label TEXT,
                  price REAL,
                  stock REAL,
                  sales REAL,
                  main_image TEXT,
                  category TEXT,
                  article_no TEXT,
                  sku_count INTEGER DEFAULT 0,
                  skus_json TEXT,
                  raw_json TEXT,
                  product_key TEXT NOT NULL,
                  synced_at TEXT,
                  created_at TEXT,
                  updated_at TEXT
                )
                """);
        jdbc.execute("CREATE UNIQUE INDEX IF NOT EXISTS uk_pdd_product_key ON pdd_product(product_key)");

        // 经营罗盘快照
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS pdd_compass_snapshot (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  date_type INTEGER NOT NULL,
                  date_window TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  raw_json TEXT,
                  synced_at TEXT,
                  created_at TEXT,
                  updated_at TEXT
                )
                """);
        jdbc.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uk_pdd_compass ON pdd_compass_snapshot(tenant_id, store_id, date_window)"
        );

        // 同步任务
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS pdd_sync_job (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  scope TEXT NOT NULL,
                  status TEXT NOT NULL,
                  store_id TEXT,
                  agent_task_id TEXT,
                  orders_count INTEGER DEFAULT 0,
                  products_count INTEGER DEFAULT 0,
                  compass_count INTEGER DEFAULT 0,
                  error_code TEXT,
                  error_message TEXT,
                  message TEXT,
                  created_at TEXT,
                  updated_at TEXT,
                  finished_at TEXT
                )
                """);
        jdbc.execute(
                "CREATE INDEX IF NOT EXISTS idx_pdd_sync_job_tenant ON pdd_sync_job(tenant_id, created_at)"
        );

        // 会话快照（登录态/店铺信息）
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS pdd_session_snapshot (
                  tenant_id INTEGER PRIMARY KEY,
                  payload_json TEXT NOT NULL,
                  updated_at TEXT
                )
                """);

        log.info("V50PddOpsMigration applied");
    }
}
