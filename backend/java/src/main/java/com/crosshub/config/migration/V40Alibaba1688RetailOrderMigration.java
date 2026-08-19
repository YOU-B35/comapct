package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(40)
public class V40Alibaba1688RetailOrderMigration {
    private static final Logger log = LoggerFactory.getLogger(V40Alibaba1688RetailOrderMigration.class);

    private final JdbcTemplate jdbc;

    public V40Alibaba1688RetailOrderMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS alibaba1688_order (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  order_no TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT '',
                  paid_amount TEXT NOT NULL DEFAULT '0',
                  refunded_amount TEXT NOT NULL DEFAULT '0',
                  paid_at TEXT DEFAULT '',
                  refunded_at TEXT DEFAULT '',
                  created_platform_at TEXT DEFAULT '',
                  updated_platform_at TEXT DEFAULT '',
                  buyer_masked TEXT DEFAULT '',
                  raw_json TEXT DEFAULT '',
                  synced_at TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE (tenant_id, store_id, order_no)
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS alibaba1688_order_item (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  order_no TEXT NOT NULL,
                  line_id TEXT NOT NULL,
                  offer_id TEXT DEFAULT '',
                  sku_id TEXT DEFAULT '',
                  sku_text TEXT DEFAULT '',
                  product_name TEXT DEFAULT '',
                  quantity TEXT NOT NULL DEFAULT '0',
                  paid_amount TEXT NOT NULL DEFAULT '0',
                  refunded_amount TEXT NOT NULL DEFAULT '0',
                  image_url TEXT DEFAULT '',
                  raw_json TEXT DEFAULT '',
                  UNIQUE (tenant_id, store_id, order_no, line_id)
                )
                """);
        jdbc.execute("""
                CREATE INDEX IF NOT EXISTS idx_a1688_order_paid_at
                ON alibaba1688_order(tenant_id, store_id, paid_at)
                """);
        jdbc.execute("""
                CREATE INDEX IF NOT EXISTS idx_a1688_order_refunded_at
                ON alibaba1688_order(tenant_id, store_id, refunded_at)
                """);
        log.info("V40 alibaba1688_order/alibaba1688_order_item migration applied");
    }
}
