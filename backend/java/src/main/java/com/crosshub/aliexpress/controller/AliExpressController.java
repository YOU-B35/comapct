package com.crosshub.aliexpress.controller;

import com.crosshub.aliexpress.dto.AliExpressCrawlRequest;
import com.crosshub.aliexpress.dto.AliExpressHotBroadcastCreateRequest;
import com.crosshub.aliexpress.dto.AliExpressHotBroadcastReadRequest;
import com.crosshub.aliexpress.dto.AliExpressViolationPatchRequest;
import com.crosshub.aliexpress.entity.AliExpressCrawlJob;
import com.crosshub.aliexpress.service.AliExpressCrawlConflictException;
import com.crosshub.aliexpress.service.AliExpressCrawlService;
import com.crosshub.aliexpress.service.AliExpressHotBroadcastService;
import com.crosshub.aliexpress.service.AliExpressOperationalService;
import com.crosshub.aliexpress.service.AliExpressViolationService;
import com.crosshub.common.ApiResult;
import com.crosshub.common.AppErrorCode;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/aliexpress")
public class AliExpressController {
    private final AliExpressCrawlService crawlService;
    private final AliExpressOperationalService operationalService;
    private final AliExpressViolationService violationService;
    private final AliExpressHotBroadcastService hotBroadcastService;

    public AliExpressController(
            AliExpressCrawlService crawlService,
            AliExpressOperationalService operationalService,
            AliExpressViolationService violationService,
            AliExpressHotBroadcastService hotBroadcastService
    ) {
        this.crawlService = crawlService;
        this.operationalService = operationalService;
        this.violationService = violationService;
        this.hotBroadcastService = hotBroadcastService;
    }

    @PostMapping("/crawl")
    public ResponseEntity<Map<String, Object>> trigger(@RequestBody(required = false) AliExpressCrawlRequest request) {
        AliExpressCrawlRequest body = request == null ? new AliExpressCrawlRequest(null, null, null, null) : request;
        try {
            return ResponseEntity.status(HttpStatus.ACCEPTED).body(ApiResult.ok(toJobDto(crawlService.triggerCrawl(body))));
        } catch (AliExpressCrawlConflictException ex) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(ApiResult.conflict(
                    409,
                    AppErrorCode.CRAWL_IN_PROGRESS.getUserMessage(),
                    AppErrorCode.CRAWL_IN_PROGRESS.getCode(),
                    toJobDto(ex.getExistingJob())
            ));
        }
    }

    @GetMapping("/crawl/{jobId}")
    public Map<String, Object> status(@PathVariable String jobId) {
        return ApiResult.ok(toJobDto(crawlService.getJob(jobId)));
    }

    @GetMapping("/jobs")
    public Map<String, Object> listJobs(@RequestParam(value = "limit", required = false) Integer limit) {
        List<AliExpressCrawlJob> jobs = crawlService.listRecentJobs(limit == null ? 20 : limit);
        List<Map<String, Object>> rows = new ArrayList<>();
        for (AliExpressCrawlJob job : jobs) {
            Map<String, Object> dto = toJobDto(job);
            dto.put("triggered_by", job.getTriggeredBy());
            rows.add(dto);
        }
        return ApiResult.ok(Map.of("jobs", rows));
    }

    @PostMapping("/violations/sync")
    public ResponseEntity<Map<String, Object>> syncViolations(@RequestBody(required = false) Map<String, Object> body) {
        boolean force = body != null && Boolean.TRUE.equals(body.get("force"));
        boolean recordCooldown = body == null || body.get("record_cooldown") == null || Boolean.TRUE.equals(body.get("record_cooldown"));
        try {
            return ResponseEntity.status(HttpStatus.ACCEPTED).body(ApiResult.ok(toJobDto(crawlService.triggerViolationSync(force, recordCooldown))));
        } catch (AliExpressCrawlConflictException ex) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(ApiResult.conflict(
                    409,
                    AppErrorCode.CRAWL_IN_PROGRESS.getUserMessage(),
                    AppErrorCode.CRAWL_IN_PROGRESS.getCode(),
                    toJobDto(ex.getExistingJob())
            ));
        }
    }

    @GetMapping("/operational")
    public Map<String, Object> operational(@RequestParam(value = "store_id", required = false) String storeId) {
        return ApiResult.ok(operationalService.operational(storeId));
    }

    @GetMapping("/orders/today")
    public Map<String, Object> orders(@RequestParam(value = "store_id", required = false) String storeId) {
        return ApiResult.ok(operationalService.todayOrders(storeId));
    }

    @GetMapping("/violations")
    public Map<String, Object> violations(@RequestParam(value = "store_id", required = false) String storeId) {
        return ApiResult.ok(operationalService.violations(storeId));
    }

    @PatchMapping("/violations/{id}")
    public Map<String, Object> patchViolation(@PathVariable String id, @RequestBody(required = false) AliExpressViolationPatchRequest request) {
        return ApiResult.ok(violationService.patch(id, request == null ? new AliExpressViolationPatchRequest(null, null) : request));
    }

    @GetMapping("/hot-broadcasts")
    public Map<String, Object> broadcasts(@RequestParam(value = "store_id", required = false) String storeId) {
        return ApiResult.ok(hotBroadcastService.list(storeId));
    }

    @PostMapping("/hot-broadcasts")
    public Map<String, Object> createBroadcast(@RequestBody AliExpressHotBroadcastCreateRequest request) {
        return ApiResult.ok(hotBroadcastService.create(request));
    }

    @PostMapping("/hot-broadcasts/{id}/read")
    public Map<String, Object> readBroadcast(@PathVariable String id, @RequestBody(required = false) AliExpressHotBroadcastReadRequest request) {
        return ApiResult.ok(hotBroadcastService.markRead(
                id,
                request == null ? new AliExpressHotBroadcastReadRequest("", "") : request
        ));
    }

    private Map<String, Object> toJobDto(AliExpressCrawlJob job) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("job_id", job.getId());
        row.put("status", job.getStatus());
        row.put("mode", job.getMode());
        row.put("scope", job.getScope());
        row.put("report_time", job.getReportTime());
        row.put("shops_count", job.getShopsCount());
        row.put("rows_count", job.getRowsCount());
        row.put("orders_count", job.getOrdersCount());
        row.put("violations_count", job.getViolationsCount());
        row.put("products_count", job.getProductsCount());
        row.put("error_code", job.getErrorCode());
        row.put("error_message", job.getErrorMessage());
        row.put("started_at", job.getStartedAt());
        row.put("finished_at", job.getFinishedAt());
        row.put("created_at", job.getCreatedAt());
        return row;
    }
}

