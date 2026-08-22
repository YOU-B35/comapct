package com.crosshub.warehouse.service.impl;

import com.crosshub.warehouse.service.WarehouseOrderService;
import com.crosshub.warehouse.service.WarehouseSiteService;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.crosshub.warehouse.entity.WarehouseSite;
import com.crosshub.tenant.repository.UserMenuGrantRepository;
import com.crosshub.security.AuthContext;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

@Service
public class WarehouseOrderServiceImpl implements WarehouseOrderService {
    private static final DateTimeFormatter DT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final Set<String> VALID_STATUS = Set.of(
            "pending_review", "pending_shipment", "blocked", "shipped", "cancelled"
    );

    private static final Map<String, String> PLATFORM_LABELS = Map.ofEntries(
            Map.entry("temu", "Temu"),
            Map.entry("aliexpress", "AliExpress"),
            Map.entry("amazon", "Amazon"),
            Map.entry("walmart", "Walmart"),
            Map.entry("1688", "1688"),
            Map.entry("pdd", "拼多多"),
            Map.entry("taobao", "淘宝"),
            Map.entry("douyin", "抖音"),
            Map.entry("channels", "视频号"),
            Map.entry("shopify", "Shopify"),
            Map.entry("wordpress", "WordPress"),
            Map.entry("dtc", "独立站")
    );

    private final JdbcTemplate jdbc;
    private final AuthContext authContext;
    private final ObjectMapper objectMapper;
    private final WarehouseSiteService warehouseSiteService;
    private final UserMenuGrantRepository menuGrantRepository;

    public WarehouseOrderServiceImpl(
            JdbcTemplate jdbc,
            AuthContext authContext,
            ObjectMapper objectMapper,
            WarehouseSiteService warehouseSiteService,
            UserMenuGrantRepository menuGrantRepository
    ) {
        this.jdbc = jdbc;
        this.authContext = authContext;
        this.objectMapper = objectMapper;
        this.warehouseSiteService = warehouseSiteService;
        this.menuGrantRepository = menuGrantRepository;
    }

    public Map<String, Object> listOrders() {
        Long tenantId = requireTenant();
        String portal = authContext.portalRole();
        Long userId = authContext.userId();

        List<Map<String, Object>> orders;
        if ("employee".equalsIgnoreCase(portal)) {
            orders = queryOrders(tenantId, String.valueOf(userId), null);
        } else if ("warehouse".equalsIgnoreCase(portal)) {
            List<String> warehouseScope = authContext.warehouseScope();
            orders = queryOrders(tenantId, null, warehouseScope);
        } else {
            orders = queryOrders(tenantId, null, null);
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("orders", orders);
        result.put("stats", stats(orders));
        return result;
    }

    public Map<String, Object> getOrder(String id) {
        Map<String, Object> order = findOrder(requireTenant(), id);
        assertReadable(order);
        return order;
    }

    public Map<String, Object> createOrder(Map<String, Object> payload) {
        requireSubmitterPortal();
        Long tenantId = requireTenant();
        Long userId = authContext.userId();
        requireEmployeeWarehouseGrant(tenantId, userId);
        String portal = authContext.portalRole();

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> items = (List<Map<String, Object>>) payload.get("items");
        if (items == null || items.isEmpty()) {
            throw badRequest("请至少添加一条货品明细");
        }
        for (Map<String, Object> item : items) {
            String name = String.valueOf(item.getOrDefault("productName", "")).trim();
            Number qty = (Number) item.get("quantity");
            if (name.isEmpty() || qty == null || qty.doubleValue() <= 0) {
                throw badRequest("请完善货品名称与数量");
            }
        }

        String sourceType = text(payload.get("sourceType"), "marketplace");
        if ("b2b".equals(sourceType) && text(payload.get("b2bCustomerName"), "").isEmpty()) {
            throw badRequest("请填写 B 端客户名称");
        }
        if ("marketplace".equals(sourceType) && text(payload.get("sourcePlatform"), "").isEmpty()) {
            throw badRequest("请选择电商平台");
        }

        String warehouseId = text(payload.get("warehouseId"), "");
        WarehouseSite site = warehouseSiteService.requireActiveSite(tenantId, warehouseId);

        String now = nowText();
        String id = "wh_ord_" + System.currentTimeMillis() + "_" + randomSuffix();
        String orderNo = nextOrderNo(tenantId);
        String submitterRole = "boss".equalsIgnoreCase(portal) ? "boss" : "employee";
        String submitterName = resolveSubmitterName(userId, submitterRole);
        String sourceOrderRef = text(payload.get("sourceOrderRef"), text(payload.get("source_order_ref"), ""));
        boolean fromPlatformOrder = Boolean.TRUE.equals(payload.get("fromPlatformOrder"))
                || Boolean.TRUE.equals(payload.get("from_platform_order"));

        jdbc.update("""
                INSERT INTO warehouse_order (
                  id, tenant_id, order_no, status, warehouse_id, warehouse_name,
                  source_type, source_platform, source_store_name,
                  source_label, b2b_customer_name, remark, items_json, attachments_json,
                  carton_marks_json, labels_json, submitted_by_role, submitted_by_id,
                  submitted_by_name, submitted_at, warehouse_review_json, updated_at,
                  source_order_ref, from_platform_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                id,
                tenantId,
                orderNo,
                "pending_review",
                site.getId(),
                site.getName(),
                sourceType,
                text(payload.get("sourcePlatform"), ""),
                text(payload.get("sourceStoreName"), ""),
                buildSourceLabel(payload),
                text(payload.get("b2bCustomerName"), ""),
                text(payload.get("remark"), ""),
                writeJson(normalizeItems(items)),
                writeJson(normalizeFiles(payload.get("attachments"), "att")),
                writeJson(normalizeFiles(payload.get("cartonMarks"), "cm")),
                writeJson(normalizeFiles(payload.get("labels"), "lb")),
                submitterRole,
                String.valueOf(userId),
                submitterName,
                now,
                null,
                now,
                sourceOrderRef,
                fromPlatformOrder ? 1 : 0
        );

        return findOrder(tenantId, id);
    }

    public Map<String, Object> createFromPlatformOrder(Map<String, Object> payload) {
        String sourceOrderRef = text(payload.get("sourceOrderRef"), text(payload.get("source_order_ref"), ""));
        if (sourceOrderRef.isBlank()) {
            throw badRequest("缺少平台订单引用");
        }
        Long tenantId = requireTenant();
        List<Map<String, Object>> existing = jdbc.query(
                """
                SELECT id FROM warehouse_order
                WHERE tenant_id = ? AND source_order_ref = ? AND status != 'cancelled'
                LIMIT 1
                """,
                (rs, rowNum) -> Map.of("id", rs.getString("id")),
                tenantId,
                sourceOrderRef
        );
        if (!existing.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "该订单已推送至仓库");
        }
        payload.put("fromPlatformOrder", true);
        payload.put("sourceOrderRef", sourceOrderRef);
        return createOrder(payload);
    }

    public Map<String, Object> reviewOrder(String id, Map<String, Object> payload) {
        requireWarehousePortal();
        Long tenantId = requireTenant();
        Map<String, Object> order = findOrder(tenantId, id);
        assertWarehouseWritable(order);
        String status = String.valueOf(order.get("status"));
        if ("cancelled".equals(status) || "shipped".equals(status)) {
            throw badRequest("当前订单状态不可审批");
        }

        boolean canShip = Boolean.TRUE.equals(payload.get("canShip"));
        Map<String, Object> review = new LinkedHashMap<>();
        review.put("canShip", canShip);
        review.put("estimatedShipAt", text(payload.get("estimatedShipAt"), ""));
        review.put("missingMaterials", text(payload.get("missingMaterials"), ""));
        review.put("packagingNotes", text(payload.get("packagingNotes"), ""));
        review.put("extraOrderNotes", text(payload.get("extraOrderNotes"), ""));
        review.put("reviewRemark", text(payload.get("reviewRemark"), ""));
        review.put("reviewedById", String.valueOf(authContext.userId()));
        review.put("reviewedByName", resolveSubmitterName(authContext.userId(), "warehouse"));
        review.put("reviewedAt", nowText());

        updateOrder(tenantId, id, canShip ? "pending_shipment" : "blocked", review);
        return findOrder(tenantId, id);
    }

    public Map<String, Object> releaseOrder(String id, Map<String, Object> payload) {
        requireWarehousePortal();
        Long tenantId = requireTenant();
        Map<String, Object> order = findOrder(tenantId, id);
        assertWarehouseWritable(order);
        if (!"blocked".equals(order.get("status"))) {
            throw badRequest("仅暂不可发订单可确认可发");
        }

        @SuppressWarnings("unchecked")
        Map<String, Object> review = order.get("warehouseReview") instanceof Map<?, ?> map
                ? new LinkedHashMap<>((Map<String, Object>) map)
                : new LinkedHashMap<>();

        review.put("canShip", true);
        review.put("estimatedShipAt", text(payload.get("estimatedShipAt"), ""));
        review.put("releaseRemark", text(payload.get("releaseRemark"), ""));
        review.put("releasedById", String.valueOf(authContext.userId()));
        review.put("releasedByName", resolveSubmitterName(authContext.userId(), "warehouse"));
        review.put("releasedAt", nowText());

        updateOrder(tenantId, id, "pending_shipment", review);
        return findOrder(tenantId, id);
    }

    public Map<String, Object> shipOrder(String id) {
        requireWarehousePortal();
        Long tenantId = requireTenant();
        Map<String, Object> order = findOrder(tenantId, id);
        assertWarehouseWritable(order);
        if (!"pending_shipment".equals(order.get("status"))) {
            throw badRequest("仅待发货订单可标记为已发货");
        }
        updateOrder(tenantId, id, "shipped", order.get("warehouseReview"));
        return findOrder(tenantId, id);
    }

    public Map<String, Object> cancelOrder(String id) {
        Long tenantId = requireTenant();
        Map<String, Object> order = findOrder(tenantId, id);
        assertCancellable(order);
        String status = String.valueOf(order.get("status"));
        if (!"pending_review".equals(status) && !"blocked".equals(status)) {
            throw badRequest("当前状态不可取消");
        }
        updateOrder(tenantId, id, "cancelled", order.get("warehouseReview"));
        return findOrder(tenantId, id);
    }

    public void deleteOrder(String id) {
        requireBossPortal();
        Long tenantId = requireTenant();
        findOrder(tenantId, id);
        jdbc.update("DELETE FROM warehouse_order WHERE tenant_id = ? AND id = ?", tenantId, id);
    }

    private List<Map<String, Object>> queryOrders(Long tenantId, String submittedById, List<String> warehouseIds) {
        StringBuilder sql = new StringBuilder("""
                SELECT * FROM warehouse_order
                WHERE tenant_id = ?
                """);
        List<Object> args = new ArrayList<>();
        args.add(tenantId);

        if (submittedById != null) {
            sql.append(" AND submitted_by_id = ?");
            args.add(submittedById);
        }
        if (warehouseIds != null) {
            if (warehouseIds.isEmpty()) {
                return List.of();
            }
            sql.append(" AND warehouse_id IN (")
                    .append(String.join(",", Collections.nCopies(warehouseIds.size(), "?")))
                    .append(")");
            args.addAll(warehouseIds);
        }

        sql.append(" ORDER BY submitted_at DESC");
        return jdbc.query(sql.toString(), (rs, rowNum) -> mapRow(rs), args.toArray());
    }

    private Map<String, Object> findOrder(Long tenantId, String id) {
        List<Map<String, Object>> rows = jdbc.query(
                "SELECT * FROM warehouse_order WHERE tenant_id = ? AND id = ? LIMIT 1",
                (rs, rowNum) -> mapRow(rs),
                tenantId,
                id
        );
        if (rows.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "订单不存在");
        }
        return rows.get(0);
    }

    private Map<String, Object> mapRow(java.sql.ResultSet rs) throws java.sql.SQLException {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", rs.getString("id"));
        row.put("orderNo", rs.getString("order_no"));
        row.put("status", rs.getString("status"));
        row.put("warehouseId", rs.getString("warehouse_id"));
        row.put("warehouseName", rs.getString("warehouse_name"));
        row.put("sourceType", rs.getString("source_type"));
        row.put("sourcePlatform", rs.getString("source_platform"));
        row.put("sourceStoreName", rs.getString("source_store_name"));
        row.put("sourceLabel", rs.getString("source_label"));
        row.put("b2bCustomerName", rs.getString("b2b_customer_name"));
        row.put("remark", rs.getString("remark"));
        row.put("items", readJsonList(rs.getString("items_json")));
        row.put("attachments", readJsonList(rs.getString("attachments_json")));
        row.put("cartonMarks", readJsonList(rs.getString("carton_marks_json")));
        row.put("labels", readJsonList(rs.getString("labels_json")));
        row.put("submittedByRole", rs.getString("submitted_by_role"));
        row.put("submittedById", rs.getString("submitted_by_id"));
        row.put("submittedByName", rs.getString("submitted_by_name"));
        row.put("submittedAt", rs.getString("submitted_at"));
        row.put("warehouseReview", readJsonMap(rs.getString("warehouse_review_json")));
        row.put("updatedAt", rs.getString("updated_at"));
        row.put("sourceOrderRef", rs.getString("source_order_ref"));
        row.put("fromPlatformOrder", rs.getInt("from_platform_order") == 1);
        return row;
    }

    private void updateOrder(Long tenantId, String id, String status, Object review) {
        if (!VALID_STATUS.contains(status)) {
            throw badRequest("无效状态");
        }
        jdbc.update(
                "UPDATE warehouse_order SET status = ?, warehouse_review_json = ?, updated_at = ? WHERE tenant_id = ? AND id = ?",
                status,
                review == null ? null : writeJson(review),
                nowText(),
                tenantId,
                id
        );
    }

    private Map<String, Object> stats(List<Map<String, Object>> orders) {
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("total", orders.size());
        stats.put("pendingReview", countStatus(orders, "pending_review"));
        stats.put("pendingShipment", countStatus(orders, "pending_shipment"));
        stats.put("blocked", countStatus(orders, "blocked"));
        stats.put("shipped", countStatus(orders, "shipped"));
        return stats;
    }

    private long countStatus(List<Map<String, Object>> orders, String status) {
        return orders.stream().filter(o -> status.equals(o.get("status"))).count();
    }

    private void assertReadable(Map<String, Object> order) {
        if ("employee".equalsIgnoreCase(authContext.portalRole())) {
            String owner = String.valueOf(order.get("submittedById"));
            if (!String.valueOf(authContext.userId()).equals(owner)) {
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, "无权查看该订单");
            }
        }
        if ("warehouse".equalsIgnoreCase(authContext.portalRole())) {
            assertWarehouseWritable(order);
        }
    }

    private void assertWarehouseWritable(Map<String, Object> order) {
        if (!authContext.isWarehousePortal()) {
            return;
        }
        List<String> scope = authContext.warehouseScope();
        if (scope.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "未分配仓库管理权限");
        }
        String warehouseId = String.valueOf(order.getOrDefault("warehouseId", ""));
        if (!scope.contains(warehouseId)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "无权操作该仓库订单");
        }
    }

    private void assertCancellable(Map<String, Object> order) {
        String portal = authContext.portalRole();
        if ("warehouse".equalsIgnoreCase(portal)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "仓库用户不可取消订单");
        }
        if ("employee".equalsIgnoreCase(portal)) {
            String owner = String.valueOf(order.get("submittedById"));
            if (!String.valueOf(authContext.userId()).equals(owner)) {
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, "无权取消该订单");
            }
        }
    }

    private void requireSubmitterPortal() {
        String portal = authContext.portalRole();
        if (!"boss".equalsIgnoreCase(portal) && !"employee".equalsIgnoreCase(portal)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "无权创建出库单");
        }
    }

    private void requireEmployeeWarehouseGrant(Long tenantId, Long userId) {
        if (!"employee".equalsIgnoreCase(authContext.portalRole())) {
            return;
        }
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "未登录");
        }
        boolean granted = menuGrantRepository.findByTenantIdAndUserId(tenantId, userId).stream()
                .anyMatch(row -> "employee.warehouse".equals(row.getMenuCode()));
        if (!granted) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "未授权仓库下单功能");
        }
    }

    private void requireWarehousePortal() {
        if (!authContext.isWarehousePortal()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "仅仓库用户可操作");
        }
    }

    private void requireBossPortal() {
        if (!authContext.isBossPortal()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "仅企业管理员可删除订单");
        }
    }

    private Long requireTenant() {
        Long tenantId = authContext.tenantId();
        if (tenantId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "未登录");
        }
        return tenantId;
    }

    private String resolveSubmitterName(Long userId, String roleHint) {
        if ("boss".equals(roleHint)) {
            return jdbc.query(
                    "SELECT nickname FROM app_user WHERE id = ? LIMIT 1",
                    rs -> rs.next() ? rs.getString(1) : "企业管理员",
                    userId
            );
        }
        return jdbc.query(
                "SELECT nickname FROM app_user WHERE id = ? LIMIT 1",
                rs -> rs.next() ? rs.getString(1) : "仓库用户",
                userId
        );
    }

    private String nextOrderNo(Long tenantId) {
        String date = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM warehouse_order WHERE tenant_id = ? AND order_no LIKE ?",
                Integer.class,
                tenantId,
                "WH" + date + "%"
        );
        int seq = (count == null ? 0 : count) + 1;
        return "WH" + date + String.format("%03d", seq);
    }

    private String buildSourceLabel(Map<String, Object> payload) {
        String sourceType = text(payload.get("sourceType"), "marketplace");
        if ("b2b".equals(sourceType)) {
            String name = text(payload.get("b2bCustomerName"), "");
            return name.isEmpty() ? "B 端客户货" : "B 端 · " + name;
        }
        String platform = PLATFORM_LABELS.getOrDefault(
                text(payload.get("sourcePlatform"), ""),
                text(payload.get("sourcePlatform"), "电商平台")
        );
        String store = text(payload.get("sourceStoreName"), "");
        return store.isEmpty() ? platform : platform + " · " + store;
    }

    private List<Map<String, Object>> normalizeItems(List<Map<String, Object>> items) {
        List<Map<String, Object>> normalized = new ArrayList<>();
        for (int i = 0; i < items.size(); i++) {
            Map<String, Object> item = items.get(i);
            Map<String, Object> row = new LinkedHashMap<>();
            Object id = item.get("id");
            row.put("id", id != null ? String.valueOf(id) : "li_" + System.currentTimeMillis() + "_" + i);
            row.put("productName", text(item.get("productName"), "").trim());
            row.put("sku", text(item.get("sku"), "").trim());
            Number qty = (Number) item.get("quantity");
            row.put("quantity", qty == null ? 1 : qty.intValue());
            row.put("unit", text(item.get("unit"), "件"));
            normalized.add(row);
        }
        return normalized;
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> normalizeFiles(Object raw, String prefix) {
        if (!(raw instanceof List<?> list)) return List.of();
        List<Map<String, Object>> normalized = new ArrayList<>();
        for (int i = 0; i < list.size(); i++) {
            if (!(list.get(i) instanceof Map<?, ?> map)) continue;
            Map<String, Object> file = new LinkedHashMap<>((Map<String, Object>) map);
            if (file.get("id") == null) {
                file.put("id", prefix + "_" + System.currentTimeMillis() + "_" + i);
            }
            normalized.add(file);
        }
        return normalized;
    }

    private List<Map<String, Object>> readJsonList(String json) {
        if (json == null || json.isBlank()) return List.of();
        try {
            return objectMapper.readValue(json, new TypeReference<>() {});
        } catch (Exception ex) {
            return List.of();
        }
    }

    private Map<String, Object> readJsonMap(String json) {
        if (json == null || json.isBlank()) return null;
        try {
            return objectMapper.readValue(json, new TypeReference<>() {});
        } catch (Exception ex) {
            return null;
        }
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception ex) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "JSON 序列化失败");
        }
    }

    private String nowText() {
        return LocalDateTime.now().format(DT);
    }

    private String text(Object value, String fallback) {
        if (value == null) return fallback;
        return String.valueOf(value).trim();
    }

    private String randomSuffix() {
        return Integer.toHexString(new Random().nextInt(0x10000));
    }

    private ResponseStatusException badRequest(String message) {
        return new ResponseStatusException(HttpStatus.BAD_REQUEST, message);
    }
}
