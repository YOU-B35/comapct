package com.crosshub.alibaba1688.service;

import com.crosshub.config.migration.V40Alibaba1688RetailOrderMigration;
import com.crosshub.config.migration.V41Alibaba1688RetailOrderItemUnitPriceMigration;
import com.crosshub.config.migration.V42Alibaba1688PeerBestsellerMigration;
import com.crosshub.config.migration.V43Alibaba1688PeerBestsellerQualityMigration;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

import java.util.List;
import java.util.Map;
import java.nio.file.Files;
import java.nio.file.Path;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;

class Alibaba1688RetailOpsServiceTest {

    private static Fixture db() throws Exception {
        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("org.sqlite.JDBC");
        Path tmp = Files.createTempFile("a1688-retail-ops-test-", ".db");
        Files.deleteIfExists(tmp);
        dataSource.setUrl("jdbc:sqlite:" + tmp.toAbsolutePath());
        JdbcTemplate jdbc = new JdbcTemplate(dataSource);
        new V40Alibaba1688RetailOrderMigration(jdbc).migrate();
        new V41Alibaba1688RetailOrderItemUnitPriceMigration(jdbc).migrate();
        new V42Alibaba1688PeerBestsellerMigration(jdbc).migrate();
        new V43Alibaba1688PeerBestsellerQualityMigration(jdbc).migrate();
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS alibaba1688_product (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  offer_id TEXT NOT NULL,
                  product_name TEXT DEFAULT '',
                  price TEXT DEFAULT '',
                  stock TEXT DEFAULT '',
                  status TEXT DEFAULT '',
                  image_url TEXT DEFAULT '',
                  product_updated_at TEXT DEFAULT ''
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS agent_task (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER,
                  agent_id TEXT,
                  task_type TEXT,
                  status TEXT,
                  payload_json TEXT,
                  result_json TEXT,
                  error_code TEXT,
                  error_message TEXT,
                  created_at TEXT,
                  started_at TEXT,
                  finished_at TEXT
                )
                """);
        return new Fixture(jdbc, tmp);
    }

    private static void seedProduct(
            Fixture fx,
            String offerId,
            String name,
            String price,
            String stock,
            String status,
            String updatedAt
    ) {
        fx.jdbc.update(
                """
                INSERT INTO alibaba1688_product (
                  id, tenant_id, store_id, offer_id, product_name, price, stock, status, image_url, product_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                "p-" + offerId, 1L, "store-1", offerId, name, price, stock, status, "", updatedAt
        );
    }

    @Test
    void ingestPersistsOrderAndItems() throws Exception {
        Fixture fx = db();
        Map<String, Object> order = Map.of(
                "order", Map.of(
                        "order_no", "O1",
                        "status", "paid",
                        "paid_amount", "5325",
                        "paid_at", "2026-08-19 10:23:13",
                        "created_platform_at", "2026-08-19 10:00:00",
                        "buyer_masked", "永***"
                ),
                "items", List.of(
                        Map.of(
                                "line_id", "L1",
                                "offer_id", "offer-1",
                                "sku_id", "sku-1",
                                "product_name", "商品A",
                                "quantity", "2",
                                "paid_amount", "5325"
                        )
                )
        );
        Map<String, Object> result = fx.service.ingestOrders(1L, Map.of("store_id", "store-1", "orders", List.of(order)));
        assertEquals(1, result.get("orderCount"));
        assertEquals(1, result.get("itemCount"));

        Map<String, Object> row = fx.jdbc.queryForMap(
                "SELECT status, paid_amount, paid_at FROM alibaba1688_order WHERE tenant_id=1 AND store_id='store-1' AND order_no='O1'"
        );
        assertEquals("paid", row.get("status"));
        assertEquals("5325", row.get("paid_amount"));
        assertEquals("2026-08-19 10:23:13", row.get("paid_at"));
        assertEquals(1, fx.jdbc.queryForObject(
                "SELECT COUNT(*) FROM alibaba1688_order_item WHERE order_no='O1'", Integer.class
        ));
    }

    @Test
    void repeatedIngestIsIdempotentAndUpdatesFields() throws Exception {
        Fixture fx = db();
        Map<String, Object> order = Map.of(
                "order", Map.of("order_no", "O2", "status", "paid", "paid_amount", "100", "paid_at", "2026-08-19 10:00:00"),
                "items", List.of(Map.of("line_id", "L1", "offer_id", "offer-1", "quantity", "1", "paid_amount", "100"))
        );
        fx.service.ingestOrders(1L, Map.of("store_id", "store-1", "orders", List.of(order)));
        fx.service.ingestOrders(1L, Map.of("store_id", "store-1", "orders", List.of(order)));

        assertEquals(1, fx.jdbc.queryForObject("SELECT COUNT(*) FROM alibaba1688_order WHERE order_no='O2'", Integer.class));
        assertEquals(1, fx.jdbc.queryForObject("SELECT COUNT(*) FROM alibaba1688_order_item WHERE order_no='O2'", Integer.class));

        // 行数不变，退款字段允许后续更新
        Map<String, Object> updated = Map.of(
                "order", Map.of("order_no", "O2", "status", "completed", "paid_amount", "100", "paid_at", "2026-08-19 10:00:00"),
                "items", List.of(Map.of("line_id", "L1", "offer_id", "offer-1", "quantity", "1", "paid_amount", "100"))
        );
        fx.service.ingestOrders(1L, Map.of("store_id", "store-1", "orders", List.of(updated)));
        assertEquals("completed", fx.jdbc.queryForObject(
                "SELECT status FROM alibaba1688_order WHERE order_no='O2'", String.class
        ));
    }

    @Test
    void refundUpdatesOrderRefundFieldsByOrderNo() throws Exception {
        Fixture fx = db();
        fx.service.ingestOrders(1L, Map.of(
                "store_id", "store-1",
                "orders", List.of(Map.of(
                        "order", Map.of("order_no", "O3", "status", "paid", "paid_amount", "6400", "paid_at", "2026-08-12 18:00:00"),
                        "items", List.of()
                ))
        ));

        Map<String, Object> result = fx.service.ingestOrders(1L, Map.of(
                "store_id", "store-1",
                "orders", List.of(),
                "refunds", List.of(Map.of(
                        "order_no", "O3",
                        "refunded_amount", "6400",
                        "refunded_at", "2026-08-13 14:14:38"
                ))
        ));
        assertEquals(1, result.get("refundCount"));

        Map<String, Object> row = fx.jdbc.queryForMap(
                "SELECT refunded_amount, refunded_at FROM alibaba1688_order WHERE order_no='O3'"
        );
        assertEquals("6400", row.get("refunded_amount"));
        assertEquals("2026-08-13 14:14:38", row.get("refunded_at"));
    }

    @Test
    void refundMatchesPrecisionTruncatedPlatformOrderId() throws Exception {
        Fixture fx = db();
        seedOrder(fx, "store-1", "5127251402284040047", "paid", "6400", "", "2026-08-12 18:00:00", "L1", "offer-1", "1");

        Map<String, Object> result = fx.service.ingestOrders(1L, Map.of(
                "store_id", "store-1",
                "refunds", List.of(Map.of(
                        "order_no", "5127251402284040000", // 平台精度截断：末 4 位归零
                        "refunded_amount", "6400",
                        "refunded_at", "2026-08-13 14:14:38"
                ))
        ));
        assertEquals(1, result.get("refundCount"));
        Map<String, Object> row = fx.jdbc.queryForMap(
                "SELECT refunded_amount, refunded_at FROM alibaba1688_order WHERE order_no='5127251402284040047'"
        );
        assertEquals("6400", row.get("refunded_amount"));
        assertEquals("2026-08-13 14:14:38", row.get("refunded_at"));
    }

    @Test
    void missingOrderNoRefundDoesNotTouchRows() throws Exception {
        Fixture fx = db();
        Map<String, Object> result = fx.service.ingestOrders(1L, Map.of(
                "store_id", "store-1",
                "refunds", List.of(Map.of("order_no", "", "refunded_amount", "1", "refunded_at", "2026-08-13 14:14:38"))
        ));
        assertEquals(0, result.get("refundCount"));
    }

    @Test
    void summaryCountsPaidOrdersOnlyAndAttributedByPaidDate() throws Exception {
        Fixture fx = db();
        seedOrder(fx, "store-1", "O-PAID-1", "paid", "100", "", "2026-08-18 10:00:00", "L1", "offer-1", "2");
        seedOrder(fx, "store-1", "O-PAID-2", "paid", "50", "", "2026-08-19 10:00:00", "L2", "offer-2", "1");
        seedOrder(fx, "store-1", "O-UNPAID", "unpaid", "0", "", "", "L3", "offer-3", "1");
        seedOrder(fx, "store-1", "O-CANCEL", "cancelled", "0", "", "", "L4", "offer-4", "1");

        Map<String, Object> day1 = fx.service.summary(1L, LocalDate.of(2026, 8, 18), LocalDate.of(2026, 8, 18), "store-1");
        assertEquals(0, new BigDecimal("100").compareTo((BigDecimal) day1.get("paid_sales")));
        assertEquals(1, day1.get("paid_order_count"));

        Map<String, Object> both = fx.service.summary(1L, LocalDate.of(2026, 8, 18), LocalDate.of(2026, 8, 19), "store-1");
        assertEquals(0, new BigDecimal("150").compareTo((BigDecimal) both.get("paid_sales")));
        assertEquals(2, both.get("paid_order_count"));
        assertEquals(0, new BigDecimal("75.00").compareTo((BigDecimal) both.get("average_order_value")));
        assertEquals(3, ((Number) both.get("sold_quantity")).intValue());
        assertEquals(2, both.get("sold_product_count"));
    }

    @Test
    void refundSubtractsOnRefundDateWithoutChangingPaidDay() throws Exception {
        Fixture fx = db();
        seedOrder(fx, "store-1", "O-REFUND", "completed", "6400", "6400", "2026-08-12 18:00:00", "L1", "offer-1", "1");
        fx.service.ingestOrders(1L, Map.of(
                "store_id", "store-1",
                "refunds", List.of(Map.of("order_no", "O-REFUND", "refunded_amount", "6400", "refunded_at", "2026-08-13 14:14:38"))
        ));

        Map<String, Object> paidDay = fx.service.summary(1L, LocalDate.of(2026, 8, 12), LocalDate.of(2026, 8, 12), "store-1");
        assertEquals(0, new BigDecimal("6400").compareTo((BigDecimal) paidDay.get("paid_sales")));
        assertEquals(0, new BigDecimal("0").compareTo((BigDecimal) paidDay.get("refund_amount")));

        Map<String, Object> refundDay = fx.service.summary(1L, LocalDate.of(2026, 8, 13), LocalDate.of(2026, 8, 13), "store-1");
        assertEquals(0, new BigDecimal("6400").compareTo((BigDecimal) refundDay.get("refund_amount")));
        assertEquals(1, refundDay.get("refund_order_count"));
        assertEquals(0, new BigDecimal("-6400").compareTo((BigDecimal) refundDay.get("net_sales")));
    }

    @Test
    void summaryFiltersByStore() throws Exception {
        Fixture fx = db();
        seedOrder(fx, "store-1", "O-A", "paid", "100", "", "2026-08-18 10:00:00", "L1", "offer-1", "1");
        seedOrder(fx, "store-2", "O-B", "paid", "999", "", "2026-08-18 10:00:00", "L2", "offer-2", "1");

        Map<String, Object> store1 = fx.service.summary(1L, LocalDate.of(2026, 8, 18), LocalDate.of(2026, 8, 18), "store-1");
        Map<String, Object> all = fx.service.summary(1L, LocalDate.of(2026, 8, 18), LocalDate.of(2026, 8, 18), "");
        assertEquals(0, new BigDecimal("100").compareTo((BigDecimal) store1.get("paid_sales")));
        assertEquals(0, new BigDecimal("1099").compareTo((BigDecimal) all.get("paid_sales")));
    }

    @Test
    void summaryComparisonUsesPreviousEqualLengthWindow() throws Exception {
        Fixture fx = db();
        seedOrder(fx, "store-1", "O-CUR", "paid", "300", "", "2026-08-19 10:00:00", "L1", "offer-1", "1");
        seedOrder(fx, "store-1", "O-PREV", "paid", "100", "", "2026-08-16 10:00:00", "L2", "offer-2", "1");

        Map<String, Object> summary = fx.service.summary(1L, LocalDate.of(2026, 8, 18), LocalDate.of(2026, 8, 19), "store-1");
        @SuppressWarnings("unchecked")
        Map<String, Object> comparison = (Map<String, Object>) summary.get("comparison");
        assertEquals(0, new BigDecimal("100").compareTo((BigDecimal) comparison.get("paid_sales")));
    }

    @Test
    void trendReturnsDailyRowsWithNetSales() throws Exception {
        Fixture fx = db();
        seedOrder(fx, "store-1", "O-T1", "paid", "100", "", "2026-08-18 10:00:00", "L1", "offer-1", "1");
        seedOrder(fx, "store-1", "O-T2", "paid", "50", "20", "2026-08-19 10:00:00", "L2", "offer-2", "1");
        fx.service.ingestOrders(1L, Map.of(
                "store_id", "store-1",
                "refunds", List.of(Map.of("order_no", "O-T2", "refunded_amount", "20", "refunded_at", "2026-08-19 12:00:00"))
        ));

        List<Map<String, Object>> trend = fx.service.trend(1L, LocalDate.of(2026, 8, 18), LocalDate.of(2026, 8, 19), "store-1");
        assertEquals(2, trend.size());
        Map<String, Object> day1 = trend.get(0);
        assertEquals("2026-08-18", day1.get("date"));
        assertEquals(0, new BigDecimal("100").compareTo((BigDecimal) day1.get("paid_sales")));
        Map<String, Object> day2 = trend.get(1);
        assertEquals(0, new BigDecimal("50").compareTo((BigDecimal) day2.get("paid_sales")));
        assertEquals(0, new BigDecimal("20").compareTo((BigDecimal) day2.get("refund_amount")));
        assertEquals(0, new BigDecimal("30.0").compareTo((BigDecimal) day2.get("net_sales")));
    }

    @Test
    void listOrdersReturnsLineRowsWithFiltersAndPagination() throws Exception {
        Fixture fx = db();
        fx.service.ingestOrders(1L, Map.of(
                "store_id", "store-1",
                "orders", List.of(Map.of(
                        "order", Map.of(
                                "order_no", "O-L1",
                                "status", "paid",
                                "paid_amount", "100",
                                "paid_at", "2026-08-18 10:00:00"
                        ),
                        "items", List.of(
                                Map.of("line_id", "L1", "offer_id", "offer-1", "quantity", "2", "paid_amount", "60"),
                                Map.of("line_id", "L2", "offer_id", "offer-2", "quantity", "1", "paid_amount", "40")
                        )
                ))
        ));
        seedOrder(fx, "store-1", "O-L2", "completed", "50", "", "2026-08-19 10:00:00", "L3", "offer-3", "1");

        Map<String, Object> all = fx.service.listOrders(
                1L, LocalDate.of(2026, 8, 18), LocalDate.of(2026, 8, 19), "", "", "store-1", 1, 20);
        assertEquals(3, all.get("total"));
        assertEquals(3, ((List<?>) all.get("items")).size());

        Map<String, Object> filtered = fx.service.listOrders(
                1L, LocalDate.of(2026, 8, 18), LocalDate.of(2026, 8, 18), "paid", "", "store-1", 1, 20);
        assertEquals(2, filtered.get("total"));

        Map<String, Object> paged = fx.service.listOrders(
                1L, LocalDate.of(2026, 8, 18), LocalDate.of(2026, 8, 19), "", "", "store-1", 1, 2);
        assertEquals(3, paged.get("total"));
        assertEquals(2, ((List<?>) paged.get("items")).size());
    }

    @Test
    void listOrdersDateFilterActuallyFilters() throws Exception {
        Fixture fx = db();
        seedOrder(fx, "store-1", "O-D1", "paid", "100", "", "2026-08-19 10:00:00", "L1", "offer-1", "1");
        seedOrder(fx, "store-1", "O-D2", "paid", "50", "", "2026-08-18 10:00:00", "L2", "offer-2", "1");

        Map<String, Object> today = fx.service.listOrders(
                1L, LocalDate.of(2026, 8, 19), LocalDate.of(2026, 8, 19), "", "", "store-1", 1, 20);
        Map<String, Object> week = fx.service.listOrders(
                1L, LocalDate.of(2026, 8, 13), LocalDate.of(2026, 8, 19), "", "", "store-1", 1, 20);
        assertEquals(1, today.get("total"));
        assertEquals(2, week.get("total"));
    }

    @Test
    void bestsellersTiersAndUnitPrice() throws Exception {
        Fixture fx = db();
        seedProduct(fx, "offer-hot", "爆款A", "0.5", "100", "on_sale", "2026-08-10 10:00");
        seedProduct(fx, "offer-mid", "潜力B", "1.2", "50", "on_sale", "2026-08-10 10:00");
        seedProduct(fx, "offer-zero", "无销量C", "3.0", "0", "on_sale", "2026-08-10 10:00");
        String today = "2026-08-19 10:00:00";
        seedOrder(fx, "store-1", "O-H1", "paid", "15", "", today, "L1", "offer-hot", "20");
        seedOrder(fx, "store-1", "O-H2", "paid", "5", "", today, "L2", "offer-hot", "10");
        seedOrder(fx, "store-1", "O-M1", "paid", "12", "", today, "L3", "offer-mid", "12");

        Map<String, Object> result = fx.service.productAnalytics("bestsellers", 1L, "store-1");
        List<Map<String, Object>> items = (List<Map<String, Object>>) result.get("items");
        Map<String, Map<String, Object>> byOffer = new java.util.HashMap<>();
        for (Map<String, Object> item : items) {
            byOffer.put(String.valueOf(item.get("offerId")), item);
        }
        assertEquals("爆款", byOffer.get("offer-hot").get("tier"));
        assertEquals(30.0, ((Number) byOffer.get("offer-hot").get("salesQty")).doubleValue());
        assertEquals("潜力爆款", byOffer.get("offer-mid").get("tier"));
        assertEquals("无销量", byOffer.get("offer-zero").get("tier"));
        assertEquals("0.5", byOffer.get("offer-hot").get("price"));
        assertEquals(3, items.size());
    }

    @Test
    void todayBestsellersOnlyIncludesQuantityAtLeastTen() throws Exception {
        Fixture fx = db();
        seedProduct(fx, "offer-hot", "爆款A", "0.5", "100", "on_sale", "2026-08-10 10:00");
        seedProduct(fx, "offer-low", "低销量B", "1.2", "50", "on_sale", "2026-08-10 10:00");
        String recent = LocalDateTime.now().minusHours(1).format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
        String old = LocalDateTime.now().minusDays(2).format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
        seedOrder(fx, "store-1", "O-1", "paid", "10", "", recent, "L1", "offer-hot", "10");
        seedOrder(fx, "store-1", "O-2", "paid", "5", "", recent, "L2", "offer-low", "5");
        seedOrder(fx, "store-1", "O-3", "paid", "10", "", old, "L3", "offer-hot", "10");

        Map<String, Object> result = fx.service.productAnalytics("today_bestsellers", 1L, "store-1");
        List<Map<String, Object>> items = (List<Map<String, Object>>) result.get("items");
        assertEquals(1, items.size());
        assertEquals("offer-hot", String.valueOf(items.get(0).get("offerId")));
    }

    @Test
    void recentSalesOnlyIncludesProductsListedInLastThreeDays() throws Exception {
        Fixture fx = db();
        seedProduct(fx, "offer-new", "新品A", "0.5", "100", "on_sale", LocalDateTime.now().minusDays(1).format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")));
        seedProduct(fx, "offer-old", "老品B", "1.2", "50", "on_sale", LocalDateTime.now().minusDays(10).format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")));
        String recent = LocalDateTime.now().minusHours(2).format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
        seedOrder(fx, "store-1", "O-N", "paid", "8", "", recent, "L1", "offer-new", "8");

        Map<String, Object> result = fx.service.productAnalytics("recent_sales", 1L, "store-1");
        List<Map<String, Object>> items = (List<Map<String, Object>>) result.get("items");
        assertEquals(1, items.size());
        assertEquals("offer-new", String.valueOf(items.get(0).get("offerId")));
        assertEquals(8.0, ((Number) items.get(0).get("salesQty")).doubleValue());
    }

    @Test
    void syncLogsReturnRecentTasksWithSummary() throws Exception {
        Fixture fx = db();
        fx.jdbc.update(
                """
                INSERT INTO agent_task (
                  id, tenant_id, task_type, status, result_json, error_code, error_message,
                  created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                "agt-1", 1L, "1688_orders_sync", "success",
                "{\"orders_count\":1473,\"items_count\":3020,\"refunds_count\":10}",
                "", "", "2026-08-19 13:23:22", "2026-08-19 13:23:24", "2026-08-19 13:24:34"
        );
        fx.jdbc.update(
                """
                INSERT INTO agent_task (
                  id, tenant_id, task_type, status, result_json, error_code, error_message,
                  created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                "agt-2", 1L, "1688_products_sync", "failed",
                "{}", "A1688_NOT_LOGGED_IN", "1688 未登录",
                "2026-08-19 13:25:00", "2026-08-19 13:25:01", "2026-08-19 13:25:20"
        );

        Map<String, Object> result = fx.service.listSyncLogs(1L, 10);
        List<Map<String, Object>> items = (List<Map<String, Object>>) result.get("items");
        assertEquals(2, items.size());
        Map<String, Object> first = items.get(0);
        assertEquals("agt-2", first.get("taskId"));
        assertEquals("商品同步", first.get("label"));
        assertEquals("failed", first.get("status"));
        assertEquals("A1688_NOT_LOGGED_IN", first.get("errorCode"));
        Map<String, Object> second = items.get(1);
        assertEquals("agt-1", second.get("taskId"));
        assertEquals("订单同步", second.get("label"));
        assertEquals("success", second.get("status"));
        @SuppressWarnings("unchecked")
        Map<String, Object> summary = (Map<String, Object>) second.get("summary");
        assertEquals(1473, summary.get("orders_count"));
    }

    @Test
    void orderItemUnitPriceRoundTripsThroughIngestAndList() throws Exception {
        Fixture fx = db();
        fx.service.ingestOrders(1L, Map.of(
                "store_id", "store-1",
                "orders", List.of(Map.of(
                        "order", Map.of(
                                "order_no", "O-UP",
                                "status", "paid",
                                "paid_amount", "53.25",
                                "paid_at", "2026-08-19 10:00:00"
                        ),
                        "items", List.of(Map.of(
                                "line_id", "L1",
                                "offer_id", "offer-1",
                                "quantity", "45",
                                "paid_amount", "38.25",
                                "unit_price", "0.85"
                        ))
                ))
        ));

        Map<String, Object> result = fx.service.listOrders(
                1L, LocalDate.of(2026, 8, 19), LocalDate.of(2026, 8, 19), "", "", "store-1", 1, 20);
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> items = (List<Map<String, Object>>) result.get("items");
        assertEquals("0.85", items.get(0).get("unitPrice"));
        assertEquals("38.25", items.get(0).get("itemAmount"));
        assertEquals("53.25", items.get(0).get("paidAmount"));
    }

    @Test
    void peerBestsellersReplaceAndPaginateByTen() throws Exception {
        Fixture fx = db();
        List<Map<String, Object>> items = new java.util.ArrayList<>();
        for (int i = 1; i <= 12; i++) {
            items.add(Map.of(
                    "offer_id", "peer-" + i,
                    "shop_name", "店铺" + i,
                    "title", "商品" + i,
                    "price", "1." + i,
                    "sales", i * 100,
                    "sale_text", "已售" + (i * 100) + "+件"
            ));
        }
        Map<String, Object> replaced = fx.service.replacePeerBestsellers(1L, Map.of("items", items));
        assertEquals(12, replaced.get("ingested"));

        Map<String, Object> page1 = fx.service.listPeerBestsellers(1L, 1, 10);
        assertEquals(12, page1.get("total"));
        assertEquals(10, ((List<?>) page1.get("items")).size());
        assertEquals(1200, ((Map<?, ?>) ((List<?>) page1.get("items")).get(0)).get("sales"));

        Map<String, Object> page2 = fx.service.listPeerBestsellers(1L, 2, 10);
        assertEquals(2, ((List<?>) page2.get("items")).size());

        // 替换后旧数据清空
        fx.service.replacePeerBestsellers(1L, Map.of("items", List.of(
                Map.of("offer_id", "peer-new", "shop_name", "新店", "title", "新品", "price", "0.5", "sales", 50, "sale_text", "已售50+件")
        )));
        Map<String, Object> after = fx.service.listPeerBestsellers(1L, 1, 10);
        assertEquals(1, after.get("total"));
        assertEquals("peer-new", ((Map<?, ?>) ((List<?>) after.get("items")).get(0)).get("offerId"));
    }

    @Test
    void peerBestsellerQualityScoreRoundTrips() throws Exception {
        Fixture fx = db();
        fx.service.replacePeerBestsellers(1L, Map.of("items", List.of(
                Map.of(
                        "offer_id", "peer-q",
                        "shop_name", "某店",
                        "title", "某商品",
                        "price", "0.5",
                        "sales", 120,
                        "sale_text", "已售120+件",
                        "quality_score", "复购31.58% · 达标100%"
                )
        )));
        Map<String, Object> result = fx.service.listPeerBestsellers(1L, 1, 10);
        Map<?, ?> item = (Map<?, ?>) ((List<?>) result.get("items")).get(0);
        assertEquals("复购31.58% · 达标100%", item.get("qualityScore"));
    }

    private static void seedOrder(
            Fixture fx,
            String storeId,
            String orderNo,
            String status,
            String paidAmount,
            String refundedAmount,
            String paidAt,
            String lineId,
            String offerId,
            String quantity
    ) {
        fx.service.ingestOrders(1L, Map.of(
                "store_id", storeId,
                "orders", List.of(Map.of(
                        "order", Map.of(
                                "order_no", orderNo,
                                "status", status,
                                "paid_amount", paidAmount,
                                "refunded_amount", refundedAmount,
                                "paid_at", paidAt
                        ),
                        "items", List.of(Map.of(
                                "line_id", lineId,
                                "offer_id", offerId,
                                "quantity", quantity,
                                "paid_amount", paidAmount
                        ))
                ))
        ));
    }

    private record Fixture(JdbcTemplate jdbc, Alibaba1688RetailOpsService service, Path tmp) {
        Fixture(JdbcTemplate jdbc, Path tmp) {
            this(jdbc, new Alibaba1688RetailOpsService(jdbc, new ObjectMapper()), tmp);
        }
    }
}
