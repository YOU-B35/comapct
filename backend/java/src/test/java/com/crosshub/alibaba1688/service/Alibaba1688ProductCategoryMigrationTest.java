package com.crosshub.alibaba1688.service;

import com.crosshub.config.migration.V39Alibaba1688ProductCategoryMigration;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class Alibaba1688ProductCategoryMigrationTest {

    @Test
    void createsCategoryRelationTableWithUniqueMembership() throws Exception {
        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("org.sqlite.JDBC");
        dataSource.setUrl("jdbc:sqlite:file:a1688-category-migration?mode=memory&cache=shared");
        JdbcTemplate jdbc = new JdbcTemplate(dataSource);

        try (var keepAlive = dataSource.getConnection()) {
            V39Alibaba1688ProductCategoryMigration migration =
                    new V39Alibaba1688ProductCategoryMigration(jdbc);

            migration.migrate();
            migration.migrate();

            List<String> columns = jdbc.queryForList(
                    "SELECT name FROM pragma_table_info('alibaba1688_product_category') ORDER BY cid",
                    String.class
            );
            assertEquals(List.of(
                    "id",
                    "tenant_id",
                    "store_id",
                    "offer_id",
                    "category_code",
                    "source_sync_id",
                    "synced_at",
                    "created_at",
                    "updated_at"
            ), columns);

            jdbc.update(
                    """
                    INSERT INTO alibaba1688_product_category (
                      id, tenant_id, store_id, offer_id, category_code,
                      source_sync_id, synced_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    "row-1", 1L, "store-1", "offer-1", "growth_potential",
                    "sync-1", "2026-08-18 18:00:00", "2026-08-18 18:00:00", "2026-08-18 18:00:00"
            );

            assertThrows(Exception.class, () -> jdbc.update(
                    """
                    INSERT INTO alibaba1688_product_category (
                      id, tenant_id, store_id, offer_id, category_code,
                      source_sync_id, synced_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    "row-2", 1L, "store-1", "offer-1", "growth_potential",
                    "sync-2", "2026-08-18 18:01:00", "2026-08-18 18:01:00", "2026-08-18 18:01:00"
            ));

            Integer lookupIndexes = jdbc.queryForObject(
                    """
                    SELECT COUNT(1) FROM sqlite_master
                    WHERE type = 'index'
                      AND tbl_name = 'alibaba1688_product_category'
                      AND name = 'idx_a1688_product_category_lookup'
                    """,
                    Integer.class
            );
            assertEquals(1, lookupIndexes);
        }
    }
}
