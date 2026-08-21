package com.crosshub.alibaba1688.controller;

import com.crosshub.alibaba1688.dto.Alibaba1688CrawlRequest;
import com.crosshub.alibaba1688.entity.Alibaba1688CrawlJob;
import com.crosshub.alibaba1688.service.Alibaba1688CrawlConflictException;
import com.crosshub.alibaba1688.service.Alibaba1688CrawlService;
import com.crosshub.alibaba1688.service.Alibaba1688OperationalService;
import com.crosshub.alibaba1688.service.Alibaba1688ProductService;
import com.crosshub.alibaba1688.service.Alibaba1688RetailOpsService;
import com.crosshub.alibaba1688.service.Alibaba1688SessionService;
import com.crosshub.alibaba1688.service.impl.Alibaba1688CrawlServiceImpl;
import com.crosshub.common.ApiResult;
import com.crosshub.common.AppErrorCode;
import com.crosshub.tenant.service.DataScopeService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.ArrayList;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/1688")
public class Alibaba1688Controller {
    private final Alibaba1688CrawlService crawlService;
    private final Alibaba1688OperationalService operationalService;
    private final Alibaba1688SessionService sessionService;
    private final Alibaba1688ProductService productService;
    private final Alibaba1688RetailOpsService retailOpsService;
    private final DataScopeService dataScopeService;

    public Alibaba1688Controller(
            Alibaba1688CrawlService crawlService,
            Alibaba1688OperationalService operationalService,
            Alibaba1688SessionService sessionService,
            Alibaba1688ProductService productService,
            Alibaba1688RetailOpsService retailOpsService,
            DataScopeService dataScopeService
    ) {
        this.crawlService = crawlService;
        this.operationalService = operationalService;
        this.sessionService = sessionService;
        this.productService = productService;
        this.retailOpsService = retailOpsService;
        this.dataScopeService = dataScopeService;
    }

    @GetMapping("/session")
    public Map<String, Object> session(
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake
    ) {
        String sid = storeId != null && !storeId.isBlank() ? storeId : storeIdSnake;
        return ApiResult.ok(sessionService.session(sid));
    }

    @GetMapping("/login/status")
    public Map<String, Object> loginStatus() {
        return ApiResult.ok(sessionService.latestLoginStatus());
    }

    @PostMapping("/login/open")
    public ResponseEntity<Map<String, Object>> loginOpen(
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake
    ) {
        try {
            String sid = storeId != null && !storeId.isBlank() ? storeId : storeIdSnake;
            return ResponseEntity.ok(ApiResult.ok(sessionService.enqueueLoginOpen(sid)));
        } catch (ResponseStatusException ex) {
            return mapSessionError(ex);
        }
    }

    @PostMapping("/session/probe")
    public ResponseEntity<Map<String, Object>> sessionProbe(
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake
    ) {
        try {
            String sid = storeId != null && !storeId.isBlank() ? storeId : storeIdSnake;
            return ResponseEntity.ok(ApiResult.ok(sessionService.enqueueSessionProbe(sid)));
        } catch (ResponseStatusException ex) {
            return mapSessionError(ex);
        }
    }

    @PostMapping("/products/sync")
    public ResponseEntity<Map<String, Object>> syncProducts() {
        try {
            return ResponseEntity.ok(ApiResult.ok(productService.enqueueProductsSync()));
        } catch (ResponseStatusException ex) {
            return mapSessionError(ex);
        }
    }

    @PostMapping("/orders/sync")
    public ResponseEntity<Map<String, Object>> syncOrders(
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake
    ) {
        try {
            String sid = storeId != null && !storeId.isBlank() ? storeId : storeIdSnake;
            return ResponseEntity.ok(ApiResult.ok(sessionService.enqueueOrdersSync(sid)));
        } catch (ResponseStatusException ex) {
            return mapSessionError(ex);
        }
    }

    @GetMapping("/products")
    public Map<String, Object> products(
            @RequestParam(required = false, defaultValue = "all") String tab,
            @RequestParam(required = false, defaultValue = "all") String status,
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake
    ) {
        String sid = storeId != null && !storeId.isBlank() ? storeId : storeIdSnake;
        return ApiResult.ok(productService.listProducts(tab, status, sid));
    }

    @GetMapping("/operations/summary")
    public Map<String, Object> operationsSummary(
            @RequestParam String startDate,
            @RequestParam String endDate,
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        LocalDate[] range = parseRange(startDate, endDate);
        return ApiResult.ok(retailOpsService.summary(
                tenantId,
                range[0],
                range[1],
                storeId != null && !storeId.isBlank() ? storeId : storeIdSnake
        ));
    }

    @GetMapping("/operations/trend")
    public Map<String, Object> operationsTrend(
            @RequestParam String startDate,
            @RequestParam String endDate,
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        LocalDate[] range = parseRange(startDate, endDate);
        return ApiResult.ok(retailOpsService.trend(
                tenantId,
                range[0],
                range[1],
                storeId != null && !storeId.isBlank() ? storeId : storeIdSnake
        ));
    }

    @GetMapping("/operations/overview")
    public Map<String, Object> operationsOverview(
            @RequestParam String startDate,
            @RequestParam String endDate
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        LocalDate[] range = parseRange(startDate, endDate);
        return ApiResult.ok(retailOpsService.overview(tenantId, range[0], range[1]));
    }

    @GetMapping("/orders")
    public Map<String, Object> orders(
            @RequestParam(required = false) String startDate,
            @RequestParam(required = false) String endDate,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake,
            @RequestParam(required = false, defaultValue = "1") int page,
            @RequestParam(required = false, defaultValue = "20") int pageSize
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        LocalDate start = null;
        LocalDate end = null;
        if (startDate != null && !startDate.isBlank() && endDate != null && !endDate.isBlank()) {
            LocalDate[] range = parseRange(startDate, endDate);
            start = range[0];
            end = range[1];
        }
        return ApiResult.ok(retailOpsService.listOrders(
                tenantId,
                start,
                end,
                status,
                keyword,
                storeId != null && !storeId.isBlank() ? storeId : storeIdSnake,
                page,
                pageSize
        ));
    }

    @GetMapping("/products/analytics")
    public Map<String, Object> productAnalytics(
            @RequestParam String type,
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        return ApiResult.ok(retailOpsService.productAnalytics(
                type,
                tenantId,
                storeId != null && !storeId.isBlank() ? storeId : storeIdSnake
        ));
    }

    @GetMapping("/sync-logs")
    public Map<String, Object> syncLogs(@RequestParam(required = false, defaultValue = "20") int limit) {
        Long tenantId = dataScopeService.requireTenantId();
        return ApiResult.ok(retailOpsService.listSyncLogs(tenantId, limit));
    }

    @GetMapping("/peer-bestsellers")
    public Map<String, Object> peerBestsellers(
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake,
            @RequestParam(required = false, defaultValue = "1") int page,
            @RequestParam(required = false, defaultValue = "10") int pageSize
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        return ApiResult.ok(retailOpsService.listPeerBestsellers(
                tenantId,
                storeId != null && !storeId.isBlank() ? storeId : storeIdSnake,
                page,
                pageSize
        ));
    }

    @PostMapping("/peer-bestsellers/sync")
    public ResponseEntity<Map<String, Object>> syncPeerBestsellers(
            @RequestParam(required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake
    ) {
        try {
            String sid = storeId != null && !storeId.isBlank() ? storeId : storeIdSnake;
            return ResponseEntity.ok(ApiResult.ok(sessionService.enqueuePeerBestsellersSync(sid)));
        } catch (ResponseStatusException ex) {
            return mapSessionError(ex);
        }
    }

    private static LocalDate[] parseRange(String startDate, String endDate) {
        try {
            LocalDate start = LocalDate.parse(startDate);
            LocalDate end = LocalDate.parse(endDate);
            if (end.isBefore(start)) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "endDate 不能早于 startDate");
            }
            return new LocalDate[]{start, end};
        } catch (DateTimeParseException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "日期格式应为 yyyy-MM-dd");
        }
    }

    private ResponseEntity<Map<String, Object>> mapSessionError(ResponseStatusException ex) {
        HttpStatus status = HttpStatus.resolve(ex.getStatusCode().value());
        if (status == null) status = HttpStatus.BAD_REQUEST;
        String msg = ex.getReason() == null ? AppErrorCode.A1688_AGENT_OFFLINE.getUserMessage() : ex.getReason();
        String code = status == HttpStatus.SERVICE_UNAVAILABLE
                ? AppErrorCode.A1688_AGENT_OFFLINE.getCode()
                : AppErrorCode.A1688_LOGIN_FAILED.getCode();
        return ResponseEntity.status(status).body(ApiResult.error(status.value(), code, msg));
    }

    @PostMapping("/crawl")
    public ResponseEntity<Map<String, Object>> crawl(@RequestBody(required = false) Alibaba1688CrawlRequest body) {
        try {
            return ResponseEntity.status(HttpStatus.ACCEPTED)
                    .body(ApiResult.ok(toJobDto(crawlService.triggerCrawl(body))));
        } catch (Alibaba1688CrawlConflictException ex) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(ApiResult.conflict(
                    409,
                    AppErrorCode.CRAWL_IN_PROGRESS.getUserMessage(),
                    AppErrorCode.CRAWL_IN_PROGRESS.getCode(),
                    toJobDto(ex.getExistingJob())
            ));
        }
    }

    @PostMapping("/sync")
    public ResponseEntity<Map<String, Object>> sync(@RequestBody(required = false) Alibaba1688CrawlRequest body) {
        if (body == null) body = new Alibaba1688CrawlRequest();
        body.setJobType("sync");
        return crawl(body);
    }

    @GetMapping("/crawl/{jobId}")
    public Map<String, Object> job(@PathVariable String jobId) {
        return ApiResult.ok(toJobDto(crawlService.getJob(jobId)));
    }

    @GetMapping("/crawl")
    public Map<String, Object> jobs(@RequestParam(required = false) Integer limit) {
        List<Alibaba1688CrawlJob> jobs = crawlService.listRecentJobs(
                Alibaba1688CrawlServiceImpl.clampJobListLimit(limit));
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Alibaba1688CrawlJob job : jobs) {
            rows.add(toJobDto(job));
        }
        return ApiResult.ok(Map.of("jobs", rows));
    }

    @GetMapping("/operational")
    public Map<String, Object> operational(
            @RequestParam(value = "storeId", required = false) String storeId,
            @RequestParam(value = "store_id", required = false) String storeIdSnake
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        String sid = storeId != null && !storeId.isBlank() ? storeId : storeIdSnake;
        return ApiResult.ok(operationalService.getOperational(tenantId, sid));
    }

    static Map<String, Object> toJobDto(Alibaba1688CrawlJob job) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", job.getId());
        m.put("jobId", job.getId());
        m.put("job_id", job.getId());
        m.put("tenantId", job.getTenantId());
        m.put("storeId", job.getStoreId());
        m.put("status", job.getStatus());
        m.put("jobType", job.getJobType());
        m.put("progress", job.getProgress());
        m.put("message", job.getMessage());
        m.put("errorCode", job.getErrorCode());
        m.put("error_code", job.getErrorCode());
        m.put("errorMessage", job.getErrorMessage());
        m.put("rowsCount", job.getRowsCount());
        m.put("startedAt", job.getStartedAt());
        m.put("finishedAt", job.getFinishedAt());
        m.put("createdAt", job.getCreatedAt());
        return m;
    }
}
