package com.crosshub.agent.service.impl;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.agent.entity.IntegrationAgent;
import com.crosshub.agent.repository.AgentTaskRepository;
import com.crosshub.agent.repository.IntegrationAgentRepository;
import com.crosshub.config.AgentProperties;
import com.crosshub.security.AgentContext;
import com.crosshub.security.AuthContext;
import com.crosshub.temu.service.TemuAgentTasks;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AgentServiceImplPollFilterTest {

    @Test
    void pollSkipsTaskAimedAtOtherAgent() {
        IntegrationAgentRepository agentRepository = mock(IntegrationAgentRepository.class);
        AgentTaskRepository taskRepository = mock(AgentTaskRepository.class);
        DataScopeService dataScopeService = mock(DataScopeService.class);
        TransactionTemplate transactionTemplate = mock(TransactionTemplate.class);

        AgentContext agentContext = new AgentContext();
        IntegrationAgent agent = new IntegrationAgent();
        agent.setId("A1");
        agent.setTenantId(5L);
        agentContext.setAgent(agent);

        AgentTask foreign = new AgentTask();
        foreign.setId("agt-other");
        foreign.setTenantId(5L);
        foreign.setAgentId("A2");
        foreign.setTaskType(TemuAgentTasks.LOGIN_OPEN);
        foreign.setStatus("pending");
        foreign.setPayloadJson("{\"tenant_id\":5,\"session_key\":\"default\"}");
        foreign.setCreatedAt("2026-08-11 10:00:00");

        when(taskRepository.findByTenantIdAndStatusOrderByCreatedAtAsc(5L, "running"))
                .thenReturn(List.of());
        when(taskRepository.findByTenantIdAndStatusOrderByCreatedAtAsc(5L, "pending"))
                .thenReturn(List.of(foreign));

        AgentServiceImpl service = new AgentServiceImpl(
                agentRepository,
                taskRepository,
                new AuthContext(),
                agentContext,
                dataScopeService,
                new ObjectMapper(),
                transactionTemplate,
                new AgentProperties(),
                null,
                null,
                null,
                null,
                null,
                null,
                null
        );

        List<Map<String, Object>> claimed = service.pollTasks();

        assertTrue(claimed.isEmpty());
        verify(taskRepository, never()).save(any());
    }
}
