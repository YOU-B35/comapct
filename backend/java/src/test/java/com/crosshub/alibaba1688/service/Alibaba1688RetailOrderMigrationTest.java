package com.crosshub.alibaba1688.service;

import com.crosshub.config.migration.V40Alibaba1688RetailOrderMigration;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class Alibaba1688RetailOrderMigrationTest {

    @Test
    void createsOrderTablesWithUniqueKeysAndDateIndexes() throws Exception {
        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("org.sqlite.JDBC");
        dataSource.setUrl("jdbc:sqlite:file:a1688-retail-order-migration?mode=memory&cache=shared");
        JdbcTemplate jdbc = new JdbcTemplate(dataSource);

        try (var keepAlive = dataSource.getConnection()) {
            V40Alibaba1688RetailOrderMigration migration =
                    new V40Alibaba1688RetailOrderMigration(jdbc);

            migration.migrate();
            migration.migrate();

            List<String> orderColumns = jdbc.queryForList(
                    "SELECT name FROM pragma_table_info('alibaba1688_order') ORDER BY cid",
                    String.class
            );
            assertEquals(List.of(
                    "id", "tenant_id", "store_id", "order_no", "status",
                    "paid_amount", "refunded_amount", "paid_at", "refunded_at",
                    "created_platform_at", "updated_platform_at", "buyer_masked",
                    "raw_json", "synced_at", "created_at", "updated_at"
            ), orderColumns);

            List<String> itemColumns = jdbc.queryForList(
                    "SELECT name FROM pragma_table_info('alibaba1688_order_item') ORDER BY cid",
                    String.class
            );
            assertEquals(List.of(
                    "id", "tenant_id", "store_id", "order_no", "line_id",
                    "offer_id", "sku_id", "sku_text", "product_name", "quantity",
                    "paid_amount", "refunded_amount", "image_url", "raw_json"
            ), itemColumns);

            jdbc.update(
                    """
                    INSERT INTO alibaba1688_order (
                      id, tenant_id, store_id, order_no, status, paid_amount, refunded_amount,
                      paid_at, refunded_at, created_platform_at, updated_platform_at,
                      buyer_masked, raw_json, synced_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    "row-1", 1L, "store-1", "order-1", "paid", "100", "0",
                    "2026-08-19 10:00:00", "", "2026-08-19 09:00:00", "",
                    "", "", "2026-08-19 10:00:00", "2026-08-19 10:00:00", "2026-08-19 10:00:00"
            );

            assertThrows(Exception.class, () -> jdbc.update(
                    """
                    INSERT INTO alibaba1688_order (
                      id, tenant_id, store_id, order_no, status, paid_amount, refunded_amount,
                      paid_at, refunded_at, created_platform_at, updated_platform_at,
                      buyer_masked, raw_json, synced_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    "row-2", 1L, "store-1", "order-1", "paid", "100", "0",
                    "2026-08-19 10:00:00", "", "2026-08-19 09:00:00", "",
                    "", "", "2026-08-19 10:00:00", "2026-08-19 10:00:00", "2026-08-19 10:00:00"
            ));

            jdbc.update(
                    """
                    INSERT INTO alibaba1688_order_item (
                      id, tenant_id, store_id, order_no, line_id, offer_id, sku_id,
                      sku_text, product_name, quantity, paid_amount, refunded_amount,
                      image_url, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    "item-1", 1L, "store-1", "order-1", "line-1", "offer-1", "sku-1",
                    "默认", "商品A", "2", "100", "0", "", ""
            );

            assertThrows(Exception.class, () -> jdbc.update(
                    """
                    INSERT INTO alibaba1688_order_item (
                      id, tenant_id, store_id, order_no, line_id, offer_id, sku_id,
                      sku_text, product_name, quantity, paid_amount, refunded_amount,
                      image_url, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    "item-2", 1L, "store-1", "order-1", "line-1", "offer-1", "sku-1",
                    "默认", "商品A", "2", "100", "0", "", ""
            ));

            for (String idx : new String[]{"idx_a1688_order_paid_at", "idx_a1688_order_refunded_at"}) {
                Integer count = jdbc.queryForObject(
                        """
                        SELECT COUNT(1) FROM sqlite_master
                        WHERE type = 'index' AND tbl_name = 'alibaba1688_order' AND name = ?
                        """,
                        Integer.class,
                        idx
                );
                assertEquals(1, count, idx);
            }
        }
    }
}
