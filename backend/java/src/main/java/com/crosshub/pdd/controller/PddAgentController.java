package com.crosshub.pdd.controller;

import com.crosshub.common.ApiResult;
import com.crosshub.common.SqliteBusy;
import com.crosshub.monitor.service.impl.MonitorIngestService;
import com.crosshub.pdd.service.PddOpsService;
import com.crosshub.security.AgentContext;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 拼多多 Agent 回写 ingest 接口。对齐抖音 {@code DouyinAgentController}。
 * Agent 完成 Playwright 爬取后，将订单/商品/罗盘数据 POST 到这里入库。
 */
@RestController
@RequestMapping("/api/agent/pdd")
public class PddAgentController {
    private final PddOpsService pddOpsService;
    private final MonitorIngestService monitorIngestService;
    private final AgentContext agentContext;

    public PddAgentController(
            PddOpsService pddOpsService,
            MonitorIngestService monitorIngestService,
            AgentContext agentContext
    ) {
        this.pddOpsService = pddOpsService;
        this.monitorIngestService = monitorIngestService;
        this.agentContext = agentContext;
    }

    @PostMapping("/orders/ingest")
    public Map<String, Object> ingestOrders(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(SqliteBusy.retry(() ->
                pddOpsService.ingestOrders(tenantId, body == null ? Map.of() : body)));
    }

    @PostMapping("/products/ingest")
    public Map<String, Object> ingestProducts(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(SqliteBusy.retry(() ->
                pddOpsService.ingestProducts(tenantId, body == null ? Map.of() : body)));
    }

    @PostMapping("/compass/ingest")
    public Map<String, Object> ingestCompass(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(SqliteBusy.retry(() ->
                pddOpsService.ingestCompass(tenantId, body == null ? Map.of() : body)));
    }

    @PostMapping("/issues/ingest")
    public Map<String, Object> ingestIssues(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(SqliteBusy.retry(() ->
                pddOpsService.ingestIssues(tenantId, body == null ? Map.of() : body)));
    }

    @PostMapping("/monitor/ingest")
    public Map<String, Object> ingestMonitorSnapshot(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(SqliteBusy.retry(() ->
                monitorIngestService.ingestSnapshot(tenantId, body == null ? Map.of() : body)));
    }
}
