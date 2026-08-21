package com.crosshub.agent.controller;

import com.crosshub.agent.dto.AgentHeartbeatRequest;
import com.crosshub.agent.dto.AgentRegisterRequest;
import com.crosshub.agent.dto.AgentTaskCompleteRequest;
import com.crosshub.agent.service.AgentService;
import com.crosshub.amazon.dto.AmazonSyncRequest;
import com.crosshub.amazon.entity.AmazonSyncJob;
import com.crosshub.amazon.service.AmazonSyncConflictException;
import com.crosshub.amazon.service.AmazonSyncService;
import com.crosshub.auth.entity.AppUser;
import com.crosshub.auth.repository.AppUserRepository;
import com.crosshub.common.ApiResult;
import com.crosshub.common.AppErrorCode;
import com.crosshub.common.SqliteBusy;
import com.crosshub.platform.dto.StorePayload;
import com.crosshub.platform.entity.PlatformAccount;
import com.crosshub.platform.repository.PlatformAccountRepository;
import com.crosshub.platform.service.PlatformAccountService;
import com.crosshub.security.AgentContext;
import com.crosshub.temu.service.TemuAgentService;
import com.crosshub.temu.service.TemuSellerSessionService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.*;

@RestController
@RequestMapping("/api/agent")
public class AgentController {
    private final AgentService agentService;
    private final TemuAgentService temuAgentService;
    private final TemuSellerSessionService sellerSessionService;
    private final AgentContext agentContext;
    private final AppUserRepository appUserRepository;
    private final PlatformAccountRepository platformAccountRepository;
    private final PlatformAccountService platformAccountService;
    private final AmazonSyncService amazonSyncService;

    public AgentController(AgentService agentService, TemuAgentService temuAgentService,
                           TemuSellerSessionService sellerSessionService, AgentContext agentContext,
                           AppUserRepository appUserRepository, PlatformAccountRepository platformAccountRepository,
                           PlatformAccountService platformAccountService,
                           AmazonSyncService amazonSyncService) {
        this.agentService = agentService;
        this.temuAgentService = temuAgentService;
        this.sellerSessionService = sellerSessionService;
        this.agentContext = agentContext;
        this.appUserRepository = appUserRepository;
        this.platformAccountRepository = platformAccountRepository;
        this.platformAccountService = platformAccountService;
        this.amazonSyncService = amazonSyncService;
    }

    @PostMapping("/register")
    public Map<String, Object> register(@RequestBody AgentRegisterRequest request) {
        return Map.of("success", true, "data", agentService.registerAgent(request.name()));
    }

    @PostMapping("/setup")
    public Map<String, Object> setup(@RequestBody(required = false) AgentRegisterRequest request) {
        String name = request == null ? null : request.name();
        return Map.of("success", true, "data", agentService.setupLocalAgent(name));
    }

    @GetMapping("/nodes")
    public Map<String, Object> nodes() {
        List<Map<String, Object>> rows = agentService.listAgents();
        return Map.of("success", true, "data", rows);
    }

    @PostMapping("/heartbeat")
    public Map<String, Object> heartbeat(@RequestBody AgentHeartbeatRequest request) {
        boolean online = request != null && Boolean.TRUE.equals(request.ziniaoOnline());
        return Map.of("success", true, "data", agentService.heartbeat(online));
    }

    @GetMapping("/tasks")
    public Map<String, Object> pollTasks() {
        return Map.of("success", true, "data", agentService.pollTasks());
    }

    @PostMapping("/tasks/{taskId}/complete")
    public Map<String, Object> completeTask(@PathVariable String taskId, @RequestBody AgentTaskCompleteRequest request) {
        return Map.of(
                "success", true,
                "data", agentService.completeTask(
                        taskId,
                        request.status(),
                        request.result(),
                        request.errorCode(),
                        request.errorMessage()
                )
        );
    }

    /**
     * Helper 面板：仅返回当前 Agent Token 所属租户（机器绑定后不应再看到别的企业）。
     */
    @GetMapping("/tenants")
    public Map<String, Object> tenants() {
        Long agentTenantId = agentContext.tenantId();
        if (agentTenantId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未绑定租户");
        }
        List<AppUser> admins = appUserRepository.findAll().stream()
                .filter(u -> "admin".equals(u.getRole()))
                .filter(u -> agentTenantId.equals(u.getTenantId()))
                .toList();
        List<Map<String, Object>> rows = new ArrayList<>();
        if (!admins.isEmpty()) {
            AppUser u = admins.get(0);
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("tenant_id", u.getTenantId());
            row.put("username", u.getUsername());
            row.put("enterprise", u.getEnterprise());
            row.put("nickname", u.getNickname());
            rows.add(row);
        } else {
            // 无 admin 行时仍返回本租户，避免面板显示「无租户/未绑定」
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("tenant_id", agentTenantId);
            row.put("username", "");
            row.put("enterprise", "当前企业");
            row.put("nickname", "Tenant #" + agentTenantId);
            rows.add(row);
        }
        return Map.of("success", true, "data", rows);
    }

    /** Helper 面板：获取指定租户下所有平台的绑定账号。 */
    @GetMapping("/platform-accounts")
    public Map<String, Object> platformAccounts(@RequestParam(value = "tenant_id") Long tenantId) {
        requireAgentTenant(tenantId);
        List<PlatformAccount> accounts = platformAccountRepository.findByTenantIdOrderByBoundAtDesc(tenantId);
        Map<String, List<Map<String, Object>>> grouped = new LinkedHashMap<>();
        for (PlatformAccount pa : accounts) {
            String platform = pa.getPlatform() == null ? "unknown" : pa.getPlatform().toLowerCase();
            grouped.computeIfAbsent(platform, k -> new ArrayList<>()).add(Map.of(
                    "id", pa.getId(),
                    "store_name", pa.getStoreName() == null ? "" : pa.getStoreName(),
                    "account", pa.getAccount() == null ? "" : pa.getAccount(),
                    "platform", platform,
                    "external_shop_id", pa.getExternalShopId() == null ? "" : pa.getExternalShopId()
            ));
        }
        return Map.of("success", true, "data", grouped);
    }

    /**
     * Helper 面板：在指定租户下绑定店铺（与 Boss「账户绑定」写同一张 platform_account 表）。
     * 密码可空（Temu/速卖通等走浏览器登录）。
     */
    @PostMapping("/platform-accounts")
    public Map<String, Object> bindPlatformAccount(@RequestBody Map<String, Object> body) {
        Long tenantId = parseLong(body.get("tenant_id"));
        if (tenantId == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "缺少 tenant_id");
        }
        requireAgentTenant(tenantId);
        String platform = str(body.get("platform"));
        String storeName = str(body.get("store_name"));
        if (storeName.isBlank()) storeName = str(body.get("storeName"));
        String account = str(body.get("account"));
        String password = str(body.get("password"));
        String externalShopId = str(body.get("external_shop_id"));
        if (externalShopId.isBlank()) externalShopId = str(body.get("externalShopId"));
        String companyName = str(body.get("company_name"));
        if (companyName.isBlank()) companyName = str(body.get("companyName"));
        String id = str(body.get("id"));

        Map<String, Object> data = platformAccountService.upsertForTenant(
                tenantId,
                new StorePayload(id.isBlank() ? null : id, platform, storeName, account, password,
                        companyName.isBlank() ? null : companyName, externalShopId.isBlank() ? null : externalShopId,
                        "browser", null),
                true
        );
        return Map.of("success", true, "message", "店铺绑定成功", "data", data);
    }

    /** Helper 面板：解绑店铺。 */
    @DeleteMapping("/platform-accounts/{id}")
    public Map<String, Object> deletePlatformAccount(
            @PathVariable String id,
            @RequestParam(value = "tenant_id") Long tenantId
    ) {
        requireAgentTenant(tenantId);
        Map<String, Object> data = platformAccountService.deleteForTenant(tenantId, id);
        return Map.of("success", true, "message", "店铺已解除绑定", "data", data);
    }

    private void requireAgentTenant(Long tenantId) {
        Long agentTenantId = agentContext.tenantId();
        if (agentTenantId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未绑定租户");
        }
        if (tenantId == null || !agentTenantId.equals(tenantId)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "只能操作本机已绑定的企业");
        }
    }

    private static Long parseLong(Object value) {
        if (value == null) return null;
        if (value instanceof Number n) return n.longValue();
        String s = String.valueOf(value).trim();
        if (s.isBlank()) return null;
        try {
            return Long.parseLong(s);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static String str(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    /** Helper 本地面板拉取 Temu 卖家账号列表（可指定 tenant_id，默认用 Agent 绑定租户）。 */
    @GetMapping("/temu/seller-sessions")
    public Map<String, Object> temuSellerSessions(
            @RequestParam(value = "tenant_id", required = false) Long tenantId) {
        Long tid = tenantId != null ? tenantId : agentContext.tenantId();
        return Map.of("success", true, "data", sellerSessionService.listSellerSessions(tid));
    }

    @PostMapping("/temu/ingest")
    public Map<String, Object> ingestTemu(@RequestBody Map<String, Object> payload) {
        Long tenantId = agentContext.tenantId();
        if (tenantId == null) {
            throw new org.springframework.web.server.ResponseStatusException(
                    org.springframework.http.HttpStatus.UNAUTHORIZED,
                    "Agent 未认证"
            );
        }
        return Map.of("success", true, "data",
                SqliteBusy.retry(() -> temuAgentService.ingestFromAgent(tenantId, payload)));
    }

    /** Agent：登录窗口内会话就绪时即时上报，供网站状态栏刷新。 */
    @PostMapping("/temu/session-snapshot")
    public Map<String, Object> reportTemuSessionSnapshot(@RequestBody Map<String, Object> payload) {
        Long tenantId = agentContext.tenantId();
        if (tenantId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未认证");
        }
        return Map.of("success", true, "data", temuAgentService.reportSessionSnapshot(tenantId, payload));
    }

    @PostMapping("/amazon/sync")
    public ResponseEntity<Map<String, Object>> triggerAmazonSync(@RequestBody(required = false) AmazonSyncRequest request) {
        Long tenantId = agentContext.tenantId();
        if (tenantId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未认证");
        }
        AmazonSyncRequest body = request == null
                ? new AmazonSyncRequest("account_health", null, null, null)
                : request;
        try {
            return ResponseEntity.ok(Map.of("success", true, "data", amazonSyncService.triggerSyncForTenant(tenantId, body)));
        } catch (AmazonSyncConflictException ex) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(ApiResult.conflict(
                    409,
                    AppErrorCode.AMAZON_SYNC_IN_PROGRESS.getUserMessage(),
                    AppErrorCode.AMAZON_SYNC_IN_PROGRESS.getCode(),
                    toJobDto(ex.getExistingJob())
            ));
        }
    }

    @GetMapping("/amazon/sync-jobs")
    public Map<String, Object> listAmazonSyncJobs(
            @RequestParam(value = "tenant_id", required = false) Long tenantId,
            @RequestParam(value = "limit", required = false) Integer limit
    ) {
        Long resolvedTenantId = tenantId != null ? tenantId : agentContext.tenantId();
        if (resolvedTenantId == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "缺少 tenant_id");
        }
        return Map.of("success", true, "data", amazonSyncService.listRecentJobsForTenant(resolvedTenantId, limit));
    }

    private Map<String, Object> toJobDto(AmazonSyncJob job) {
        if (job == null) {
            return Map.of();
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("job_id", job.getId());
        out.put("platform_account_id", job.getPlatformAccountId());
        out.put("agent_task_id", job.getAgentTaskId());
        out.put("scope", job.getScope());
        out.put("status", job.getStatus());
        out.put("mode", job.getMode());
        out.put("error_code", job.getErrorCode());
        out.put("error_message", job.getErrorMessage());
        out.put("created_at", job.getCreatedAt());
        out.put("started_at", job.getStartedAt());
        out.put("finished_at", job.getFinishedAt());
        return out;
    }
}
