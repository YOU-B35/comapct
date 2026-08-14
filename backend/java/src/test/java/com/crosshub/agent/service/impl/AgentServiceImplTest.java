package com.crosshub.agent.service.impl;

import com.crosshub.agent.entity.AgentTask;
import com.crosshub.agent.entity.IntegrationAgent;
import com.crosshub.agent.repository.AgentTaskRepository;
import com.crosshub.agent.repository.IntegrationAgentRepository;
import com.crosshub.config.AgentProperties;
import com.crosshub.security.AgentContext;
import com.crosshub.security.AuthContext;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AgentServiceImplTest {

    @Test
    void completeTaskIgnoresLateCompletionForAlreadyFailedTask() {
        IntegrationAgentRepository agentRepository = mock(IntegrationAgentRepository.class);
        AgentTaskRepository taskRepository = mock(AgentTaskRepository.class);
        DataScopeService dataScopeService = mock(DataScopeService.class);
        TransactionTemplate transactionTemplate = mock(TransactionTemplate.class);
        AgentServiceImpl.AmazonSyncBridge amazonSyncBridge = mock(AgentServiceImpl.AmazonSyncBridge.class);
        AgentServiceImpl.AmazonWriteBridge amazonWriteBridge = mock(AgentServiceImpl.AmazonWriteBridge.class);
        AgentServiceImpl.TemuBridge temuBridge = mock(AgentServiceImpl.TemuBridge.class);

        AgentContext agentContext = new AgentContext();
        IntegrationAgent agent = new IntegrationAgent();
        agent.setId("agent-1");
        agent.setTenantId(5L);
        agentContext.setAgent(agent);

        AgentTask task = new AgentTask();
        task.setId("agt-timeout");
        task.setTenantId(5L);
        task.setTaskType("amazon_sync");
        task.setStatus("failed");
        task.setErrorCode("CRAWL_INTERRUPTED");
        task.setErrorMessage("任务已超时回收");
        task.setResultJson("{}");

        when(taskRepository.findByIdAndTenantId("agt-timeout", 5L)).thenReturn(Optional.of(task));

        AgentServiceImpl service = new AgentServiceImpl(
                agentRepository,
                taskRepository,
                new AuthContext(),
                agentContext,
                dataScopeService,
                new ObjectMapper(),
                transactionTemplate,
                new AgentProperties(),
                amazonSyncBridge,
                amazonWriteBridge,
                temuBridge,
                null
        );

        Map<String, Object> result = service.completeTask(
                "agt-timeout",
                "success",
                Map.of("products_count", 10),
                "",
                ""
        );

        assertEquals("failed", result.get("status"));
        assertEquals("failed", task.getStatus());
        verify(taskRepository, never()).save(any());
        verify(amazonSyncBridge, never()).onAgentTaskCompleted(any(), any(), any(), any(), any());
        verify(amazonWriteBridge, never()).onAgentTaskCompleted(any(), any(), any(), any(), any());
        verify(temuBridge, never()).onAgentTaskCompleted(any(), any(), any(), any(), any());
    }
}
