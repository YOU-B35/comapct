package com.crosshub.amazon.controller;

import com.crosshub.amazon.dto.*;
import com.crosshub.amazon.entity.AmazonSyncJob;
import com.crosshub.amazon.service.*;
import com.crosshub.common.ApiResult;
import com.crosshub.common.AppErrorCode;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/amazon")
public class AmazonController {
    private final AmazonSyncService syncService;
    private final AmazonOperationalService operationalService;
    private final AmazonWriteService writeService;
    private final AmazonZiniaoService ziniaoService;
    private final DataScopeService dataScopeService;
    private final ObjectMapper objectMapper;

    public AmazonController(
            AmazonSyncService syncService,
            AmazonOperationalService operationalService,
            AmazonWriteService writeService,
            AmazonZiniaoService ziniaoService,
            DataScopeService dataScopeService,
            ObjectMapper objectMapper
    ) {
        this.syncService = syncService;
        this.operationalService = operationalService;
        this.writeService = writeService;
        this.ziniaoService = ziniaoService;
        this.dataScopeService = dataScopeService;
        this.objectMapper = objectMapper;
    }

    @PostMapping("/sync")
    public ResponseEntity<Map<String, Object>> triggerSync(@RequestBody(required = false) AmazonSyncRequest request) {
        AmazonSyncRequest body = request == null ? new AmazonSyncRequest("account_health", null, null, null) : request;
        try {
            return ResponseEntity.status(HttpStatus.ACCEPTED).body(ApiResult.ok(syncService.triggerSync(body)));
        } catch (AmazonSyncConflictException ex) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(ApiResult.conflict(
                    409,
                    AppErrorCode.AMAZON_SYNC_IN_PROGRESS.getUserMessage(),
                    AppErrorCode.AMAZON_SYNC_IN_PROGRESS.getCode(),
                    toJobDto(ex.getExistingJob())
            ));
        }
    }

    @GetMapping("/sync/{jobId}")
    public Map<String, Object> getSyncJob(@PathVariable String jobId) {
        return ApiResult.ok(toJobDto(syncService.getJob(jobId)));
    }

    @GetMapping("/sync-jobs")
    public Map<String, Object> listSyncJobs(@RequestParam(value = "limit", required = false) Integer limit) {
        Long tenantId = dataScopeService.requireTenantId();
        return ApiResult.ok(syncService.listRecentJobsForTenant(tenantId, limit));
    }

    @GetMapping("/sync-versions")
    public Map<String, Object> syncVersions(
            @RequestParam(value = "store_id", required = false) String storeId,
            @RequestParam(value = "scope", required = false) String scope,
            @RequestParam(value = "limit", defaultValue = "20") int limit
    ) {
        return ApiResult.ok(operationalService.syncVersions(storeId, scope, limit));
    }

    @GetMapping("/daily")
    public Map<String, Object> daily(
            @RequestParam(value = "store_id", required = false) String storeId,
            @RequestParam(value = "sync_version_id", required = false) String syncVersionId
    ) {
        return ApiResult.ok(operationalService.daily(storeId, syncVersionId));
    }

    @GetMapping("/insights")
    public Map<String, Object> insights(
            @RequestParam(value = "store_id", required = false) String storeId,
            @RequestParam(value = "sync_version_id", required = false) String syncVersionId
    ) {
        return ApiResult.ok(operationalService.insights(storeId, syncVersionId));
    }

    @GetMapping("/sp-api/status")
    public Map<String, Object> spApiStatus() {
        return ApiResult.ok(operationalService.spApiStatus());
    }

    @GetMapping("/integration/status")
    public Map<String, Object> integrationStatus() {
        return ApiResult.ok(operationalService.integrationStatus());
    }

    @PatchMapping("/daily/messages/{id}")
    public Map<String, Object> replyMessage(@PathVariable String id, @RequestBody(required = false) AmazonMessagePatchRequest request) {
        AmazonMessagePatchRequest body = request == null ? new AmazonMessagePatchRequest("", "") : request;
        return ApiResult.ok(writeService.replyMessage(id, body.templateId(), body.note()));
    }

    @PatchMapping("/daily/reviews/{id}")
    public Map<String, Object> handleReview(@PathVariable String id, @RequestBody(required = false) AmazonReviewPatchRequest request) {
        return ApiResult.ok(writeService.handleReview(id, request == null ? "" : request.note()));
    }

    @PatchMapping("/daily/cases/{id}")
    public Map<String, Object> readCase(@PathVariable String id, @RequestBody(required = false) AmazonCasePatchRequest request) {
        return ApiResult.ok(writeService.acknowledgeCase(id, request == null ? "" : request.note()));
    }

    @PatchMapping("/outbound/{id}/ship")
    public Map<String, Object> shipOutbound(@PathVariable String id, @RequestBody(required = false) AmazonOutboundShipPatchRequest request) {
        return ApiResult.ok(writeService.shipOutbound(id, request == null ? "" : request.trackingNo()));
    }

    @GetMapping("/write/audit")
    public Map<String, Object> listWriteAudit(
            @RequestParam(value = "item_id", required = false) String itemId,
            @RequestParam(value = "limit", defaultValue = "20") int limit
    ) {
        return ApiResult.ok(writeService.listWriteAudit(itemId, limit));
    }

    @GetMapping("/write/{jobId}")
    public Map<String, Object> getWriteJob(@PathVariable String jobId) {
        return ApiResult.ok(writeService.getWriteJob(jobId));
    }

    @PostMapping("/ziniao/discover")
    public Map<String, Object> discover() {
        return ApiResult.ok(ziniaoService.triggerDiscover());
    }

    @GetMapping("/ziniao/discover/{jobId}")
    public Map<String, Object> discoverStatus(@PathVariable String jobId) {
        return ApiResult.ok(ziniaoService.getDiscoverJob(jobId));
    }

    @GetMapping("/ziniao/candidates")
    public Map<String, Object> listCandidates() {
        return ApiResult.ok(ziniaoService.listCandidates());
    }

    @PostMapping("/ziniao/bind")
    public Map<String, Object> bind(@RequestBody ZiniaoBindRequest request) {
        return ApiResult.ok(ziniaoService.bindStores(request));
    }

    private Map<String, Object> toJobDto(AmazonSyncJob job) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("job_id", job.getId());
        row.put("platform_account_id", job.getPlatformAccountId());
        row.put("agent_task_id", job.getAgentTaskId());
        row.put("scope", job.getScope());
        row.put("status", job.getStatus());
        row.put("mode", job.getMode());
        row.put("error_code", job.getErrorCode() == null ? "" : job.getErrorCode());
        row.put("error_message", job.getErrorMessage() == null ? "" : job.getErrorMessage());
        row.put("created_at", job.getCreatedAt() == null ? "" : job.getCreatedAt());
        row.put("started_at", job.getStartedAt() == null ? "" : job.getStartedAt());
        row.put("finished_at", job.getFinishedAt() == null ? "" : job.getFinishedAt());
        try {
            row.put("result_summary", objectMapper.readValue(job.getResultSummary() == null ? "{}" : job.getResultSummary(), new TypeReference<Map<String, Object>>() {}));
        } catch (Exception ex) {
            row.put("result_summary", Map.of());
        }
        return row;
    }
}
