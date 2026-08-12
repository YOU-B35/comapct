package com.crosshub.temu.controller;

import com.crosshub.common.ApiResult;
import com.crosshub.common.AppErrorCode;
import com.crosshub.security.AuthContext;
import com.crosshub.temu.dto.CrawlRequest;
import com.crosshub.temu.entity.TemuCrawlJob;
import com.crosshub.temu.mapper.TemuMapper;
import com.crosshub.temu.service.TemuAgentService;
import com.crosshub.temu.service.TemuCrawlService;
import com.crosshub.temu.service.TemuSyncLimitService;
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
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/temu")
public class TemuSyncController {
    private final TemuSyncLimitService syncLimitService;
    private final TemuCrawlService crawlService;
    private final TemuAgentService temuAgentService;
    private final TemuMapper temuMapper;
    private final DataScopeService dataScopeService;
    private final AuthContext authContext;

    public TemuSyncController(
            TemuSyncLimitService syncLimitService,
            TemuCrawlService crawlService,
            TemuAgentService temuAgentService,
            TemuMapper temuMapper,
            DataScopeService dataScopeService,
            AuthContext authContext
    ) {
        this.syncLimitService = syncLimitService;
        this.crawlService = crawlService;
        this.temuAgentService = temuAgentService;
        this.temuMapper = temuMapper;
        this.dataScopeService = dataScopeService;
        this.authContext = authContext;
    }

    @PostMapping("/sync/enqueue")
    public ResponseEntity<Map<String, Object>> enqueueSync(@RequestBody(required = false) CrawlRequest request) {
        CrawlRequest body = request == null ? new CrawlRequest(null, null, null, null) : request;
        Long tenantId = dataScopeService.requireTenantId();
        Long userId = requireUserId();

        TemuCrawlJob job = syncLimitService.runWithEnqueueGate(tenantId, userId, () ->
                crawlService.enqueueUserSync(
                        body.reportTime(),
                        Boolean.TRUE.equals(body.seed()),
                        body.resolvedForce(),
                        body.resolvedRecordCooldown()
                )
        );
        Map<String, Object> data = new LinkedHashMap<>(temuMapper.toCrawlJobDto(job));
        data.putIfAbsent("job_id", job.getId());
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(ApiResult.ok(data));
    }

    @PostMapping("/login/enqueue")
    public Map<String, Object> enqueueLogin(@RequestBody(required = false) Map<String, Object> body) {
        Long tenantId = dataScopeService.requireTenantId();
        Long userId = requireUserId();

        String platformAccountId = null;
        if (body != null && body.get("platform_account_id") != null) {
            platformAccountId = String.valueOf(body.get("platform_account_id")).trim();
            if (platformAccountId.isEmpty() || "null".equalsIgnoreCase(platformAccountId)) {
                platformAccountId = null;
            }
        }
        final String accountId = platformAccountId;
        Map<String, Object> queued = syncLimitService.runWithLoginEnqueueGate(tenantId, userId, () ->
                temuAgentService.enqueueLoginOpenForUser(tenantId, userId, accountId)
        );
        return ApiResult.ok(queued);
    }

    @GetMapping("/jobs")
    public Map<String, Object> listJobs(@RequestParam(value = "limit", required = false) Integer limit) {
        List<TemuCrawlJob> jobs = crawlService.listRecentJobs(limit == null ? 20 : limit);
        List<Map<String, Object>> rows = new ArrayList<>();
        for (TemuCrawlJob job : jobs) {
            rows.add(temuMapper.toCrawlJobDto(job));
        }
        return ApiResult.ok(Map.of("jobs", rows));
    }

    @GetMapping("/jobs/{id}")
    public Map<String, Object> jobStatus(@PathVariable("id") String id) {
        TemuCrawlJob job = crawlService.getJob(id);
        Map<String, Object> data = new LinkedHashMap<>(temuMapper.toCrawlJobDto(job));
        Object errMsg = data.get("error_message");
        data.put("msg", errMsg == null ? "" : errMsg);
        Map<String, Object> shops = new LinkedHashMap<>();
        shops.put("shops_count", job.getShopsCount() == null ? 0 : job.getShopsCount());
        shops.put("rows_count", job.getRowsCount() == null ? 0 : job.getRowsCount());
        data.put("shops", shops);
        return ApiResult.ok(data);
    }

    private Long requireUserId() {
        Long userId = authContext.userId();
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, AppErrorCode.AUTH_MISSING_USER.getUserMessage());
        }
        return userId;
    }
}
