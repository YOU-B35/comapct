package com.crosshub.agent.service.impl;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.agent.entity.IntegrationAgent;
import com.crosshub.agent.repository.AgentTaskRepository;
import com.crosshub.agent.repository.IntegrationAgentRepository;
import com.crosshub.agent.service.AgentService;
import com.crosshub.agent.service.AgentTaskConcurrency;
import com.crosshub.alibaba1688.service.Alibaba1688AgentTasks;
import com.crosshub.common.AppErrorCode;
import com.crosshub.config.AgentProperties;
import com.crosshub.security.AgentContext;
import com.crosshub.security.AuthContext;
import com.crosshub.temu.service.TemuAgentTasks;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Lazy;
import org.springframework.dao.CannotAcquireLockException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class AgentServiceImpl implements AgentService {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final long AMAZON_TASK_RUNNING_TTL_SECONDS = 6 * 60;
    private static final long AGENT_TASK_RUNNING_TTL_SECONDS = 40 * 60;
    private static final long AGENT_TASK_DEFAULT_TTL_SECONDS = 10 * 60;
    /** 1688 商品同步安全上限；正常应像抖音一样 1–2 分钟内结束。 */
    private static final long A1688_PRODUCTS_SYNC_TTL_SECONDS = 15 * 60;
    private static final long A1688_ORDERS_SYNC_TTL_SECONDS = 10 * 60;
    private static final long A1688_PEER_BESTSELLERS_TTL_SECONDS = 10 * 60;

    private final IntegrationAgentRepository agentRepository;
    private final AgentTaskRepository taskRepository;
    private final AuthContext authContext;
    private final AgentContext agentContext;
    private final DataScopeService dataScopeService;
    private final ObjectMapper objectMapper;
    public interface AmazonWriteBridge {
        void onAgentTaskStarted(AgentTask task);
        void onAgentTaskCompleted(AgentTask task, String status, Map<String, Object> result, String errorCode, String errorMessage);
    }

    private final AmazonSyncBridge amazonSyncBridge;
    private final AmazonWriteBridge amazonWriteBridge;
    private final TemuBridge temuBridge;
    private final DouyinBridge douyinBridge;
    private final Alibaba1688Bridge alibaba1688Bridge;
    private final TransactionTemplate transactionTemplate;
    private final AgentProperties agentProperties;

    public AgentServiceImpl(
            IntegrationAgentRepository agentRepository,
            AgentTaskRepository taskRepository,
            AuthContext authContext,
            AgentContext agentContext,
            DataScopeService dataScopeService,
            ObjectMapper objectMapper,
            TransactionTemplate transactionTemplate,
            AgentProperties agentProperties,
            @Autowired(required = false) @Lazy AmazonSyncBridge amazonSyncBridge,
            @Autowired(required = false) @Lazy AmazonWriteBridge amazonWriteBridge,
            @Autowired(required = false) @Lazy TemuBridge temuBridge,
            @Autowired(required = false) @Lazy DouyinBridge douyinBridge,
            @Autowired(required = false) @Lazy Alibaba1688Bridge alibaba1688Bridge
    ) {
        this.agentRepository = agentRepository;
        this.taskRepository = taskRepository;
        this.authContext = authContext;
        this.agentContext = agentContext;
        this.dataScopeService = dataScopeService;
        this.objectMapper = objectMapper;
        this.transactionTemplate = transactionTemplate;
        this.agentProperties = agentProperties == null ? new AgentProperties() : agentProperties;
        this.amazonSyncBridge = amazonSyncBridge;
        this.amazonWriteBridge = amazonWriteBridge;
        this.temuBridge = temuBridge;
        this.douyinBridge = douyinBridge;
        this.alibaba1688Bridge = alibaba1688Bridge;
    }

    private AgentTaskConcurrency.Limits concurrencyLimits() {
        AgentProperties.Concurrency cfg = agentProperties.getConcurrency();
        return new AgentTaskConcurrency.Limits(
                cfg.getMaxTemu(),
                  cfg.getMaxAliExpress(),
                  cfg.getMaxAmazon(),
                  1,
                  cfg.getMax1688(),
                  cfg.getMaxGlobal(),
                cfg.getMaxClaimBatch(),
                cfg.getTemuParallelSessions()
        );
    }

    public interface AmazonSyncBridge {
        void onAgentTaskStarted(AgentTask task);
        void onAgentTaskCompleted(AgentTask task, String status, Map<String, Object> result, String errorCode, String errorMessage);
    }

    public interface TemuBridge {
        void onAgentTaskStarted(AgentTask task);
        void onAgentTaskCompleted(AgentTask task, String status, Map<String, Object> result, String errorCode, String errorMessage);
    }

    public interface DouyinBridge {
        void onAgentTaskStarted(AgentTask task);
        void onAgentTaskCompleted(AgentTask task, String status, Map<String, Object> result, String errorCode, String errorMessage);
    }

    public interface Alibaba1688Bridge {
        void onAgentTaskStarted(AgentTask task);
        void onAgentTaskCompleted(AgentTask task, String status, Map<String, Object> result, String errorCode, String errorMessage);
    }

    private Long requireBossTenant() {
        if (!authContext.isBossPortal() && !authContext.isAdmin()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, AppErrorCode.FORBIDDEN.getUserMessage());
        }
        return dataScopeService.requireTenantId();
    }

    private IntegrationAgent requireAgent() {
        IntegrationAgent agent = agentContext.agent();
        if (agent == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未认证");
        }
        return agent;
    }

    private String now() {
        return LocalDateTime.now().format(TS);
    }

    @Override
    @Transactional
    public Map<String, Object> registerAgent(String name) {
        Long tenantId = requireBossTenant();
        return createAgent(tenantId, name);
    }

    @Override
    @Transactional
    public Map<String, Object> setupLocalAgent(String name) {
        Long tenantId = requireBossTenant();
        return createAgent(tenantId, name == null || name.isBlank() ? "本机 Agent" : name.trim());
    }

    private Map<String, Object> createAgent(Long tenantId, String name) {
        IntegrationAgent agent = new IntegrationAgent();
        agent.setId(UUID.randomUUID().toString());
        agent.setTenantId(tenantId);
        agent.setName(name);
        agent.setAgentToken(UUID.randomUUID().toString().replace("-", ""));
        agent.setStatus("active");
        agent.setCreatedAt(now());
        agent.setLastHeartbeatAt("");
        agent.setZiniaoOnline(0);
        agentRepository.save(agent);
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("node_id", agent.getId());
        data.put("agent_token", agent.getAgentToken());
        data.put("name", agent.getName());
        return data;
    }

    @Override
    public List<Map<String, Object>> listAgents() {
        Long tenantId = requireBossTenant();
        return agentRepository.findByTenantIdOrderByCreatedAtDesc(tenantId).stream()
                .map(this::toAgentDto)
                .toList();
    }

    @Override
    public Map<String, Object> heartbeat(boolean ziniaoOnline) {
        IntegrationAgent agent = requireAgent();
        String heartbeatAt = now();
        int ziniaoFlag = ziniaoOnline ? 1 : 0;
        for (int attempt = 0; attempt < 5; attempt++) {
            try {
                transactionTemplate.executeWithoutResult(status -> {
                    IntegrationAgent row = agentRepository.findById(agent.getId())
                            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Agent 未认证"));
                    row.setLastHeartbeatAt(heartbeatAt);
                    row.setZiniaoOnline(ziniaoFlag);
                    agentRepository.save(row);
                });
                return Map.of(
                        "node_id", agent.getId(),
                        "tenant_id", agent.getTenantId(),
                        "status", "ok"
                );
            } catch (CannotAcquireLockException ex) {
                if (attempt >= 4) {
                    throw ex;
                }
                sleepQuiet(50L * (attempt + 1));
            }
        }
        throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "数据库繁忙，请稍后重试");
    }

    private void sleepQuiet(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "心跳被中断");
        }
    }

    @Override
    @Transactional
    public List<Map<String, Object>> pollTasks() {
        IntegrationAgent agent = requireAgent();
        Long tenantId = agent.getTenantId();
        reconcileStaleRunningTasks(tenantId);
        AgentTaskConcurrency.Limits limits = concurrencyLimits();
        List<AgentTask> running = taskRepository.findByTenantIdAndStatusOrderByCreatedAtAsc(tenantId, "running");
        AgentTaskConcurrency.State state = new AgentTaskConcurrency.State(limits);
        for (AgentTask runningTask : running) {
            state.admit(analyzeTask(runningTask, limits));
        }
        List<AgentTask> pending = taskRepository.findByTenantIdAndStatusOrderByCreatedAtAsc(tenantId, "pending");
        List<Map<String, Object>> result = new ArrayList<>();
        for (AgentTask task : pending) {
            if (result.size() >= limits.maxClaimBatch()) {
                break;
            }
            if (!isClaimableByAgent(task, agent)) {
                continue;
            }
            AgentTaskConcurrency.Requirement need = analyzeTask(task, limits);
            if (!state.canAdmit(need)) {
                continue;
            }
            task.setStatus("running");
            task.setAgentId(agent.getId());
            task.setStartedAt(now());
            taskRepository.save(task);
            onAgentTaskStarted(task);
            result.add(toTaskDto(task));
            state.admit(need);
        }
        return result;
    }

    /** Blank agent_id = legacy tenant-wide; otherwise only the targeted agent may claim. */
    private static boolean isClaimableByAgent(AgentTask task, IntegrationAgent agent) {
        if (task == null || agent == null) {
            return false;
        }
        String target = task.getAgentId();
        if (target == null || target.isBlank()) {
            return true;
        }
        return target.equals(agent.getId());
    }

    private AgentTaskConcurrency.Requirement analyzeTask(AgentTask task, AgentTaskConcurrency.Limits limits) {
        return AgentTaskConcurrency.analyze(
                task.getTaskType(),
                AgentTaskConcurrency.parsePayload(objectMapper, task.getPayloadJson()),
                task.getTenantId(),
                limits
        );
    }

    @Override
    @Transactional
    public Map<String, Object> completeTask(
            String taskId,
            String status,
            Map<String, Object> result,
            String errorCode,
            String errorMessage
    ) {
        IntegrationAgent agent = requireAgent();
        AgentTask task = taskRepository.findByIdAndTenantId(taskId, agent.getTenantId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "任务不存在"));
        if (!"pending".equalsIgnoreCase(task.getStatus()) && !"running".equalsIgnoreCase(task.getStatus())) {
            return Map.of("task_id", task.getId(), "status", task.getStatus(), "ignored", true);
        }
        String normalized = status == null ? "failed" : status.trim().toLowerCase();
        task.setStatus(normalized);
        task.setFinishedAt(now());
        task.setErrorCode(errorCode == null ? "" : errorCode);
        task.setErrorMessage(errorMessage == null ? "" : errorMessage);
        try {
            task.setResultJson(objectMapper.writeValueAsString(result == null ? Map.of() : result));
        } catch (Exception ex) {
            task.setResultJson("{}");
        }
        taskRepository.save(task);
        if (amazonSyncBridge != null) {
            amazonSyncBridge.onAgentTaskCompleted(task, normalized, result, task.getErrorCode(), task.getErrorMessage());
        }
        if (amazonWriteBridge != null) {
            amazonWriteBridge.onAgentTaskCompleted(task, normalized, result, task.getErrorCode(), task.getErrorMessage());
        }
        if (temuBridge != null) {
            temuBridge.onAgentTaskCompleted(task, normalized, result, task.getErrorCode(), task.getErrorMessage());
        }
        if (douyinBridge != null) {
            douyinBridge.onAgentTaskCompleted(task, normalized, result, task.getErrorCode(), task.getErrorMessage());
        }
        if (alibaba1688Bridge != null) {
            alibaba1688Bridge.onAgentTaskCompleted(task, normalized, result, task.getErrorCode(), task.getErrorMessage());
        }
        return Map.of("task_id", task.getId(), "status", task.getStatus());
    }

    @Override
    public void onAgentTaskStarted(AgentTask task) {
        if (amazonSyncBridge != null) {
            amazonSyncBridge.onAgentTaskStarted(task);
        }
        if (amazonWriteBridge != null) {
            amazonWriteBridge.onAgentTaskStarted(task);
        }
        if (temuBridge != null) {
            temuBridge.onAgentTaskStarted(task);
        }
        if (douyinBridge != null) {
            douyinBridge.onAgentTaskStarted(task);
        }
        if (alibaba1688Bridge != null) {
            alibaba1688Bridge.onAgentTaskStarted(task);
        }
    }

    private Map<String, Object> toAgentDto(IntegrationAgent agent) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", agent.getId());
        row.put("name", agent.getName());
        row.put("status", agent.getStatus());
        row.put("last_heartbeat_at", agent.getLastHeartbeatAt());
        row.put("ziniao_online", agent.getZiniaoOnline());
        row.put("created_at", agent.getCreatedAt());
        return row;
    }

    private Map<String, Object> toTaskDto(AgentTask task) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("task_id", task.getId());
        row.put("id", task.getId());
        row.put("task_type", task.getTaskType());
        row.put("status", task.getStatus());
        try {
            row.put("payload", objectMapper.readValue(
                    task.getPayloadJson() == null || task.getPayloadJson().isBlank() ? "{}" : task.getPayloadJson(),
                    new TypeReference<Map<String, Object>>() {}
            ));
        } catch (Exception ex) {
            row.put("payload", Map.of());
        }
        return row;
    }

    private void reconcileStaleRunningTasks(Long tenantId) {
        List<AgentTask> running = taskRepository.findByTenantIdAndStatusOrderByCreatedAtAsc(tenantId, "running");
        for (AgentTask task : running) {
            if (!isStaleAgentTask(task)) {
                continue;
            }
            task.setStatus("failed");
            task.setFinishedAt(now());
            task.setErrorCode(AppErrorCode.CRAWL_INTERRUPTED.getCode());
            task.setErrorMessage(AppErrorCode.CRAWL_INTERRUPTED.getUserMessage());
            taskRepository.save(task);
            if (amazonSyncBridge != null) {
                amazonSyncBridge.onAgentTaskCompleted(
                        task,
                        "failed",
                        Map.of(),
                        task.getErrorCode(),
                        task.getErrorMessage()
                );
            }
            if (temuBridge != null) {
                temuBridge.onAgentTaskCompleted(
                        task,
                        "failed",
                        Map.of(),
                        task.getErrorCode(),
                        task.getErrorMessage()
                );
            }
            if (douyinBridge != null) {
                douyinBridge.onAgentTaskCompleted(
                        task,
                        "failed",
                        Map.of(),
                        task.getErrorCode(),
                        task.getErrorMessage()
                );
            }
            if (alibaba1688Bridge != null) {
                alibaba1688Bridge.onAgentTaskCompleted(
                        task,
                        "failed",
                        Map.of(),
                        task.getErrorCode(),
                        task.getErrorMessage()
                );
            }
        }
    }

    private boolean isStaleAgentTask(AgentTask task) {
        LocalDateTime base = parseTime(task.getStartedAt());
        if (base == null) {
            base = parseTime(task.getCreatedAt());
        }
        if (base == null) {
            return true;
        }
        long ttl;
        if (TASK_TYPE.equals(task.getTaskType())) {
            ttl = AMAZON_TASK_RUNNING_TTL_SECONDS;
        } else if (TemuAgentTasks.CRAWL.equals(task.getTaskType())) {
            ttl = AGENT_TASK_RUNNING_TTL_SECONDS;
        } else if (Alibaba1688AgentTasks.PRODUCTS_SYNC.equals(task.getTaskType())) {
            ttl = A1688_PRODUCTS_SYNC_TTL_SECONDS;
        } else if (Alibaba1688AgentTasks.ORDERS_SYNC.equals(task.getTaskType())) {
            ttl = A1688_ORDERS_SYNC_TTL_SECONDS;
        } else if (Alibaba1688AgentTasks.PEER_BESTSELLERS_SYNC.equals(task.getTaskType())) {
            ttl = A1688_PEER_BESTSELLERS_TTL_SECONDS;
        } else {
            ttl = AGENT_TASK_DEFAULT_TTL_SECONDS;
        }
        return base.plusSeconds(ttl).isBefore(LocalDateTime.now());
    }

    private LocalDateTime parseTime(String text) {
        if (text == null || text.isBlank()) {
            return null;
        }
        try {
            return LocalDateTime.parse(text, TS);
        } catch (Exception ex) {
            return null;
        }
    }
}
