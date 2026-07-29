package com.crosshub.temu.controller;

import com.crosshub.common.ApiResult;
import com.crosshub.common.AppErrorCode;
import com.crosshub.temu.dto.CrawlRequest;
import com.crosshub.temu.entity.TemuCrawlJob;
import com.crosshub.temu.mapper.TemuMapper;
import com.crosshub.temu.service.CrawlConflictException;
import com.crosshub.temu.service.TemuCrawlService;
import com.crosshub.platform.service.PlatformDailySyncService;
import com.crosshub.tenant.service.DataScopeService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/temu")
public class TemuCrawlController {
    private final TemuCrawlService crawlService;
    private final TemuMapper temuMapper;
    private final PlatformDailySyncService dailySyncService;
    private final DataScopeService dataScopeService;

    public TemuCrawlController(
            TemuCrawlService crawlService,
            TemuMapper temuMapper,
            PlatformDailySyncService dailySyncService,
            DataScopeService dataScopeService
    ) {
        this.crawlService = crawlService;
        this.temuMapper = temuMapper;
        this.dailySyncService = dailySyncService;
        this.dataScopeService = dataScopeService;
    }

    @PostMapping("/crawl")
    public ResponseEntity<Map<String, Object>> trigger(@RequestBody(required = false) CrawlRequest request) {
        CrawlRequest body = request == null ? new CrawlRequest(null, null, null, null) : request;
        try {
            TemuCrawlJob job = crawlService.triggerCrawl(
                    body.reportTime(),
                    Boolean.TRUE.equals(body.seed()),
                    body.resolvedForce(),
                    body.resolvedRecordCooldown()
            );
            return ResponseEntity.status(HttpStatus.ACCEPTED).body(ApiResult.ok(temuMapper.toCrawlJobDto(job)));
        } catch (CrawlConflictException ex) {
            return ResponseEntity.status(HttpStatus.CONFLICT)
                    .body(ApiResult.conflict(
                            409,
                            AppErrorCode.CRAWL_IN_PROGRESS.getUserMessage(),
                            AppErrorCode.CRAWL_IN_PROGRESS.getCode(),
                            temuMapper.toCrawlJobDto(ex.getExistingJob())
                    ));
        }
    }

    @GetMapping("/crawl/{jobId}")
    public Map<String, Object> status(@PathVariable String jobId) {
        return ApiResult.ok(temuMapper.toCrawlJobDto(crawlService.getJob(jobId)));
    }

    /** 兼容：等同 {@code GET /api/platform/sync-status}（全平台日批状态） */
    @GetMapping("/sync-status")
    public Map<String, Object> syncStatus() {
        Long tenantId = dataScopeService.requireTenantId();
        return ApiResult.ok(dailySyncService.buildSyncStatus(tenantId));
    }
}
