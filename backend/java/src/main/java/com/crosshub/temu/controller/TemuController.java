package com.crosshub.temu.controller;



import com.crosshub.common.ApiResult;

import com.crosshub.platform.entity.PlatformAccount;

import com.crosshub.temu.entity.TemuShop;

import com.crosshub.temu.mapper.TemuMapper;

import com.crosshub.platform.repository.PlatformAccountRepository;

import com.crosshub.security.AuthContext;

import com.crosshub.temu.dto.TemuCompetitorDiscoverRequest;
import com.crosshub.temu.dto.TemuSkuCostUpsertRequest;
import com.crosshub.temu.service.TemuCompetitorService;
import com.crosshub.temu.service.TemuSkuCostService;
import com.crosshub.temu.service.TemuAgentService;
import com.crosshub.temu.service.TemuHotBroadcastService;
import com.crosshub.temu.service.TemuOperationalService;
import com.crosshub.temu.service.TemuRestockStatusService;
import com.crosshub.temu.service.TemuSessionService;

import org.springframework.web.bind.annotation.*;



import java.util.HashMap;

import java.util.LinkedHashMap;

import java.util.List;

import java.util.Map;



@RestController

@RequestMapping("/api/temu")

public class TemuController {

    private final TemuOperationalService operationalService;

    private final TemuRestockStatusService restockStatusService;

    private final TemuHotBroadcastService hotBroadcastService;

    private final TemuSessionService sessionService;

    private final TemuCompetitorService competitorService;

    private final TemuMapper temuMapper;

    private final PlatformAccountRepository platformAccountRepository;

    private final AuthContext authContext;
    private final TemuAgentService temuAgentService;
    private final TemuSkuCostService skuCostService;



    public TemuController(

            TemuOperationalService operationalService,

            TemuRestockStatusService restockStatusService,

            TemuHotBroadcastService hotBroadcastService,

            TemuSessionService sessionService,

            TemuCompetitorService competitorService,

            TemuMapper temuMapper,

            PlatformAccountRepository platformAccountRepository,

            AuthContext authContext,
            TemuAgentService temuAgentService,
            TemuSkuCostService skuCostService

    ) {

        this.operationalService = operationalService;

        this.restockStatusService = restockStatusService;

        this.hotBroadcastService = hotBroadcastService;

        this.sessionService = sessionService;

        this.competitorService = competitorService;

        this.temuMapper = temuMapper;

        this.platformAccountRepository = platformAccountRepository;

        this.authContext = authContext;
        this.temuAgentService = temuAgentService;
        this.skuCostService = skuCostService;

    }



    @GetMapping("/shops")

    public Map<String, Object> shops() {

        Map<String, PlatformAccount> boundByExternalShopId = loadBoundTemuAccountsByExternalShopId();

        List<Map<String, Object>> items = operationalService.shops().stream()

                .map(shop -> enrichShopDto(shop, boundByExternalShopId))

                .toList();

        return ApiResult.ok(items);

    }



    @GetMapping("/session")
    public Map<String, Object> session() {
        return ApiResult.ok(sessionService.getSessionStatus());
    }

    @GetMapping("/integration/status")
    public Map<String, Object> integrationStatus() {
        Long tenantId = authContext.tenantId();
        return ApiResult.ok(temuAgentService.integrationStatus(tenantId));
    }

    /**
     * Temu 会话诊断：用于排查“需要商家后台登录/刷新数据跳登录”等问题。
     * 返回 tenant 维度的 session 快照 + 最近登录/探测 agent_task 记录。
     */
    @GetMapping("/session/debug")
    public Map<String, Object> sessionDebug() {
        Long tenantId = authContext.tenantId();
        return ApiResult.ok(temuAgentService.sessionDebug(tenantId));
    }

    @PostMapping("/login/open")
    public Map<String, Object> openLogin(@RequestBody(required = false) Map<String, Object> body) {
        String platformAccountId = body == null || body.get("platform_account_id") == null
                ? ""
                : String.valueOf(body.get("platform_account_id"));
        return ApiResult.ok(sessionService.openLoginWindow(platformAccountId));
    }

    @PostMapping("/frontend-login/open")
    public Map<String, Object> openFrontendLogin(@RequestBody(required = false) Map<String, Object> body) {
        String url = body == null || body.get("url") == null ? null : String.valueOf(body.get("url"));
        return ApiResult.ok(sessionService.openFrontendLoginWindow(url));
    }

    @PostMapping("/competitors/discover")
    public Map<String, Object> discoverCompetitors(@RequestBody(required = false) TemuCompetitorDiscoverRequest request) {
        return ApiResult.ok(competitorService.discoverCandidates(request));
    }

    @PostMapping("/sku-costs")
    public Map<String, Object> upsertSkuCosts(@RequestBody TemuSkuCostUpsertRequest request) {
        Long tenantId = authContext.tenantId();
        skuCostService.upsertCosts(tenantId, request == null ? List.of() : request.items());
        return ApiResult.ok(Map.of(
                "updated", request == null || request.items() == null ? 0 : request.items().size(),
                "tenant_id", tenantId
        ));
    }

    @GetMapping("/operational")

    public Map<String, Object> operational(

            @RequestParam(value = "shop_id", required = false) String shopId,

            @RequestParam(value = "report_time", required = false) String reportTime

    ) {

        return operationalService.operationalBundle(shopId, reportTime);

    }



    @GetMapping("/trend")

    public Map<String, Object> trend(

            @RequestParam(value = "shop_id", required = false) String shopId,

            @RequestParam(value = "days", defaultValue = "7") int days

    ) {

        return operationalService.salesTrend(shopId, days);

    }



    @GetMapping("/restock-status")

    public Map<String, Object> listRestockStatus() {

        return ApiResult.ok(restockStatusService.listAll());

    }



    @PutMapping("/restock-status")

    public Map<String, Object> upsertRestockStatus(@RequestBody Map<String, Object> payload) {

        return ApiResult.ok(restockStatusService.upsert(payload));

    }



    @GetMapping("/hot-broadcasts")

    public Map<String, Object> listHotBroadcasts() {

        return ApiResult.ok(hotBroadcastService.listBroadcasts());

    }



    @PostMapping("/hot-broadcasts")

    public Map<String, Object> createHotBroadcast(@RequestBody Map<String, Object> payload) {

        return ApiResult.ok(hotBroadcastService.createBroadcast(payload));

    }



    @PostMapping("/hot-broadcasts/{id}/read")

    public Map<String, Object> markHotBroadcastRead(

            @PathVariable String id,

            @RequestBody(required = false) Map<String, Object> payload

    ) {

        return ApiResult.ok(hotBroadcastService.markRead(id, payload == null ? Map.of() : payload));

    }



    private Map<String, PlatformAccount> loadBoundTemuAccountsByExternalShopId() {

        Long tenantId = authContext.tenantId();

        if (tenantId == null) {

            return Map.of();

        }

        List<PlatformAccount> bound = platformAccountRepository.findByTenantIdAndPlatformOrderByBoundAtDesc(tenantId, "temu");

        Map<String, PlatformAccount> map = new HashMap<>();

        for (PlatformAccount account : bound) {

            String externalShopId = account.getExternalShopId();

            if (externalShopId == null || externalShopId.isBlank()) {

                continue;

            }

            map.put(externalShopId.trim(), account);

        }

        return map;

    }



    private Map<String, Object> enrichShopDto(TemuShop shop, Map<String, PlatformAccount> boundByExternalShopId) {

        Map<String, Object> dto = new LinkedHashMap<>(temuMapper.toShopDto(shop));

        PlatformAccount account = boundByExternalShopId.get(shop.getShopId());

        if (account != null) {

            dto.put("platform_account_id", account.getId());

            dto.put("bound_store_name", account.getStoreName());

            dto.put("external_shop_id", account.getExternalShopId());

        }

        return dto;

    }

}


