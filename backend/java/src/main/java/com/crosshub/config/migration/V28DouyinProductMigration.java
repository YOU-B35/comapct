package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(28)
public class V28DouyinProductMigration {
    private static final Logger log = LoggerFactory.getLogger(V28DouyinProductMigration.class);

    private final JdbcTemplate jdbc;

    public V28DouyinProductMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS douyin_product (
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
                  sku_count INTEGER DEFAULT 0,
                  skus_json TEXT,
                  raw_json TEXT,
                  product_key TEXT NOT NULL,
                  synced_at TEXT,
                  created_at TEXT,
                  updated_at TEXT
                )
                """);
        jdbc.execute("CREATE UNIQUE INDEX IF NOT EXISTS uk_douyin_product_key ON douyin_product(product_key)");
        jdbc.execute(
                "CREATE INDEX IF NOT EXISTS idx_douyin_product_tenant_store ON douyin_product(tenant_id, store_id)"
        );

        addColumnIfMissing("douyin_sync_job", "products_count", "INTEGER NOT NULL DEFAULT 0");
        log.info("V28 douyin_product migration applied");
    }

    private void addColumnIfMissing(String table, String column, String ddlType) {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(1) FROM pragma_table_info(?) WHERE name = ?",
                Integer.class,
                table,
                column
        );
        if (count != null && count > 0) {
            return;
        }
        jdbc.execute("ALTER TABLE " + table + " ADD COLUMN " + column + " " + ddlType);
    }
}
