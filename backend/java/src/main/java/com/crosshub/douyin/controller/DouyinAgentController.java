package com.crosshub.douyin.controller;

import com.crosshub.common.ApiResult;
import com.crosshub.douyin.service.DouyinOpsService;
import com.crosshub.security.AgentContext;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/agent/douyin")
public class DouyinAgentController {
    private final DouyinOpsService douyinOpsService;
    private final AgentContext agentContext;

    public DouyinAgentController(DouyinOpsService douyinOpsService, AgentContext agentContext) {
        this.douyinOpsService = douyinOpsService;
        this.agentContext = agentContext;
    }

    @PostMapping("/orders/ingest")
    public Map<String, Object> ingestOrders(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(douyinOpsService.ingestOrders(tenantId, body == null ? Map.of() : body));
    }

    @PostMapping("/products/ingest")
    public Map<String, Object> ingestProducts(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(douyinOpsService.ingestProducts(tenantId, body == null ? Map.of() : body));
    }

    @PostMapping("/compass/ingest")
    public Map<String, Object> ingestCompass(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(douyinOpsService.ingestCompass(tenantId, body == null ? Map.of() : body));
    }

    @PostMapping("/opportunity/ingest")
    public Map<String, Object> ingestOpportunity(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(douyinOpsService.ingestOpportunity(tenantId, body == null ? Map.of() : body));
    }

    @PostMapping("/compass-product-rank/ingest")
    public Map<String, Object> ingestCompassProductRank(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(douyinOpsService.ingestCompassProductRank(tenantId, body == null ? Map.of() : body));
    }

    @PostMapping("/issues/ingest")
    public Map<String, Object> ingestIssues(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(douyinOpsService.ingestIssues(tenantId, body == null ? Map.of() : body));
    }
}
