package com.crosshub.pdd.repository;

import com.crosshub.pdd.entity.PddProduct;
import com.crosshub.pdd.entity.PddOrder;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.AutoConfigureTestEntityManager;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.TestPropertySource;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Regression test for the production PDD products ingest bug:
 * deleteByTenantIdAndStoreId (derived delete) queues EntityManager#remove actions that
 * Hibernate executes AFTER queued inserts at flush time, so re-inserting the same
 * product keys violates the unique index uk_pdd_product_key.
 */
@DataJpaTest
@AutoConfigureTestEntityManager
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@TestPropertySource(properties = {
        "spring.datasource.url=jdbc:sqlite:file::memory:?cache=shared",
        "spring.datasource.driver-class-name=org.sqlite.JDBC",
        "spring.jpa.database-platform=org.hibernate.community.dialect.SQLiteDialect",
        "spring.jpa.hibernate.ddl-auto=create-drop",
})
class PddProductReplaceRepositoryTest {

    private static final long TENANT = 5L;
    private static final String STORE = "fdc163b5-e485-4a49-8201-cbc6af8ac72c";

    @Autowired
    private PddProductRepository repository;

    @Autowired
    private PddOrderRepository orderRepository;

    @Autowired
    private JdbcTemplate jdbc;

    @BeforeEach
    void createProdUniqueIndex() {
        // Mirrors V50PddOpsMigration.uk_pdd_product_key in production.
        jdbc.execute("CREATE UNIQUE INDEX IF NOT EXISTS uk_pdd_product_key ON pdd_product(product_key)");
        jdbc.execute("CREATE UNIQUE INDEX IF NOT EXISTS uk_pdd_order_key ON pdd_order(order_key)");
    }

    @Test
    void replaceStoreProductsDeletesOldRowsBeforeInsertingSameKeys() {
        repository.save(product("seed-1", "pdd:old-1"));
        repository.save(product("seed-2", "pdd:old-2"));
        repository.flush();

        // Same flow as PddOpsService.ingestProducts: delete the store's products,
        // then insert the full replacement set (same product keys).
        repository.deleteByTenantIdAndStoreId(TENANT, STORE);
        repository.save(product("new-1", "pdd:old-1"));
        repository.save(product("new-2", "pdd:old-2"));
        repository.flush();

        List<PddProduct> rows = repository.findByTenantIdAndStoreIdOrderByUpdatedAtDesc(TENANT, STORE);
        assertEquals(2, rows.size());
    }

    @Test
    void replaceDayOrdersDeletesOldRowsBeforeInsertingSameKeys() {
        orderRepository.save(order("seed-1", "pdd:o-1", "2026-08-28", "d90"));
        orderRepository.save(order("seed-2", "pdd:o-2", "2026-08-28", "d90"));
        orderRepository.flush();

        // Same flow as PddOpsService.ingestOrders per replace_day.
        orderRepository.deleteByTenantIdAndStoreIdAndReportDay(TENANT, STORE, "2026-08-28");
        orderRepository.save(order("new-1", "pdd:o-1", "2026-08-28", "d90"));
        orderRepository.save(order("new-2", "pdd:o-2", "2026-08-28", "d90"));
        orderRepository.flush();

        List<PddOrder> rows = orderRepository
                .findByTenantIdAndReportDayAndStoreIdOrderByOrderedAtDesc(TENANT, "2026-08-28", STORE);
        assertEquals(2, rows.size());
    }

    private static PddProduct product(String id, String productKey) {
        PddProduct p = new PddProduct();
        p.setId(id);
        p.setTenantId(TENANT);
        p.setStoreId(STORE);
        p.setProductId("pid-" + id);
        p.setProductKey(productKey);
        p.setProductName("P " + id);
        p.setCreatedAt("2026-08-28 12:00:00");
        p.setUpdatedAt("2026-08-28 12:00:00");
        return p;
    }

    private static PddOrder order(String id, String orderKey, String reportDay, String dateWindow) {
        PddOrder o = new PddOrder();
        o.setId(id);
        o.setTenantId(TENANT);
        o.setStoreId(STORE);
        o.setReportDay(reportDay);
        o.setDateWindow(dateWindow);
        o.setOrderNo("no-" + id);
        o.setOrderKey(orderKey);
        o.setCreatedAt("2026-08-28 12:00:00");
        o.setUpdatedAt("2026-08-28 12:00:00");
        return o;
    }
}
