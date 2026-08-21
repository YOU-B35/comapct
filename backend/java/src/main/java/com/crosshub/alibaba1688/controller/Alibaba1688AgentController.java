package com.crosshub.alibaba1688.controller;

import com.crosshub.alibaba1688.service.Alibaba1688ProductService;
import com.crosshub.alibaba1688.service.Alibaba1688RetailOpsService;
import com.crosshub.common.ApiResult;
import com.crosshub.monitor.service.impl.MonitorIngestService;
import com.crosshub.security.AgentContext;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/agent/1688")
public class Alibaba1688AgentController {
    private final Alibaba1688ProductService productService;
    private final Alibaba1688RetailOpsService retailOpsService;
    private final MonitorIngestService monitorIngestService;
    private final AgentContext agentContext;

    public Alibaba1688AgentController(
            Alibaba1688ProductService productService,
            Alibaba1688RetailOpsService retailOpsService,
            MonitorIngestService monitorIngestService,
            AgentContext agentContext
    ) {
        this.productService = productService;
        this.retailOpsService = retailOpsService;
        this.monitorIngestService = monitorIngestService;
        this.agentContext = agentContext;
    }

    @PostMapping("/products/ingest")
    public Map<String, Object> ingestProducts(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(productService.ingestProducts(tenantId, body == null ? Map.of() : body));
    }

    @PostMapping("/orders/ingest")
    public Map<String, Object> ingestOrders(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(retailOpsService.ingestOrders(tenantId, body == null ? Map.of() : body));
    }

    @PostMapping("/peer-bestsellers/ingest")
    public Map<String, Object> ingestPeerBestsellers(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(retailOpsService.replacePeerBestsellers(tenantId, body == null ? Map.of() : body));
    }

    @PostMapping("/monitor/ingest")
    public Map<String, Object> ingestMonitorSnapshot(@RequestBody Map<String, Object> body) {
        Long tenantId = agentContext.agent() == null ? null : agentContext.agent().getTenantId();
        return ApiResult.ok(monitorIngestService.ingestSnapshot(tenantId, body == null ? Map.of() : body));
    }
}
