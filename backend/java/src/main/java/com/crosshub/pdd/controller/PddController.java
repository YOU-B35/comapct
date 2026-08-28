package com.crosshub.pdd.controller;

import com.crosshub.common.ApiResult;
import com.crosshub.common.AppErrorCode;
import com.crosshub.pdd.service.PddOpsService;
import com.crosshub.tenant.service.DataScopeService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.Map;

/**
 * 拼多多运营读 API + 同步触发。对齐 {@code Alibaba1688Controller}。
 * 路由前缀 {@code /api/pdd}，由 Vite 代理转发 Java :18080。
 *
 * <p>新增经营驾驶舱三端点 {@code /operations/summary|trend|overview}，
 * 并扩展 {@code /orders} 支持 startDate/endDate + status/keyword + page/pageSize 后端分页，
 * 数据由 agent 携带 cookie 抓取订单 XHR 后写入 pdd_order 直接同步读取。
 */
@RestController
@RequestMapping("/api/pdd")
public class PddController {
    private final PddOpsService pddOpsService;
    private final DataScopeService dataScopeService;

    public PddController(PddOpsService pddOpsService, DataScopeService dataScopeService) {
        this.pddOpsService = pddOpsService;
        this.dataScopeService = dataScopeService;
    }

    @GetMapping("/session")
    public Map<String, Object> session(
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake
    ) {
        String sid = storeId != null && !storeId.isBlank() ? storeId : storeIdSnake;
        return ApiResult.ok(pddOpsService.session(sid));
    }

    @PostMapping("/login/open")
    public ResponseEntity<Map<String, Object>> loginOpen(
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake
    ) {
        try {
            String sid = storeId != null && !storeId.isBlank() ? storeId : storeIdSnake;
            return ResponseEntity.ok(ApiResult.ok(pddOpsService.enqueueLoginOpen(sid)));
        } catch (ResponseStatusException ex) {
            return mapError(ex);
        }
    }

    @PostMapping("/session/probe")
    public ResponseEntity<Map<String, Object>> sessionProbe(
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake
    ) {
        try {
            String sid = storeId != null && !storeId.isBlank() ? storeId : storeIdSnake;
            return ResponseEntity.ok(ApiResult.ok(pddOpsService.enqueueSessionProbe(sid)));
        } catch (ResponseStatusException ex) {
            return mapError(ex);
        }
    }

    /**
     * 触发同步。body: scope(orders/products/compass/all) / force / store_id / date_window(today/d1/d7/d30/d90)
     */
    @PostMapping("/sync")
    public ResponseEntity<Map<String, Object>> sync(@RequestBody(required = false) Map<String, Object> body) {
        try {
            body = body == null ? Map.of() : body;
            String scope = String.valueOf(body.getOrDefault("scope", "orders"));
            boolean force = Boolean.TRUE.equals(body.get("force"));
            Object storeRaw = body.get("store_id");
            if (storeRaw == null) storeRaw = body.get("storeId");
            String storeId = storeRaw == null ? null : String.valueOf(storeRaw);
            Object windowRaw = body.get("date_window");
            if (windowRaw == null) windowRaw = body.get("dateWindow");
            String dateWindow = windowRaw == null ? null : String.valueOf(windowRaw);
            return ResponseEntity.status(HttpStatus.ACCEPTED)
                    .body(ApiResult.ok(pddOpsService.enqueueSync(scope, force, storeId, dateWindow)));
        } catch (ResponseStatusException ex) {
            return mapError(ex);
        }
    }

    @GetMapping("/sync/{jobId}")
    public Map<String, Object> syncJob(@PathVariable String jobId) {
        return ApiResult.ok(pddOpsService.getSyncJob(jobId));
    }

    /** 今日订单（date_window=today 的快捷） */
    @GetMapping("/orders/today")
    public Map<String, Object> ordersToday(@RequestParam(value = "store_id", required = false) String storeId) {
        return ApiResult.ok(pddOpsService.todayOrders(storeId));
    }

    /**
     * 订单列表。对齐 {@code Alibaba1688Controller.orders}。
     * 支持新旧两种签名：
     * <ul>
     *   <li>新签名（前端 OrderDetailsPanel 调用）：start_date/end_date + status/keyword + page/page_size</li>
     *   <li>旧签名（domesticPlatforms 调用）：date_window</li>
     * </ul>
     */
    @GetMapping("/orders")
    public Map<String, Object> orders(
            @RequestParam(value = "date_window", required = false) String dateWindow,
            @RequestParam(value = "start_date", required = false) String startDate,
            @RequestParam(value = "end_date", required = false) String endDate,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String keyword,
            @RequestParam(value = "store_id", required = false) String storeId,
            @RequestParam(value = "page", required = false, defaultValue = "1") int page,
            @RequestParam(value = "page_size", required = false, defaultValue = "20") int pageSize
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        if (startDate != null && !startDate.isBlank() && endDate != null && !endDate.isBlank()) {
            LocalDate[] range = parseRange(startDate, endDate);
            String sid = resolveStoreId(storeId);
            return ApiResult.ok(pddOpsService.listOrders(
                    tenantId, range[0], range[1], status, keyword, sid, page, pageSize
            ));
        }
        String window = dateWindow == null || dateWindow.isBlank() ? "today" : dateWindow;
        return ApiResult.ok(pddOpsService.ordersByWindow(storeId, window));
    }

    /** 经营汇总（对齐 Alibaba1688Controller.operationsSummary） */
    @GetMapping("/operations/summary")
    public Map<String, Object> operationsSummary(
            @RequestParam(value = "start_date") String startDate,
            @RequestParam(value = "end_date") String endDate,
            @RequestParam(value = "store_id", required = false) String storeId
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        LocalDate[] range = parseRange(startDate, endDate);
        return ApiResult.ok(pddOpsService.summary(tenantId, range[0], range[1], resolveStoreId(storeId)));
    }

    /** 销售额 / 订单趋势（对齐 Alibaba1688Controller.operationsTrend） */
    @GetMapping("/operations/trend")
    public Map<String, Object> operationsTrend(
            @RequestParam(value = "start_date") String startDate,
            @RequestParam(value = "end_date") String endDate,
            @RequestParam(value = "store_id", required = false) String storeId
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        LocalDate[] range = parseRange(startDate, endDate);
        return ApiResult.ok(pddOpsService.trend(tenantId, range[0], range[1], resolveStoreId(storeId)));
    }

    /** 多店铺经营总览（对齐 Alibaba1688Controller.operationsOverview） */
    @GetMapping("/operations/overview")
    public Map<String, Object> operationsOverview(
            @RequestParam(value = "start_date") String startDate,
            @RequestParam(value = "end_date") String endDate
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        LocalDate[] range = parseRange(startDate, endDate);
        return ApiResult.ok(pddOpsService.overview(tenantId, range[0], range[1]));
    }

    @GetMapping("/products")
    public Map<String, Object> products(@RequestParam(value = "store_id", required = false) String storeId) {
        return ApiResult.ok(pddOpsService.listProducts(storeId));
    }

    @GetMapping("/product-analytics")
    public Map<String, Object> productAnalytics(
            @RequestParam(value = "type", required = false) String type,
            @RequestParam(value = "store_id", required = false) String storeId
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        return ApiResult.ok(pddOpsService.productAnalytics(type, tenantId, resolveStoreId(storeId)));
    }

    @GetMapping("/peer-bestsellers")
    public Map<String, Object> peerBestsellers(
            @RequestParam(value = "store_id", required = false) String storeId,
            @RequestParam(value = "page", required = false, defaultValue = "1") int page,
            @RequestParam(value = "page_size", required = false, defaultValue = "10") int pageSize
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        return ApiResult.ok(pddOpsService.listPeerBestsellers(tenantId, resolveStoreId(storeId), page, pageSize));
    }

    @GetMapping("/compass")
    public Map<String, Object> compass(
            @RequestParam(value = "store_id", required = false) String storeId,
            @RequestParam(value = "date_type", required = false) Integer dateType,
            @RequestParam(value = "all", required = false) Boolean all
    ) {
        if (Boolean.TRUE.equals(all)) {
            return ApiResult.ok(pddOpsService.listCompass(storeId));
        }
        return ApiResult.ok(pddOpsService.getCompass(storeId, dateType));
    }

    @GetMapping("/issues")
    public Map<String, Object> issues(@RequestParam(value = "store_id", required = false) String storeId) {
        return ApiResult.ok(pddOpsService.listIssues(storeId));
    }

    @PatchMapping("/issues/{id}")
    public Map<String, Object> resolveIssue(@PathVariable String id, @RequestBody(required = false) Map<String, Object> body) {
        return ApiResult.ok(pddOpsService.resolveIssue(id, body == null ? Map.of() : body));
    }

    private static LocalDate[] parseRange(String startDate, String endDate) {
        try {
            LocalDate start = LocalDate.parse(startDate);
            LocalDate end = LocalDate.parse(endDate);
            if (end.isBefore(start)) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "end_date 不能早于 start_date");
            }
            return new LocalDate[]{start, end};
        } catch (DateTimeParseException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "日期格式应为 yyyy-MM-dd");
        }
    }

    private static String resolveStoreId(String storeId) {
        return storeId == null || storeId.isBlank() || "all".equals(storeId) ? null : storeId;
    }

    private ResponseEntity<Map<String, Object>> mapError(ResponseStatusException ex) {
        String msg = ex.getReason() == null ? AppErrorCode.UNKNOWN.getUserMessage() : ex.getReason();
        AppErrorCode code = AppErrorCode.fromReason(msg);
        if (code == AppErrorCode.UNKNOWN || code == AppErrorCode.SERVER_ERROR) {
            if (msg.contains("未在线") || msg.contains("助手")) {
                code = AppErrorCode.PDD_AGENT_OFFLINE;
            } else if (msg.contains("进行中")) {
                code = AppErrorCode.PDD_SYNC_IN_PROGRESS;
            } else if (msg.contains("外部 ID") || msg.contains("映射")) {
                code = AppErrorCode.PDD_SHOP_MAPPING_REQUIRED;
            } else if (msg.contains("未登录")) {
                code = AppErrorCode.PDD_NOT_LOGGED_IN;
            } else if (msg.contains("罗盘")) {
                code = AppErrorCode.PDD_COMPASS_SOURCE_UNAVAILABLE;
            } else if (msg.contains("商品")) {
                code = AppErrorCode.PDD_PRODUCTS_SOURCE_UNAVAILABLE;
            }
        }
        HttpStatus status = HttpStatus.resolve(ex.getStatusCode().value());
        if (status == null) status = HttpStatus.BAD_REQUEST;
        if (status == HttpStatus.CONFLICT) {
            return ResponseEntity.status(status).body(ApiResult.conflict(
                    status.value(), code.getUserMessage(), code.getCode(), Map.of()
            ));
        }
        return ResponseEntity.status(status).body(ApiResult.error(status.value(), code.getCode(), code.getUserMessage()));
    }
}
