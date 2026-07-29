package com.crosshub.platform.controller;

import com.crosshub.common.ApiResult;
import com.crosshub.platform.service.PlatformDailySyncService;
import com.crosshub.tenant.service.DataScopeService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/platform")
public class PlatformSyncStatusController {
    private final PlatformDailySyncService dailySyncService;
    private final DataScopeService dataScopeService;

    public PlatformSyncStatusController(
            PlatformDailySyncService dailySyncService,
            DataScopeService dataScopeService
    ) {
        this.dailySyncService = dailySyncService;
        this.dataScopeService = dataScopeService;
    }

    /** 打开应用展示：全平台日批计划 + 各平台最近同步结果/错误 */
    @GetMapping("/sync-status")
    public Map<String, Object> syncStatus() {
        Long tenantId = dataScopeService.requireTenantId();
        return ApiResult.ok(dailySyncService.buildSyncStatus(tenantId));
    }

    /**
     * 运维手动模拟日批下发（等同 09:30 调度入队）。
     * force=true 时忽略「今日已跑过」跳过，强制再入队。
     */
    @PostMapping("/daily-sync/run")
    public Map<String, Object> runDailySync(
            @RequestParam(value = "force", defaultValue = "false") boolean force,
            @RequestParam(value = "scope", defaultValue = "tenant") String scope
    ) {
        Long tenantId = dataScopeService.requireTenantId();
        if ("all".equalsIgnoreCase(scope)) {
            return ApiResult.ok(dailySyncService.runDailySyncNow(force));
        }
        return ApiResult.ok(dailySyncService.enqueueDailySyncForTenant(tenantId, force));
    }
}
