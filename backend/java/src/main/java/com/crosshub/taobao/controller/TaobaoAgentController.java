package com.crosshub.taobao.controller;

import com.crosshub.common.ApiResult;
import com.crosshub.common.SqliteBusy;
import com.crosshub.security.AgentContext;
import com.crosshub.taobao.service.TaobaoOpsService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 淘宝/天猫 Agent 回写 ingest 接口。对齐抖音 {@code DouyinAgentController} / 拼多多 {@code PddAgentController}。
 * Agent 完成 Playwright 爬取后，将订单/商品/生意参谋数据 POST 到这里入库。
 */
@RestController
@RequestMapping("/api/agent/taobao")
public class TaobaoAgentController {
    private final TaobaoOpsService taobaoOpsService;
    private final AgentContext agentContext;

    public TaobaoAgentController(TaobaoOpsService taobaoOpsService, AgentContext agentContext) {
        this.taobaoOpsService = taobaoOpsService;
        this.agentContext = agentContext;
    }

    @PostMapping("/orders/ingest")
    public Map<String, Object> ingestOrders(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(SqliteBusy.retry(() ->
                taobaoOpsService.ingestOrders(tenantId, body == null ? Map.of() : body)));
    }

    @PostMapping("/products/ingest")
    public Map<String, Object> ingestProducts(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(SqliteBusy.retry(() ->
                taobaoOpsService.ingestProducts(tenantId, body == null ? Map.of() : body)));
    }

    @PostMapping("/compass/ingest")
    public Map<String, Object> ingestCompass(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(SqliteBusy.retry(() ->
                taobaoOpsService.ingestCompass(tenantId, body == null ? Map.of() : body)));
    }

    @PostMapping("/issues/ingest")
    public Map<String, Object> ingestIssues(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(SqliteBusy.retry(() ->
                taobaoOpsService.ingestIssues(tenantId, body == null ? Map.of() : body)));
    }
}
