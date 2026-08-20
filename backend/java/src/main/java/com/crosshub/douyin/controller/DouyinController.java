package com.crosshub.douyin.controller;

import com.crosshub.common.ApiResult;
import com.crosshub.common.AppErrorCode;
import com.crosshub.douyin.service.DouyinOpsService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;

@RestController
@RequestMapping("/api/douyin")
public class DouyinController {
    private final DouyinOpsService douyinOpsService;

    public DouyinController(DouyinOpsService douyinOpsService) {
        this.douyinOpsService = douyinOpsService;
    }

    @GetMapping("/session")
    public Map<String, Object> session() {
        return ApiResult.ok(douyinOpsService.session());
    }

    @PostMapping("/login/open")
    public ResponseEntity<Map<String, Object>> loginOpen(
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake
    ) {
        try {
            String sid = storeId != null && !storeId.isBlank() ? storeId : storeIdSnake;
            return ResponseEntity.ok(ApiResult.ok(douyinOpsService.enqueueLoginOpen(sid)));
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
            return ResponseEntity.ok(ApiResult.ok(douyinOpsService.enqueueSessionProbe(sid)));
        } catch (ResponseStatusException ex) {
            return mapError(ex);
        }
    }

    @PostMapping("/sync")
    public ResponseEntity<Map<String, Object>> sync(@RequestBody(required = false) Map<String, Object> body) {
        try {
            String scope = body == null ? "orders" : String.valueOf(body.getOrDefault("scope", "orders"));
            boolean force = body != null && Boolean.TRUE.equals(body.get("force"));
            Object storeRaw = body == null ? null : body.get("store_id");
            if (storeRaw == null && body != null) {
                storeRaw = body.get("storeId");
            }
            String storeId = storeRaw == null ? null : String.valueOf(storeRaw);
            String categoryQuery = null;
            String categoryId = null;
            String pool = null;
            String sortField = null;
            if (body != null) {
                Object cq = body.get("category_query");
                if (cq == null) cq = body.get("categoryQuery");
                if (cq != null) categoryQuery = String.valueOf(cq);
                Object cid = body.get("category_id");
                if (cid == null) cid = body.get("categoryId");
                if (cid != null) categoryId = String.valueOf(cid);
                Object poolRaw = body.get("pool");
                if (poolRaw == null) poolRaw = body.get("opportunity_pool");
                if (poolRaw != null) pool = String.valueOf(poolRaw);
                Object sortRaw = body.get("sort_field");
                if (sortRaw == null) sortRaw = body.get("sortField");
                if (sortRaw != null) sortField = String.valueOf(sortRaw);
            }
            return ResponseEntity.status(HttpStatus.ACCEPTED)
                    .body(ApiResult.ok(douyinOpsService.enqueueSync(
                            scope, force, storeId, categoryQuery, categoryId, pool, sortField
                    )));
        } catch (ResponseStatusException ex) {
            return mapError(ex);
        }
    }

    @GetMapping("/sync/{jobId}")
    public Map<String, Object> syncJob(@PathVariable String jobId) {
        return ApiResult.ok(douyinOpsService.getSyncJob(jobId));
    }

    @GetMapping("/orders/today")
    public Map<String, Object> ordersToday(@RequestParam(value = "store_id", required = false) String storeId) {
        return ApiResult.ok(douyinOpsService.todayOrders(storeId));
    }

    @GetMapping("/products")
    public Map<String, Object> products(@RequestParam(value = "store_id", required = false) String storeId) {
        return ApiResult.ok(douyinOpsService.listProducts(storeId));
    }

    @GetMapping("/compass")
    public Map<String, Object> compass(
            @RequestParam(value = "store_id", required = false) String storeId,
            @RequestParam(value = "date_type", required = false) Integer dateType,
            @RequestParam(value = "all", required = false) Boolean all
    ) {
        if (Boolean.TRUE.equals(all)) {
            return ApiResult.ok(douyinOpsService.listCompass(storeId));
        }
        return ApiResult.ok(douyinOpsService.getCompass(storeId, dateType));
    }

    @GetMapping("/opportunity/products")
    public Map<String, Object> opportunityProducts(
            @RequestParam(value = "store_id", required = false) String storeId,
            @RequestParam(value = "category_key", required = false) String categoryKey,
            @RequestParam(value = "q", required = false) String q,
            @RequestParam(value = "pool", required = false) String pool,
            @RequestParam(value = "sort_field", required = false) String sortField
    ) {
        return ApiResult.ok(douyinOpsService.listOpportunityProducts(storeId, categoryKey, q, pool, sortField));
    }

    @GetMapping("/opportunity/products/{id}/overview")
    public Map<String, Object> opportunityOverview(@PathVariable String id) {
        return ApiResult.ok(douyinOpsService.getOpportunityOverview(id));
    }

    @GetMapping("/compass-product-ranks")
    public Map<String, Object> compassProductRanks(
            @RequestParam(value = "store_id", required = false) String storeId,
            @RequestParam(value = "board", required = false) String board,
            @RequestParam(value = "date_window", required = false) String dateWindow
    ) {
        return ApiResult.ok(douyinOpsService.listCompassProductRanks(storeId, board, dateWindow));
    }

    @GetMapping("/issues")
    public Map<String, Object> issues(@RequestParam(value = "store_id", required = false) String storeId) {
        return ApiResult.ok(douyinOpsService.listIssues(storeId));
    }

    @PatchMapping("/issues/{id}")
    public Map<String, Object> resolveIssue(@PathVariable String id, @RequestBody(required = false) Map<String, Object> body) {
        return ApiResult.ok(douyinOpsService.resolveIssue(id, body == null ? Map.of() : body));
    }

    private ResponseEntity<Map<String, Object>> mapError(ResponseStatusException ex) {
        String msg = ex.getReason() == null ? AppErrorCode.UNKNOWN.getUserMessage() : ex.getReason();
        AppErrorCode code = AppErrorCode.fromReason(msg);
        if (code == AppErrorCode.UNKNOWN || code == AppErrorCode.SERVER_ERROR) {
            if (msg.contains("未在线") || msg.contains("助手")) {
                code = AppErrorCode.DY_AGENT_OFFLINE;
            } else if (msg.contains("进行中")) {
                code = AppErrorCode.DY_SYNC_IN_PROGRESS;
            } else if (msg.contains("外部 ID") || msg.contains("映射")) {
                code = AppErrorCode.DY_SHOP_MAPPING_REQUIRED;
            } else if (msg.contains("未登录")) {
                code = AppErrorCode.DY_NOT_LOGGED_IN;
            } else if (msg.contains("商品榜") || msg.contains("罗盘商品")) {
                code = AppErrorCode.DY_COMPASS_RANK_SOURCE_UNAVAILABLE;
            } else if (msg.contains("商品")) {
                code = AppErrorCode.DY_PRODUCTS_SOURCE_UNAVAILABLE;
            } else if (msg.contains("罗盘")) {
                code = AppErrorCode.DY_COMPASS_SOURCE_UNAVAILABLE;
            } else if (msg.contains("商机")) {
                code = AppErrorCode.DY_OPPORTUNITY_SOURCE_UNAVAILABLE;
            }
        }
        HttpStatus status = HttpStatus.resolve(ex.getStatusCode().value());
        if (status == null) {
            status = HttpStatus.BAD_REQUEST;
        }
        if (status == HttpStatus.CONFLICT) {
            return ResponseEntity.status(status).body(ApiResult.conflict(
                    status.value(),
                    code.getUserMessage(),
                    code.getCode(),
                    Map.of()
            ));
        }
        return ResponseEntity.status(status).body(ApiResult.error(status.value(), code.getCode(), code.getUserMessage()));
    }
}
