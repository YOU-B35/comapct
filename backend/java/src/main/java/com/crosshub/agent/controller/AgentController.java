package com.crosshub.agent.controller;

import com.crosshub.agent.dto.AgentHeartbeatRequest;
import com.crosshub.agent.dto.AgentRegisterRequest;
import com.crosshub.agent.dto.AgentTaskCompleteRequest;
import com.crosshub.agent.service.AgentService;
import com.crosshub.security.AgentContext;
import com.crosshub.temu.service.TemuAgentService;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/agent")
public class AgentController {
    private final AgentService agentService;
    private final TemuAgentService temuAgentService;
    private final AgentContext agentContext;

    public AgentController(AgentService agentService, TemuAgentService temuAgentService, AgentContext agentContext) {
        this.agentService = agentService;
        this.temuAgentService = temuAgentService;
        this.agentContext = agentContext;
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

    @PostMapping("/temu/ingest")
    public Map<String, Object> ingestTemu(@RequestBody Map<String, Object> payload) {
        Long tenantId = agentContext.tenantId();
        if (tenantId == null) {
            throw new org.springframework.web.server.ResponseStatusException(
                    org.springframework.http.HttpStatus.UNAUTHORIZED,
                    "Agent 未认证"
            );
        }
        return Map.of("success", true, "data", temuAgentService.ingestFromAgent(tenantId, payload));
    }
}
