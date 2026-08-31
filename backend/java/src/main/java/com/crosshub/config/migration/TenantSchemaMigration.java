package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.event.EventListener;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.crosshub.security.PasswordService;

import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Component
public class TenantSchemaMigration {
    private static final Logger log = LoggerFactory.getLogger(TenantSchemaMigration.class);

    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;
    private final PasswordService passwordService;
    private final boolean demoSeedEnabled;

    public TenantSchemaMigration(
            JdbcTemplate jdbc,
            ObjectMapper objectMapper,
            PasswordService passwordService,
            @Value("${crosshub.demo-seed.enabled:true}") boolean demoSeedEnabled
    ) {
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
        this.passwordService = passwordService;
        this.demoSeedEnabled = demoSeedEnabled;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        createTables();
        addColumnIfMissing("app_user", "tenant_id", "INTEGER");
        addColumnIfMissing("app_user", "job_title", "TEXT NOT NULL DEFAULT ''");
        addColumnIfMissing("app_user", "phone", "TEXT NOT NULL DEFAULT ''");
        addColumnIfMissing("app_user", "other_role", "TEXT NOT NULL DEFAULT ''");
        addColumnIfMissing("app_user", "status", "TEXT NOT NULL DEFAULT 'active'");
        addColumnIfMissing("app_user", "created_at", "TEXT NOT NULL DEFAULT ''");
        addColumnIfMissing("temu_shop", "tenant_id", "INTEGER NOT NULL DEFAULT 1");
        addColumnIfMissing("temu_sale", "tenant_id", "INTEGER NOT NULL DEFAULT 1");
        addColumnIfMissing("warehouse_order", "warehouse_id", "TEXT NOT NULL DEFAULT ''");
        addColumnIfMissing("warehouse_order", "warehouse_name", "TEXT NOT NULL DEFAULT ''");
        ensureWarehouseOrderIndexes();
        if (demoSeedEnabled) {
            seedTenant();
        }
        backfillTenantIds();
        upgradeLegacyUserPasswords();
        if (demoSeedEnabled) {
            seedWarehouseSites();
            seedWarehouseUsers();
            seedUserWarehouseScopes();
        }
        backfillDtcPlatformScope();
        backfillOrderWarehouses();
        seedMenus();
        seedTenantFeatures();
        if (demoSeedEnabled) {
            seedUserScopes();
            seedWarehouseOrders();
        }
        log.info("Tenant schema migration completed");
    }

    private void createTables() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS tenant (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  code TEXT NOT NULL UNIQUE,
                  status TEXT NOT NULL DEFAULT 'active'
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS sys_menu (
                  code TEXT PRIMARY KEY,
                  parent_code TEXT,
                  portal TEXT NOT NULL,
                  platform TEXT,
                  path TEXT NOT NULL,
                  label TEXT NOT NULL,
                  menu_type TEXT NOT NULL,
                  sort_order INTEGER NOT NULL DEFAULT 0
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS tenant_feature (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  tenant_id INTEGER NOT NULL,
                  feature_code TEXT NOT NULL,
                  enabled INTEGER NOT NULL DEFAULT 1,
                  UNIQUE (tenant_id, feature_code)
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS user_platform_scope (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  tenant_id INTEGER NOT NULL,
                  user_id INTEGER NOT NULL,
                  platform TEXT NOT NULL,
                  UNIQUE (tenant_id, user_id, platform)
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS user_shop_scope (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  tenant_id INTEGER NOT NULL,
                  user_id INTEGER NOT NULL,
                  platform TEXT NOT NULL,
                  shop_id TEXT NOT NULL,
                  UNIQUE (tenant_id, user_id, platform, shop_id)
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS user_menu_grant (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  tenant_id INTEGER NOT NULL,
                  user_id INTEGER NOT NULL,
                  menu_code TEXT NOT NULL,
                  UNIQUE (tenant_id, user_id, menu_code)
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS warehouse_order (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  order_no TEXT NOT NULL,
                  status TEXT NOT NULL,
                  source_type TEXT NOT NULL,
                  source_platform TEXT,
                  source_store_name TEXT,
                  source_label TEXT NOT NULL,
                  b2b_customer_name TEXT,
                  remark TEXT,
                  items_json TEXT NOT NULL,
                  attachments_json TEXT,
                  carton_marks_json TEXT,
                  labels_json TEXT,
                  submitted_by_role TEXT NOT NULL,
                  submitted_by_id TEXT NOT NULL,
                  submitted_by_name TEXT NOT NULL,
                  submitted_at TEXT NOT NULL,
                  warehouse_review_json TEXT,
                  updated_at TEXT NOT NULL
                )
                """);
        jdbc.execute("""
                CREATE INDEX IF NOT EXISTS idx_wh_order_tenant ON warehouse_order (tenant_id)
                """);
        jdbc.execute("""
                CREATE INDEX IF NOT EXISTS idx_wh_order_submitter ON warehouse_order (tenant_id, submitted_by_id)
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS warehouse_site (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  name TEXT NOT NULL,
                  code TEXT NOT NULL,
                  address TEXT,
                  status TEXT NOT NULL DEFAULT 'active',
                  sort_order INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL
                )
                """);
        jdbc.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_wh_site_code ON warehouse_site (tenant_id, code)
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS user_warehouse_scope (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  tenant_id INTEGER NOT NULL,
                  user_id INTEGER NOT NULL,
                  warehouse_id TEXT NOT NULL,
                  UNIQUE (tenant_id, user_id, warehouse_id)
                )
                """);
    }

    private void ensureWarehouseOrderIndexes() {
        jdbc.execute("""
                CREATE INDEX IF NOT EXISTS idx_wh_order_warehouse ON warehouse_order (tenant_id, warehouse_id)
                """);
    }

    private void addColumnIfMissing(String table, String column, String ddl) {
        List<String> cols = jdbc.query(
                "PRAGMA table_info(" + table + ")",
                (rs, rowNum) -> rs.getString("name").toLowerCase(Locale.ROOT)
        );
        if (cols.stream().noneMatch(c -> c.equals(column.toLowerCase(Locale.ROOT)))) {
            jdbc.execute("ALTER TABLE " + table + " ADD COLUMN " + column + " " + ddl);
            log.info("Added column {}.{}", table, column);
        }
    }

    private void seedTenant() {
        jdbc.update("""
                INSERT OR IGNORE INTO tenant (id, name, code, status)
                VALUES (1, '泰州亿拓户外用品有限公司', 'yituo-outdoor', 'active')
                """);
    }

    private void backfillTenantIds() {
        jdbc.update("UPDATE app_user SET tenant_id = 1 WHERE tenant_id IS NULL");
        jdbc.update("UPDATE temu_shop SET tenant_id = 1 WHERE tenant_id IS NULL");
        jdbc.update("UPDATE temu_sale SET tenant_id = 1 WHERE tenant_id IS NULL");
        jdbc.update("""
                UPDATE app_user SET job_title = nickname
                WHERE (job_title IS NULL OR job_title = '')
                  AND role = 'user'
                """);
        jdbc.update("""
                UPDATE app_user SET job_title = '企业管理员'
                WHERE (job_title IS NULL OR job_title = '') AND role = 'admin'
                """);
        jdbc.update("""
                UPDATE app_user SET enterprise = (SELECT name FROM tenant WHERE id = app_user.tenant_id)
                WHERE tenant_id IS NOT NULL
                """);
        jdbc.update("""
                UPDATE app_user SET status = 'active'
                WHERE status IS NULL OR status = ''
                """);
        jdbc.update("""
                UPDATE app_user SET created_at = datetime('now', 'localtime')
                WHERE (created_at IS NULL OR created_at = '') AND role = 'user'
                """);
    }

    private void seedMenus() {
        jdbc.update("DELETE FROM sys_menu WHERE code = 'warehouse.orders'");
        jdbc.update("DELETE FROM sys_menu WHERE code IN ('warehouse.settings', 'warehouse.employees')");
        List<Object[]> rows = Arrays.asList(
                menu("boss.dashboard", null, "boss", null, "/boss/dashboard", "运营总览", "admin", 10),
                menu("boss.tasks", null, "boss", null, "/boss/tasks", "任务分配", "admin", 20),
                menu("boss.warehouse", null, "boss", null, "/boss/warehouse-orders", "仓库下单", "admin", 25),
                menu("boss.platform.temu", null, "boss", "temu", "/boss/temu", "Temu 运营", "module", 30),
                menu("boss.platform.aliexpress", null, "boss", "aliexpress", "/boss/aliexpress", "AliExpress 运营", "module", 40),
                menu("boss.platform.amazon", null, "boss", "amazon", "/boss/amazon", "Amazon 运营", "module", 50),
                menu("boss.platform.walmart", null, "boss", "walmart", "/boss/walmart", "Walmart 运营", "module", 60),
                menu("boss.platform.pdd", null, "boss", "pdd", "/boss/pdd", "拼多多运营", "module", 70),
                menu("boss.platform.taobao", null, "boss", "taobao", "/boss/taobao", "淘宝运营", "module", 75),
                menu("boss.platform.douyin", null, "boss", "douyin", "/boss/douyin", "抖音运营", "module", 80),
                menu("boss.platform.channels", null, "boss", "channels", "/boss/channels", "视频号运营", "module", 90),
                menu("boss.platform.1688", null, "boss", "1688", "/boss/1688", "1688 运营", "module", 100),
                menu("boss.platform.dtc", null, "boss", "dtc", "/boss/dtc", "独立站运营", "module", 110),
                menu("boss.settings", null, "boss", null, "#", "设置", "group", 120),
                menu("boss.employees", "boss.settings", "boss", null, "/boss/employees", "运营绑定", "admin", 121),
                menu("boss.warehouse_sites", "boss.settings", "boss", null, "/boss/warehouse-sites", "仓库设置", "admin", 122),
                menu("boss.warehouse_staff", "boss.settings", "boss", null, "/boss/warehouse-staff", "仓库人员", "admin", 123),
                menu("boss.accounts", "boss.settings", "boss", null, "/boss/accounts", "账户绑定", "admin", 124),
                menu("boss.features", "boss.settings", "boss", null, "/boss/features", "功能开关", "admin", 125),

                menu("employee.dashboard", null, "employee", null, "/employee/dashboard", "我的工作台", "base", 10),
                menu("employee.warehouse", null, "employee", null, "/employee/warehouse-orders", "仓库下单", "module", 85),
                menu("employee.tasks", null, "employee", null, "/employee/tasks", "任务中心", "base", 90),
                menu("employee.ai", null, "employee", null, "/employee/ai", "AI 办公", "base", 100),
                menu("warehouse.pending_review", null, "warehouse", null, "/warehouse/pending-review", "待审核", "base", 10),
                menu("warehouse.pending_shipment", null, "warehouse", null, "/warehouse/pending-shipment", "待发货", "base", 20),
                menu("warehouse.shipped", null, "warehouse", null, "/warehouse/shipped", "已发货", "base", 30),
                menu("warehouse.tasks", null, "warehouse", null, "/warehouse/tasks", "任务中心", "base", 40),
                menu("employee.platform.temu", null, "employee", "temu", "/employee/temu", "Temu 运营", "module", 20),
                menu("employee.platform.aliexpress", null, "employee", "aliexpress", "/employee/aliexpress", "AliExpress 运营", "module", 30),
                menu("employee.platform.amazon", null, "employee", "amazon", "/employee/amazon", "Amazon 运营", "module", 40),
                menu("employee.platform.walmart", null, "employee", "walmart", "/employee/walmart", "Walmart 运营", "module", 50),
                menu("employee.platform.pdd", null, "employee", "pdd", "/employee/pdd", "拼多多运营", "module", 60),
                menu("employee.platform.taobao", null, "employee", "taobao", "/employee/taobao", "淘宝运营", "module", 65),
                menu("employee.platform.douyin", null, "employee", "douyin", "/employee/douyin", "抖音运营", "module", 70),
                menu("employee.platform.channels", null, "employee", "channels", "/employee/channels", "视频号运营", "module", 80),
                menu("employee.platform.1688", null, "employee", "1688", "/employee/1688", "1688 运营", "module", 85),
                menu("employee.platform.dtc", null, "employee", "dtc", "/employee/dtc", "独立站运营", "module", 88)
        );
        for (Object[] row : rows) {
            jdbc.update("""
                    INSERT OR REPLACE INTO sys_menu
                    (code, parent_code, portal, platform, path, label, menu_type, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, row);
        }
    }

    private Object[] menu(String code, String parent, String portal, String platform,
                          String path, String label, String type, int sort) {
        return new Object[]{code, parent, portal, platform, path, label, type, sort};
    }

    private void seedTenantFeatures() {
        List<String> codes = jdbc.query("SELECT code FROM sys_menu", (rs, i) -> rs.getString(1));
        List<Long> tenantIds = jdbc.query("SELECT id FROM tenant", (rs, i) -> rs.getLong(1));
        for (Long tenantId : tenantIds) {
            for (String code : codes) {
                jdbc.update("""
                        INSERT OR IGNORE INTO tenant_feature (tenant_id, feature_code, enabled)
                        VALUES (?, ?, 1)
                        """, tenantId, code);
            }
        }
    }

    private void seedUserScopes() {
        seedPlatformScope("wangyiming@yituo-outdoor.com", "temu");
        seedPlatformScope("liting@yituo-outdoor.com", "temu");
        seedPlatformScope("liuyang@yituo-outdoor.com", "amazon");
        seedShopScopesForUser("wangyiming@yituo-outdoor.com", "temu", 2);
    }

    private void seedShopScopesForUser(String username, String platform, int limit) {
        Long userId = jdbc.query("""
                SELECT id FROM app_user WHERE lower(username) = lower(?) LIMIT 1
                """, rs -> rs.next() ? rs.getLong(1) : null, username);
        if (userId == null || limit <= 0) return;

        List<String> shopIds = jdbc.query(
                "SELECT shop_id FROM temu_shop WHERE tenant_id = 1 ORDER BY shop_id LIMIT ?",
                (rs, rowNum) -> rs.getString(1),
                limit
        );
        for (String shopId : shopIds) {
            jdbc.update("""
                    INSERT OR IGNORE INTO user_shop_scope (tenant_id, user_id, platform, shop_id)
                    VALUES (1, ?, ?, ?)
                    """, userId, platform, shopId);
        }
    }

    private void seedWarehouseSites() {
        insertWarehouseSiteIfMissing("wh_site_tz1", "泰州1号仓", "tz1", "江苏省泰州市海陵区", 10);
        insertWarehouseSiteIfMissing("wh_site_tz_post", "泰州邮政仓", "tz_post", "江苏省泰州市邮政物流园", 20);
        insertWarehouseSiteIfMissing("wh_site_ah", "安徽仓库", "ah", "安徽省合肥市", 30);
    }

    private void insertWarehouseSiteIfMissing(String id, String name, String code, String address, int sortOrder) {
        String existing = jdbc.query("""
                SELECT id FROM warehouse_site WHERE id = ? LIMIT 1
                """, rs -> rs.next() ? rs.getString(1) : null, id);
        if (existing != null) return;
        jdbc.update("""
                INSERT INTO warehouse_site (id, tenant_id, name, code, address, status, sort_order, created_at)
                VALUES (?, 1, ?, ?, ?, 'active', ?, datetime('now', 'localtime'))
                """, id, name, code, address, sortOrder);
    }

    private void seedUserWarehouseScopes() {
        seedWarehouseScopeForUser("warehouse@yituo-outdoor.com", "wh_site_tz1", "wh_site_tz_post");
        seedWarehouseScopeForUser("picker@yituo-outdoor.com", "wh_site_ah");
    }

    private void seedWarehouseScopeForUser(String username, String... warehouseIds) {
        Long userId = userIdByUsername(username);
        if (userId == null) return;
        for (String warehouseId : warehouseIds) {
            jdbc.update("""
                    INSERT OR IGNORE INTO user_warehouse_scope (tenant_id, user_id, warehouse_id)
                    VALUES (1, ?, ?)
                    """, userId, warehouseId);
        }
    }

    private void backfillDtcPlatformScope() {
        List<Long> userIds = jdbc.query("""
                SELECT DISTINCT user_id FROM user_platform_scope
                WHERE tenant_id = 1 AND lower(platform) IN ('shopify', 'wordpress')
                """, (rs, rowNum) -> rs.getLong(1));
        for (Long userId : userIds) {
            jdbc.update("""
                    DELETE FROM user_platform_scope
                    WHERE tenant_id = 1 AND user_id = ? AND lower(platform) IN ('shopify', 'wordpress')
                    """, userId);
            jdbc.update("""
                    INSERT OR IGNORE INTO user_platform_scope (tenant_id, user_id, platform)
                    VALUES (1, ?, 'dtc')
                    """, userId);
        }
    }

    private void backfillOrderWarehouses() {
        jdbc.update("""
                UPDATE warehouse_order
                SET warehouse_id = 'wh_site_tz1', warehouse_name = '泰州1号仓'
                WHERE tenant_id = 1 AND (warehouse_id IS NULL OR warehouse_id = '')
                """);
    }

    private void seedWarehouseUsers() {
        insertUserIfMissing(
                "warehouse@yituo-outdoor.com",
                "Wh@Demo123",
                "张仓管",
                "warehouse",
                "仓库管理员"
        );
        insertUserIfMissing(
                "picker@yituo-outdoor.com",
                "Wh@Demo456",
                "李拣货",
                "warehouse",
                "仓库管理员"
        );
        insertUserIfMissing(
                "liuyang@yituo-outdoor.com",
                "Emp@Demo987",
                "刘洋",
                "user",
                "刘洋"
        );
        jdbc.update("""
                UPDATE app_user SET job_title = '仓库管理员'
                WHERE role = 'warehouse' AND job_title <> '仓库管理员'
                """);
    }

    private void insertUserIfMissing(String username, String password, String nickname,
                                     String role, String jobTitle) {
        Long existing = jdbc.query("""
                SELECT id FROM app_user WHERE lower(username) = lower(?) LIMIT 1
                """, rs -> rs.next() ? rs.getLong(1) : null, username);
        if (existing != null) return;
        jdbc.update("""
                INSERT INTO app_user (username, password, nickname, enterprise, role, tenant_id, job_title, status, created_at)
                VALUES (?, ?, ?, (SELECT name FROM tenant WHERE id = 1), ?, 1, ?, 'active', datetime('now', 'localtime'))
                """, username, passwordService.encode(password), nickname, role, jobTitle);
    }

    private void upgradeLegacyUserPasswords() {
        List<Map<String, Object>> rows = jdbc.queryForList("SELECT id, password FROM app_user");
        for (Map<String, Object> row : rows) {
            Object id = row.get("id");
            String password = row.get("password") == null ? "" : String.valueOf(row.get("password"));
            if (!password.isBlank() && !passwordService.isHashed(password)) {
                jdbc.update("UPDATE app_user SET password = ? WHERE id = ?", passwordService.encode(password), id);
            }
        }
    }

    private void seedWarehouseOrders() {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM warehouse_order WHERE tenant_id = 1",
                Integer.class
        );
        if (count != null && count > 0) return;

        Long bossId = userIdByUsername("admin@crosshub.cn");
        Long wangId = userIdByUsername("wangyiming@yituo-outdoor.com");
        Long liuId = userIdByUsername("liuyang@yituo-outdoor.com");
        Long whId = userIdByUsername("warehouse@yituo-outdoor.com");
        if (bossId == null || wangId == null || whId == null) return;
        String whUserId = String.valueOf(whId);
        if (liuId == null) liuId = wangId;

        insertSeedOrder(buildSeedOrder1(String.valueOf(wangId), whUserId));
        insertSeedOrder(buildSeedOrder2(String.valueOf(bossId), whUserId));
        insertSeedOrder(buildSeedOrder3(String.valueOf(liuId), whUserId));
    }

    private Long userIdByUsername(String username) {
        return jdbc.query("""
                SELECT id FROM app_user WHERE lower(username) = lower(?) LIMIT 1
                """, rs -> rs.next() ? rs.getLong(1) : null, username);
    }

    private void insertSeedOrder(Map<String, Object> order) {
        try {
            jdbc.update("""
                    INSERT OR IGNORE INTO warehouse_order (
                      id, tenant_id, order_no, status, warehouse_id, warehouse_name,
                      source_type, source_platform, source_store_name,
                      source_label, b2b_customer_name, remark, items_json, attachments_json,
                      carton_marks_json, labels_json, submitted_by_role, submitted_by_id,
                      submitted_by_name, submitted_at, warehouse_review_json, updated_at
                    ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    order.get("id"),
                    order.get("orderNo"),
                    order.get("status"),
                    order.get("warehouseId"),
                    order.get("warehouseName"),
                    order.get("sourceType"),
                    order.get("sourcePlatform"),
                    order.get("sourceStoreName"),
                    order.get("sourceLabel"),
                    order.get("b2bCustomerName"),
                    order.get("remark"),
                    objectMapper.writeValueAsString(order.get("items")),
                    objectMapper.writeValueAsString(order.get("attachments")),
                    objectMapper.writeValueAsString(order.get("cartonMarks")),
                    objectMapper.writeValueAsString(order.get("labels")),
                    order.get("submittedByRole"),
                    order.get("submittedById"),
                    order.get("submittedByName"),
                    order.get("submittedAt"),
                    order.get("warehouseReview") == null ? null : objectMapper.writeValueAsString(order.get("warehouseReview")),
                    order.get("updatedAt")
            );
        } catch (Exception ex) {
            log.warn("Failed to seed warehouse order {}: {}", order.get("id"), ex.getMessage());
        }
    }

    private Map<String, Object> buildSeedOrder1(String submitterId, String whUserId) {
        Map<String, Object> review = new LinkedHashMap<>();
        review.put("canShip", true);
        review.put("estimatedShipAt", "2026-06-26");
        review.put("missingMaterials", "");
        review.put("packagingNotes", "需加贴 FBA 标签，外箱缠膜");
        review.put("extraOrderNotes", "");
        review.put("reviewRemark", "库存充足，预计 6/26 下午可出库。");
        review.put("reviewedById", whUserId);
        review.put("reviewedByName", "张仓管");
        review.put("reviewedAt", "2026-06-24 14:30:00");

        Map<String, Object> order = baseSeed("wh_ord_seed_1", "WH20260624001", "pending_shipment");
        order.put("warehouseId", "wh_site_tz1");
        order.put("warehouseName", "泰州1号仓");
        order.put("items", List.of(item("li_1", "户外折叠椅 · 黑色", "YT-CHAIR-BK", 200, "件")));
        order.put("remark", "Temu 爆款补货，请优先安排 WFS 仓出库。");
        order.put("sourceType", "marketplace");
        order.put("sourcePlatform", "temu");
        order.put("sourceStoreName", "亿拓户外旗舰店");
        order.put("sourceLabel", "Temu · 亿拓户外旗舰店");
        order.put("attachments", List.of(file("att_1", "Temu补货清单.xlsx", 48200)));
        order.put("cartonMarks", List.of(file("cm_1", "外箱唛-FBA.pdf", 156000)));
        order.put("labels", List.of(file("lb_1", "FNSKU标签.pdf", 89000)));
        order.put("submittedByRole", "employee");
        order.put("submittedById", submitterId);
        order.put("submittedByName", "王一鸣");
        order.put("submittedAt", "2026-06-24 09:12:00");
        order.put("warehouseReview", review);
        order.put("updatedAt", "2026-06-24 14:30:00");
        return order;
    }

    private Map<String, Object> buildSeedOrder2(String submitterId, String whUserId) {
        Map<String, Object> order = baseSeed("wh_ord_seed_2", "WH20260625002", "pending_review");
        order.put("warehouseId", "wh_site_tz_post");
        order.put("warehouseName", "泰州邮政仓");
        order.put("items", List.of(item("li_3", "定制 LOGO 帆布袋", "B2B-BAG-LOGO", 5000, "件")));
        order.put("remark", "B 端客户「杭州野趣贸易」首批大货，附合同与包装设计稿。");
        order.put("sourceType", "b2b");
        order.put("sourcePlatform", "");
        order.put("sourceStoreName", "");
        order.put("sourceLabel", "B 端 · 杭州野趣贸易");
        order.put("b2bCustomerName", "杭州野趣贸易有限公司");
        order.put("attachments", List.of(
                file("att_2", "采购合同.pdf", 256000),
                file("att_3", "包装设计稿.docx", 128000)
        ));
        order.put("cartonMarks", List.of());
        order.put("labels", List.of());
        order.put("submittedByRole", "boss");
        order.put("submittedById", submitterId);
        order.put("submittedByName", "企业管理员");
        order.put("submittedAt", "2026-06-25 11:18:00");
        order.put("warehouseReview", null);
        order.put("updatedAt", "2026-06-25 11:18:00");
        return order;
    }

    private Map<String, Object> buildSeedOrder3(String submitterId, String whUserId) {
        Map<String, Object> review = new LinkedHashMap<>();
        review.put("canShip", false);
        review.put("estimatedShipAt", "");
        review.put("missingMaterials", "大号外箱库存不足，仅剩 120 箱");
        review.put("packagingNotes", "需追加定制 FBA 标签纸");
        review.put("extraOrderNotes", "已向包材供应商追加订购 1000 箱，预计 6/28 到货");
        review.put("reviewRemark", "暂不可发，缺外箱与标签，已启动追加订货。");
        review.put("reviewedById", whUserId);
        review.put("reviewedByName", "张仓管");
        review.put("reviewedAt", "2026-06-25 16:05:00");

        Map<String, Object> order = baseSeed("wh_ord_seed_3", "WH20260625003", "blocked");
        order.put("warehouseId", "wh_site_ah");
        order.put("warehouseName", "安徽仓库");
        order.put("items", List.of(item("li_4", "Amazon 专用外箱（大号）", "AMZ-BOX-L", 800, "箱")));
        order.put("remark", "Amazon FBA 补货，需按 ASIN 分箱清单出库。");
        order.put("sourceType", "marketplace");
        order.put("sourcePlatform", "amazon");
        order.put("sourceStoreName", "US-Store-01");
        order.put("sourceLabel", "Amazon · US-Store-01");
        order.put("attachments", List.of(file("att_4", "FBA分箱清单.xlsx", 64000)));
        order.put("cartonMarks", List.of());
        order.put("labels", List.of());
        order.put("submittedByRole", "employee");
        order.put("submittedById", submitterId);
        order.put("submittedByName", "刘洋");
        order.put("submittedAt", "2026-06-25 15:38:00");
        order.put("warehouseReview", review);
        order.put("updatedAt", "2026-06-25 16:05:00");
        return order;
    }

    private Map<String, Object> baseSeed(String id, String orderNo, String status) {
        Map<String, Object> order = new LinkedHashMap<>();
        order.put("id", id);
        order.put("orderNo", orderNo);
        order.put("status", status);
        order.put("b2bCustomerName", "");
        return order;
    }

    private Map<String, Object> item(String id, String name, String sku, int qty, String unit) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", id);
        row.put("productName", name);
        row.put("sku", sku);
        row.put("quantity", qty);
        row.put("unit", unit);
        return row;
    }

    private Map<String, Object> file(String id, String name, int size) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", id);
        row.put("name", name);
        row.put("size", size);
        row.put("mime", "");
        row.put("uploadedAt", "2026-06-25 11:20:00");
        return row;
    }

    private void seedPlatformScope(String username, String platform) {
        Long userId = jdbc.query("""
                SELECT id FROM app_user WHERE lower(username) = lower(?) LIMIT 1
                """, rs -> rs.next() ? rs.getLong(1) : null, username);
        if (userId == null) return;
        jdbc.update("""
                INSERT OR IGNORE INTO user_platform_scope (tenant_id, user_id, platform)
                VALUES (1, ?, ?)
                """, userId, platform);
    }
}
