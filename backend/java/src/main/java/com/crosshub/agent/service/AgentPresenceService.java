package com.crosshub.agent.service;

import com.crosshub.agent.entity.IntegrationAgent;
import com.crosshub.agent.repository.IntegrationAgentRepository;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class AgentPresenceService {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final long AGENT_HEARTBEAT_TTL_SECONDS = 90;

    private final IntegrationAgentRepository agentRepository;

    public AgentPresenceService(IntegrationAgentRepository agentRepository) {
        this.agentRepository = agentRepository;
    }

    public boolean isAgentOnline(Long tenantId) {
        return findLatestOnlineAgent(tenantId) != null;
    }

    public IntegrationAgent findLatestOnlineAgentForTenant(Long tenantId) {
        return findLatestOnlineAgent(tenantId);
    }

    public boolean isAgentOnlineForTenant(Long tenantId) {
        return findLatestOnlineAgentForTenant(tenantId) != null;
    }

    public IntegrationAgent findLatestOnlineAgent(Long tenantId) {
        if (tenantId == null) {
            return null;
        }
        List<IntegrationAgent> agents = agentRepository.findByTenantIdOrderByLastHeartbeatAtDesc(tenantId);
        if (agents == null || agents.isEmpty()) {
            agents = agentRepository.findByTenantIdOrderByCreatedAtDesc(tenantId);
        }
        for (IntegrationAgent agent : agents) {
            if (isHeartbeatFresh(agent)) {
                return agent;
            }
        }
        return null;
    }

    public boolean isAgentOnlineForUser(Long userId) {
        return findLatestOnlineAgentForUser(userId) != null;
    }

    public IntegrationAgent findLatestOnlineAgentForUser(Long userId) {
        if (userId == null) {
            return null;
        }
        List<IntegrationAgent> agents = agentRepository.findByBoundUserIdOrderByLastHeartbeatAtDesc(userId);
        for (IntegrationAgent agent : agents) {
            if (isHeartbeatFresh(agent)) {
                return agent;
            }
        }
        return null;
    }

    /** 返回当前心跳在线的租户 ID（去重）。前期单机多租户可行性用。 */
    public List<Long> listOnlineTenantIds() {
        List<Long> out = new ArrayList<>();
        for (IntegrationAgent agent : agentRepository.findAll()) {
            if (!isHeartbeatFresh(agent)) {
                continue;
            }
            Long tenantId = agent.getTenantId();
            if (tenantId != null && !out.contains(tenantId)) {
                out.add(tenantId);
            }
        }
        return out;
    }

    /** 所有曾注册助手的租户（含当前离线），用于日批写失败可见。 */
    public List<Long> listRegisteredTenantIds() {
        List<Long> out = new ArrayList<>();
        for (IntegrationAgent agent : agentRepository.findAll()) {
            Long tenantId = agent.getTenantId();
            if (tenantId != null && !out.contains(tenantId)) {
                out.add(tenantId);
            }
        }
        return out;
    }

    public Map<String, Object> integrationStatus(Long tenantId) {
        List<IntegrationAgent> agents = tenantId == null
                ? List.of()
                : agentRepository.findByTenantIdOrderByCreatedAtDesc(tenantId);
        IntegrationAgent latestOnline = null;
        boolean ziniaoOnline = false;
        for (IntegrationAgent agent : agents) {
            if (!isHeartbeatFresh(agent)) {
                continue;
            }
            if (latestOnline == null) {
                latestOnline = agent;
            }
            if (agent.getZiniaoOnline() != null && agent.getZiniaoOnline() == 1) {
                ziniaoOnline = true;
            }
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("agent_online", latestOnline != null);
        out.put("ziniao_online", ziniaoOnline);
        out.put("agent_count", agents.size());
        if (latestOnline != null) {
            out.put("node_id", latestOnline.getId());
            out.put("node_name", latestOnline.getName());
            out.put("last_heartbeat_at", latestOnline.getLastHeartbeatAt());
        } else {
            out.put("node_id", "");
            out.put("node_name", "");
            out.put("last_heartbeat_at", "");
        }
        return out;
    }

    private boolean isHeartbeatFresh(IntegrationAgent agent) {
        if (agent == null || !"active".equalsIgnoreCase(agent.getStatus())) {
            return false;
        }
        LocalDateTime heartbeat = parseTime(agent.getLastHeartbeatAt());
        if (heartbeat == null) {
            return false;
        }
        return !heartbeat.plusSeconds(AGENT_HEARTBEAT_TTL_SECONDS).isBefore(LocalDateTime.now());
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
